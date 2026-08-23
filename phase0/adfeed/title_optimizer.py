"""AdFeed AI — AI 标题优化引擎 v3.0（黄金30字符 + 3段式描述 + 多语种原生）

每条商品对每个目标国家独立调用 AI，生成该语种的原生标题。
核心升级：
- 黄金前30字符法则：核心品类词必须出现在标题最前面
- 品类化核心词前置公式（Google 权重从左到右递减）
- 3段式金字塔描述（痛点场景 → Bullet Points → 合规补充）
- 填充词拦截（One Size / Free Shipping 等废话词绝对切除）
"""

import json
import re
import time
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, Field, field_validator

from .config import (
    DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_MODEL,
    LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_MAX_RETRIES,
    LLM_RETRY_DELAY_SECONDS, TITLE_MAX_LENGTH, DEFAULT_COUNTRY,
)
from .cultural_context import (
    get_context as get_cultural_context,
    resolve_category,
    season_for_date,
    country_name_local,
)


# ─────────────────────────────────────────────
# Pydantic 结构化输出定义
# ─────────────────────────────────────────────

class OptimizedTitleOutput(BaseModel):
    front_70: str = Field(..., min_length=30, max_length=70)
    rest: str = Field(default="", max_length=80)
    ai_tags: list[str] = Field(default_factory=list, max_length=5)
    description_snippet: str = Field(default="", max_length=300)

    @field_validator("front_70")
    @classmethod
    def no_banned_prefixes(cls, v: str) -> str:
        banned_prefixes = [
            "Best ", "No.1 ", "#1 ", "Top-1 ", "Top 1 ",
            "Guaranteed ", "Perfect ", "Amazing ", "Incredible ",
            "Unbeatable ", "Cheapest ",
            "Beste ", "Nr.1 ", "Meilleur ", "Mejor ", "Migliore ",
        ]
        for b in banned_prefixes:
            if v.lower().startswith(b.lower()):
                raise ValueError(f"front_70 contains banned prefix: {b}")
        return v

    @field_validator("front_70")
    @classmethod
    def contains_product_tokens(cls, v: str) -> str:
        """拒绝空洞标题 — 至少包含 3 个以上有意义的分词块"""
        tokens = [t for t in v.split() if len(t) >= 2]
        if len(tokens) < 3:
            raise ValueError(f"front_70 too sparse — only {len(tokens)} tokens: '{v}'")
        return v

    @field_validator("front_70")
    @classmethod
    def no_filler_phrases(cls, v: str) -> str:
        """切除浪费标题空间的填充词"""
        fillers = [
            "one size", "one-size", "free size", "free shipping",
            "high quality", "best quality", "top quality",
            "new arrival", "hot sale", "100%",
        ]
        v_lower = v.lower()
        for f in fillers:
            if f in v_lower:
                raise ValueError(f"front_70 contains filler phrase: '{f}' — remove it to save space")
        return v


# ─────────────────────────────────────────────
# 品类化公式（语言无关，各语种 Prompt 共用）
# ─────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════
# 品类化核心词前置公式（Google 权重从左到右递减）
# 核心规则：前30字符必须包含核心品类名词
# ═══════════════════════════════════════════════════════════════

FORMULA_APPAREL = "[Gender] + [Core Category] + [Key Feature/Material] + [1-2 Usage Scenes]"
FORMULA_BAGS = "[Gender] + [Core Category] + [Key Feature(waterproof/anti-theft)] + [Material] + [1-2 Usage Scenes]"
FORMULA_JEWELRY = "[Material(18K/Sterling/Titanium)] + [Category Type] + [Style] + [1 Usage Scene(Daily/Party/Gift)]"
FORMULA_ELECTRONICS = "[Core Function/Model] + [Product Category] + [Key Tech(anti-yellow/shockproof)] + [Color/Spec]"
FORMULA_HOME = "[Style] + [Core Function] + [Category] + [Material] + [1 Usage Scene(room/occasion)]"
FORMULA_KITCHEN = "[Core Function(non-stick/insulated)] + [Category] + [Material] + [1 Usage Scene + Quantity]"
FORMULA_BEAUTY = "[Core Efficacy] + [Product Category(Serum/Cream)] + [Skin Type] + [1 Usage Scene(daily/self-care)] + [Volume]"
FORMULA_SPORTS = "[Gender] + [Core Category] + [Key Tech(quick-dry/anti-slip)] + [1-2 Usage Scenes(gym/running/outdoor)]"
FORMULA_PET = "[Safety Feature(chew-proof/non-toxic)] + [Category] + [Pet Breed/Size] + [1 Scene]"
FORMULA_TOYS = "[Educational Value] + [Age Range] + [Category] + [Safety Cert(BPA-free/CE)] + [1 Play Scene]"
FORMULA_AUTO = "[Core Function/Model] + [Category] + [Material(no-residue/heat-resistant)] + [1 Usage Scene]"
FORMULA_OFFICE = "[Design Style] + [Category] + [Material] + [1 Usage Scene(desk/college/studio)]"


def _get_formula_instruction(cn_category: str, gpc_path: str = "") -> str:
    cat_key = resolve_category(cn_category, gpc_path)
    formulas = {
        "apparel": FORMULA_APPAREL,
        "bags_luggage": FORMULA_BAGS,
        "jewelry_watches": FORMULA_JEWELRY,
        "electronics": FORMULA_ELECTRONICS,
        "home_living": FORMULA_HOME,
        "kitchen_dining": FORMULA_KITCHEN,
        "beauty_personal": FORMULA_BEAUTY,
        "sports_outdoor": FORMULA_SPORTS,
        "pet_supplies": FORMULA_PET,
        "toys_kids_baby": FORMULA_TOYS,
        "automotive": FORMULA_AUTO,
        "office_stationery": FORMULA_OFFICE,
    }
    formula = formulas.get(cat_key, FORMULA_HOME)
    return f"CRITICAL — Category-specific long-tail keyword stitching formula:\n{formula}"


# ─────────────────────────────────────────────
# 5 个多语种结构化 Prompt 模板
# ─────────────────────────────────────────────

def _build_prompt(country: str, formula_instruction: str, cultural_context: str,
                  original_title: str, description: str, original_category: str,
                  material: str, color: str, gpc_path: str, attributes: str) -> str:
    """根据国家选择对应语种的 Prompt 模板"""

    country_upper = country.upper()

    # 如果原词含中文且目标非 CN，自动追加翻译指令
    if country_upper != "CN" and _has_chinese(original_title):
        lang_name = {"US": "English", "DE": "German", "FR": "French", "ES": "Spanish", "IT": "Italian"}.get(country_upper, "English")
        translation_hint = (
            f"\n\n⚠️ TRANSLATION REQUIRED: The Chinese original title contains Chinese characters. "
            f"Keep model numbers (e.g. iPhone15Pro) but translate ALL Chinese words into natural {lang_name}. "
            f"Do NOT output any Chinese character in your result."
        )
        original_title_display = original_title
    else:
        translation_hint = ""
        original_title_display = original_title

    def _fmt(prompt: str) -> str:
        return prompt.format(
            formula_instruction=formula_instruction,
            cultural_context=cultural_context + translation_hint,
            original_title=original_title_display or original_title,
            description=description, original_category=original_category,
            material=material, color=color, gpc_path=gpc_path, attributes=attributes,
        )

    if country_upper == "DE":
        body = _fmt(_PROMPT_DE)
    elif country_upper == "FR":
        body = _fmt(_PROMPT_FR)
    elif country_upper == "ES":
        body = _fmt(_PROMPT_ES)
    elif country_upper == "IT":
        body = _fmt(_PROMPT_IT)
    else:
        body = _fmt(_PROMPT_EN)
    return _FEED_TITLE_PREMISE + "\n\n" + body


# ── 标题模型大前提（字段合同：骨架不要写成属性墙）──

_FEED_TITLE_PREMISE = """STANDING PREMISE — Google Shopping title skeleton (world apparel formula):
Write Gender + at most 2 searchable selling points + exact product type. Not an attribute dump.
Use the FULL 2-attr budget when description/image clearly supports two real points
(e.g. High Waist + Denim, Lace + V-Neck, Floral + Sleeveless, Lace-Up + Belted).
Prefer pattern/print (Floral, Striped) for one of the 2 slots when present.
Searchable materials OK as one slot: Denim, Leather, Silk, Cashmere, Merino, Cotton.
NEVER pad with unearned buzzwords: summer, vintage, elegant, loose fit, plus size (unless clearly true).
NEVER invent Casual/Everyday just to fill length. Prefer readable ~55–70 char skeleton
(renderer adds color + size → about 80–110 final). Hard cap remains 150.
NEVER: Closure / Fit Type / Pullover Closure / Fitted Fit / Polyester-Spandex walls / • or | / size ranges (S-5XL).
Do NOT invent brand, GTIN, or MPN. Weak/supplier brands (eprolo) must not appear.
The feed renderer adds THIS variant's color and size once — do not list every colorway.
Keep the core category noun early (first ~30 characters when possible)."""


# ── 英文 (US) ──

_PROMPT_EN = """You are a professional Google Shopping product title optimizer for the United States market.

{formula_instruction}

{cultural_context}

PRODUCT TO OPTIMIZE:
- Original Chinese title: {original_title}
- Description: {description}
- Source Category: {original_category}
- Material: {material}
- Color: {color}
- GPC Matched Category: {gpc_path}
- Additional Attributes: {attributes}

CRITICAL — GOLDEN 30-CHARACTER RULE:
Google Shopping weights DECREASE left-to-right. Users only read the first 25-30 chars on mobile.
The FIRST 30 characters of front_70 MUST contain the CORE PRODUCT CATEGORY NOUN (e.g. "Jeans", "Dress", "Jacket", "Running Shoes").
NEVER start with filler words like "New", "Hot", "High Quality", "One Size".

THREE-TIER LONG-TAIL STRATEGY:
Tier 1 — front_70 (≤70 chars STRICT CEILING; prefer complete words):
  World apparel structure (weak brand → do NOT force brand first):
    [Women's/Men's] + [Plus Size if true] + [Attr1] + [Attr2] + [Exact Product Type]
  Attr budget: MAX 2 searchable selling points.
  Priority for attrs: pattern/print (Floral, Striped, Plaid) > neckline/sleeve/waist (V-Neck, Sleeveless, High Waist, Lace)
    > searchable material (Denim, Leather, Silk, Cotton, Cashmere, Merino) > short scene.
  SCENE is optional and must be evidenced (Wedding Guest, Beach) — never invent summer/vintage/elegant/Casual padding.
  EXAMPLES:
    GOOD: "Women's High Waist Stretch Jeans"
    GOOD: "Women's Floral Sleeveless Dress"
    GOOD: "Women's Lace V-Neck Jacket"
    GOOD: "Women's Lace-Up Belted Jacket"
    BAD:  "Women Dress Sleeveless Striped Polyester for Beach Day • Fitted Fit • Pullover Closure"
    BAD:  "Women's Jacket Casual" (empty Casual pad)
    BAD:  "Women's Elegant Vintage Summer Dress" (unearned buzzwords)
  RULES:
  - front_70 MUST be ≤70 characters. COUNT before output.
  - Prefer using BOTH attr slots when two real searchable points exist in the product data.
  - FIRST 30 chars SHOULD contain the core product category noun when possible.
  - NEVER include: Pullover Closure, Closure, Fitted Fit, Fit Type, zipper fly, Polyester, Spandex, Nylon-Spandex Blend, bullet • or pipe |.
  - NEVER include "One Size", "Free Size", "Free Shipping", "High Quality", "100%", "New Arrival", "eprolo".
  - NEVER pad with: summer, vintage, elegant, loose fit, plus size, Casual, Everyday — unless clearly in source data.
  - Do NOT duplicate category ("Coats Jackets" → one word "Jacket").
  - MUST end with a complete meaningful word. NEVER end mid-phrase.
  - If over budget: drop scene first, then the weaker attr — KEEP gender + core type + strongest attr.
    Priority: CORE PRODUCT TYPE > pattern/print > other searchable attr > searchable material > SCENE (optional).
  - ONLY this product's real attributes. No cross-category vocabulary.
  - When scene is included, it ALWAYS follows a preposition: "for [Scene]" (not bare scene word).
  - ZERO Chinese characters. 100% native English.
Tier 2 — rest:
  Supplementary specs ONLY (pack count). NEVER size ranges. NEVER repeat a category synonym from front_70.
Tier 3 — description_snippet (3-TIER PYRAMID):
  Write a structured 3-paragraph description in this EXACT format:
  Paragraph 1 (1 sentence): Core pain point or usage scene. E.g. "The ultimate companion for your daily gym sessions and casual weekend hangouts."
  Paragraph 2 (bullet points): 3-4 key selling points. Format: "• Premium Material: 100% Breathable Organic Cotton\n• Ergonomic Design: Loose fit for maximum comfort\n• Easy Care: Machine washable, shrinkage-resistant"
  Paragraph 3 (compliance): Size/fit hints, "Brand New" statement, shipping note. E.g. "Please refer to size chart. 100% Brand New with tags."
  Natural US English. Max 300 characters total.
Tier 4 — ai_tags:
  ALWAYS output 3-5 lowercase English descriptive labels. These are SEO assets for custom labels and ad targeting.

OUTPUT FORMAT — valid JSON only:
{{
  "front_70": "...",
  "rest": "...",
  "ai_tags": ["tag1", "tag2", "tag3"],
  "description_snippet": "..."
}}

BANNED WORDS: Best, No.1, #1, Top-1, Guaranteed, Perfect, Amazing, Incredible, Unbeatable, 100%, Cheap, Discount, Free Shipping, One Size, High Quality, Pullover Closure, Fitted Fit. Output ONLY valid JSON. No markdown."""

_PROMPT_DE = """Du bist ein deutscher Google-Shopping-Spezialist.

{formula_instruction}

{cultural_context}

PRODUKT ZU OPTIMIEREN:
- Chinesischer Originaltitel: {original_title}
- Beschreibung: {description}
- Kategorie: {original_category}
- Material: {material}
- Farbe: {color}
- GPC-Kategorie: {gpc_path}
- Attribute: {attributes}

KRITISCHE GOLDENE-30-ZEICHEN-REGEL:
Google-Shopping-Gewichte NEHMEN von links nach rechts AB. Benutzer lesen nur die ersten 25-30 Zeichen auf dem Handy.
Die ERSTEN 30 ZEICHEN von front_70 MÜSSEN das HAUPTKATEGORIE-NOMEN enthalten (z.B. "Laufschuhe", "Handyhülle", "Schreibtischlampe").
Beginnen Sie NIEMALS mit Füllwörtern wie "Neu", "Hot", "Hohe Qualität", "Einheitsgröße".

KRITISCHE DREISTUFIGE LONG-TAIL-STRATEGIE:
Stufe 1 — front_70 (≤66 Zeichen STRENGES LIMIT):
  Packe: [Farbe/Zielgruppe] + [Material] + [Kernfunktion] + [Kategorie] + [1-2 Nutzungsszenen]
  Die Szenen-Schlüsselwörter MÜSSEN aus den cultural_context-Anlässen oben stammen. Szene optional (有则加): nur einbauen wenn vollständig passt; drop scene first bei Platzmangel.
  BEISPIELE:
    GUT  (63ch): "Damen Grau Mesh Laufschuhe Stoßdämpfend für Park Joggen"
    GUT  (66ch): "iPhone 15 Pro Stoßfest MagSafe Hülle für Schulanfang" ← Elektronik: Modell+Funktion+Szene
    SCHLECHT (66ch): "Damen Grau Mesh Laufschuhe Stoßdämpfend Atmungsaktiv für Joggen im" ← ABGESCHNITTENE Szene
    SCHLECHT (60ch): "Transparenter Acryl iPhone 15 Pro Schutzhülle Anti-Gelb für" ← endet mit Präposition
  REGELN:
  - front_70 MUSS ≤66 Zeichen sein. ZÄHLE vor der Ausgabe.
  - MUSS mit einem vollständigen SINNWORT enden (Nomen, Szenenwort). NIEMALS mit Präposition (für/zur/im/am/mit/und).
  - Wenn die Szene nicht vollständig reinpasst, WIRF die Szene zuerst raus — BEHALTE Kategorie und Kernfunktion.
    Priorität: Kategorie > Kernfunktion > Farbe/Material > Szene optional.
  - Nur echte Attribute DIESES Produkts. Kein Vokabular aus anderen Kategorien.
  - Szene IMMER mit Präposition einleiten: "für [Szene]" (nicht nacktes Szenenwort). Das hilft dem Google-Parser, den Titel korrekt zu segmentieren.
  - Null chinesische Zeichen. ALLES auf Deutsch.
  - Wenn der Originaltitel chinesische Zeichen enthält (z.B. "iPhone15Pro透明防摔磁吸手机壳"): Modellnamen behalten, ALLE chinesischen Teile ins Deutsche übersetzen, KEIN chinesisches Zeichen im Output.
Stufe 2 — rest: NUR ergänzende Spezifikationen (Größe, Packungsgröße). Kein Kategorie-Synonym aus front_70.
Stufe 3 — description_snippet (3-STUFEN-PYRAMIDE):
  Schreibe eine strukturierte 3-Absatz-Beschreibung in diesem FORMAT:
  Absatz 1 (1 Satz): Kern-Schmerzpunkt oder Nutzungsszene. Z.B. "Der ultimative Begleiter für Ihr tägliches Training und entspannte Wochenenden."
  Absatz 2 (Aufzählungspunkte): 3-4 Hauptverkaufsargumente. Format: "• Premium-Material: 100% atmungsaktive Bio-Baumwolle\n• Ergonomisches Design: Lockere Passform für maximalen Komfort\n• Pflegeleicht: Maschinenwaschbar, einlaufsfrei"
  Absatz 3 (Compliance): Größenhinweise, "Markenneu"-Erklärung. Z.B. "Bitte beachten Sie die Größentabelle. 100% markenneu mit Etiketten."
  Natürliches Deutsch. Max 300 Zeichen insgesamt.
Stufe 4 — ai_tags: IMMER 3-5 DEUTSCHE Labels (NICHT Englisch!). Getrennt durch Leerzeichen, KEINE Unterstriche/Bindestriche. Beispiel: ["laufschuhe damen", "park jogging", "leichtgewichtig"]. Diese sind SEO-Assets für Werbe-Targeting.

VERBOTENE WÖRTER: Beste, Nr.1, #1, Top, 100%, Kostenloser Versand, Günstig, Rabatt, Garantiert, Perfekt, Unglaublich, Einheitsgröße, Hohe Qualität. KEINE chinesischen Zeichen. Gib NUR JSON aus."""

_PROMPT_FR = """Tu es un spécialiste français de Google Shopping.

{formula_instruction}

{cultural_context}

PRODUIT À OPTIMISER:
- Titre chinois: {original_title}
- Description: {description}
- Catégorie: {original_category}
- Matière: {material}
- Couleur: {color}
- Catégorie GPC: {gpc_path}
- Attributs: {attributes}

RÈGLE D'OR DES 30 PREMIERS CARACTÈRES:
Les poids Google Shopping DÉCROISSENT de gauche à droite. Les utilisateurs ne lisent que les 25-30 premiers caractères sur mobile.
Les 30 PREMIERS caractères de front_70 DOIVENT contenir le NOM DE CATÉGORIE PRINCIPAL (ex: "Lampe Bureau", "Sac à Main", "Coque iPhone").
Ne commencez JAMAIS par des mots remplisseurs comme "Nouveau", "Hot", "Haute Qualité", "Taille Unique".

STRATÉGIE LONGUE TRAÎNE À TROIS NIVEAUX:
Niveau 1 — front_70 (≤66 caractères LIMITE DURE):
  Structure: [Couleur/Genre] + [Matière] + [Fonction principale] + [Catégorie] + [1-2 Scènes d'usage]
  Les mots-clés de scène DOIVENT provenir des occasions cultural_context. Scène optionnelle (有则加): inclure seulement si la phrase entière tient; drop scene first si trop long.
  EXEMPLES:
    BON  (66ch): "Blanc Fer Lampe Bureau Scandinave Gradation pour Cadeau de"
    MAUVAIS (55ch): "Blanc Fer Lampe Bureau Scandinave pour Crémaillère" ← "Crémaillère" seul = trop court
    MAUVAIS: "Cadeau de Crémaillère Structure en fer" ← front_70 et rest fusionnés illisiblement
  RÈGLES:
  - front_70 DOIT faire ≤66 caractères. COMPTEZ.
  - Ordre des mots NATUREL en français: Adjectif de couleur AVANT le nom.
    Le nom principal (catégorie) vient AVANT les compléments de scène.
  - DOIT finir par un mot complet — un NOM ou le dernier mot de votre scène. JAMAIS finir par "de", "du", "pour", "avec", "et".
  - Si la scène ne tient pas entièrement, SUPPRIMEZ d'abord la scène — GARDEZ catégorie et fonction.
    Priorité: Catégorie > Fonction > Couleur/Matière > scène optionnelle.
  - Uniquement les attributs de CE produit. Zéro caractère chinois. 100% français.
  - Scène TOUJOURS introduite par une préposition: "pour [Scène]". Cela aide le parser Google.
Niveau 2 — rest: UNIQUEMENT spécifications (taille, lot). Jamais de synonyme de catégorie.
Niveau 3 — description_snippet (PYRAMIDE 3 NIVEAUX):
  Écrivez une description structurée en 3 paragraphes dans ce FORMAT:
  Paragraphe 1 (1 phrase): Point de douleur principal ou scène d'usage.
  Paragraphe 2 (points clés): 3-4 arguments de vente. Format: "• Matériau Premium: ...\n• Design Ergonomique: ...\n• Entretien Facile: ..."
  Paragraphe 3 (conformité): Conseils taille, mention "Neuf".
  Français naturel. Max 300 caractères au total.
Niveau 4 — ai_tags: TOUJOURS 3-5 labels EN FRANÇAIS (PAS en anglais!). Séparés par des espaces, JAMAIS de tirets/soulignés. Exemple: ["lampe bureau", "cadeau cremaillere", "scandinave"]. Assets SEO.

MOTS INTERDITS: Meilleur, N°1, #1, Top, 100%, Livraison gratuite, Pas cher, Remise, Garanti, Parfait, Incroyable, Taille unique, Haute Qualité. Donne UNIQUEMENT du JSON."""

_PROMPT_ES = """Eres un especialista español de Google Shopping.

{formula_instruction}

{cultural_context}

PRODUCTO A OPTIMIZAR:
- Título chino: {original_title}
- Descripción: {description}
- Categoría: {original_category}
- Material: {material}
- Color: {color}
- Categoría GPC: {gpc_path}
- Atributos: {attributes}

REGLA DE ORO DE LOS 30 PRIMEROS CARACTERES:
Los pesos de Google Shopping DISMINUYEN de izquierda a derecha. Los usuarios solo leen los primeros 25-30 caracteres en móvil.
Los 30 PRIMEROS caracteres de front_70 DEBEN contener el NOMBRE DE CATEGORÍA PRINCIPAL.
NUNCA empieces con palabras de relleno como "Nuevo", "Hot", "Alta Calidad", "Talla única".

ESTRATEGIA LONG-TAIL DE TRES NIVELES:
Nivel 1 — front_70 (≤66 caracteres LÍMITE DURO):
  Estructura: [Color/Género] + [Material] + [Función principal] + [Categoría] + [1-2 Escenas de uso]
  Las palabras clave de escena DEBEN venir de las ocasiones cultural_context. Escena opcional (有则加): solo si cabe completa; drop scene first si no cabe.
  EJEMPLOS:
    BUENO (62ch): "Mascarilla Ácido Hialurónico Hidratante para Rutina Diaria"
    MALO: "Mascarilla Hidratante Ácido Hialurónico Rutina Diaria Piel" ← sin "para", suena forzado
    MALO: terminar con "para", "por", "del", "y" — NUNCA acabar con preposición o conjunción.
    MALO: escena cortada — la frase de uso debe aparecer COMPLETA.
  REGLAS:
  - front_70 DEBE ser ≤66 caracteres. CUENTA.
  - DEBE terminar con palabra completa con sentido. NUNCA preposición o conjunción al final.
  - Si la escena no cabe entera, ELIMINA primero la escena — CONSERVA categoría y función.
    Prioridad: Categoría > Función > Color/Material > escena opcional.
  - Solo atributos reales de ESTE producto. Cero caracteres chinos. 100% español.
  - Escena SIEMPRE introducida por preposición: "para [Escena]". Ayuda al parser de Google.
Nivel 2 — rest: SOLO especificaciones (talla, lote). Sin sinónimos de categoría.
Nivel 3 — description_snippet (PIRÁMIDE 3 NIVELES):
  Escribe una descripción estructurada en 3 párrafos en este FORMATO:
  Párrafo 1 (1 frase): Punto de dolor principal o escena de uso.
  Párrafo 2 (puntos clave): 3-4 argumentos de venta. Format: "• Material Premium: ...\n• Diseño Ergonómico: ...\n• Cuidado Fácil: ..."
  Párrafo 3 (conformidad): Consejos de talla, mención "Nuevo".
  Español natural. Máx 300 caracteres en total.
Nivel 4 — ai_tags: SIEMPRE 3-5 labels EN ESPAÑOL (NO en inglés!). Separados por espacios, NUNCA guiones/subrayados. Ejemplo: ["mascarilla facial", "acido hialuronico", "rutina diaria"]. Assets SEO.

PALABRAS PROHIBIDAS: Mejor, N.º1, #1, Top, 100%, Envío gratis, Barato, Descuento, Garantizado, Perfecto, Increíble, Talla única, Alta Calidad. Devuelve SOLO JSON."""

_PROMPT_IT = """Sei uno specialista italiano di Google Shopping.

{formula_instruction}

{cultural_context}

PRODOTTO DA OTTIMIZARE:
- Titolo cinese: {original_title}
- Descrizione: {description}
- Categoria: {original_category}
- Materiale: {material}
- Colore: {color}
- Categoria GPC: {gpc_path}
- Attributi: {attributes}

REGOLA D'ORO DEI 30 CARATTERI:
I pesi di Google Shopping DIMINUISCONO da sinistra a destra. Gli utenti leggono solo i primi 25-30 caratteri su mobile.
I primi 30 CARATTERI di front_70 DEVONO contenere il NOME DELLA CATEGORIA PRINCIPALE.
Non iniziare MAI con parole riempitive come "Nuovo", "Hot", "Alta Qualità", "Taglia Unica".

STRATEGIA LONG-TAIL A TRE LIVELLI:
Livello 1 — front_70 (≤66 caratteri LIMITE RIGIDO):
  Struttura: [Colore/Genere] + [Materiale] + [Funzione principale] + [Categoria] + [1-2 Scene d'uso]
  Le parole chiave di scena DEVONO provenire dalle occasioni cultural_context. Scena opzionale (有则加): solo se entra intera; drop scene first se non entra.
  ESEMPI:
    BUONO (65ch): "Donna Rosa Mesh Scarpe Running Ammortizzate per Palestra"
    CATTIVO (58ch): "Donna Rosa Mesh Scarpe Running Ammortizzate Traspiranti Palestra" ← "Palestra" senza preposizione
    CATTIVO: finire con "per", "di", "del", "e", "a", "da" — MAI terminare con preposizione.
    CATTIVO: scena tagliata a metà — la frase d'uso deve apparire COMPLETA.
  REGOLE:
  - front_70 DEVE essere ≤66 caratteri. CONTA.
  - DEVE finire con una parola di senso compiuto. MAI preposizione o congiunzione finale.
  - Se la scena non ci sta per intero, ELIMINA prima la scena — CONSERVA categoria e funzione.
    Priorità: Categoria > Funzione > Colore/Materiale > scena opzionale.
  - Solo attributi reali di QUESTO prodotto. Zero caratteri cinesi. 100% italiano.
  - Scena SEMPRE introdotta da preposizione: "per [Scena]". Aiuta il parser di Google.
Livello 2 — rest: SOLO specifiche (taglia, confezione). Nessun sinonimo di categoria.
Livello 3 — description_snippet (PIRAMIDE 3 LIVELLI):
  Scrivi una descrizione strutturata in 3 paragrafi in questo FORMATO:
  Paragrafo 1 (1 frase): Punto di dolore principale o scena d'uso.
  Paragrafo 2 (punti chiave): 3-4 argomenti di vendita. Format: "• Materiale Premium: ...\n• Design Ergonomico: ...\n• Cura Facile: ..."
  Paragrafo 3 (conformità): Consigli taglia, menzione "Nuovo".
  Italiano naturale. Max 300 caratteri in totale.
Livello 4 — ai_tags: SEMPRE 3-5 label IN ITALIANO (NON in inglese!). Separati da spazi, MAI trattini/sottolineature. Esempio: ["scarpe running", "palestra", "ammortizzate"]. Asset SEO.

PAROLE VIETATE: Migliore, N.1, #1, Top, 100%, Spedizione gratuita, Economico, Sconto, Garantito, Perfetto, Incredibile, Taglia Unica, Alta Qualità. Restituisci SOLO JSON."""


# ─────────────────────────────────────────────
# JSON 防火墙
# ─────────────────────────────────────────────

def _extract_json_from_llm_output(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    for pat in [r'```json\s*([\s\S]*?)```', r'```\s*([\s\S]*?)```']:
        m = re.search(pat, raw)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                continue
    m = re.search(r'\{[\s\S]*\}', raw)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"JSON firewall failed. Raw output (first 200 chars): {raw[:200]}")


# ─────────────────────────────────────────────
# 违禁词清洗（多国语）
# ─────────────────────────────────────────────

_BANNED_MAP_GLOBAL = {
    "Best": "Top", "best": "top", "No.1": "", "No. 1": "", "#1": "",
    "Top-1": "", "Top 1": "", "Guaranteed": "Trusted", "guaranteed": "trusted",
    "Perfect": "Great", "perfect": "great", "Amazing": "Great", "amazing": "great",
    "Incredible": "Great", "incredible": "great", "Unbeatable": "Competitive",
    "unbeatable": "competitive", "Cheapest": "Affordable", "cheapest": "affordable",
    "100%": "", "Free Shipping": "", "free shipping": "", "Discount": "",
    "discount": "", "Cheap": "Affordable", "cheap": "affordable",
    # 德语
    "Beste": "Hochwertige", "beste": "hochwertige", "Nr.1": "", "Nr. 1": "",
    "Garantiert": "Geprüft", "garantiert": "geprüft", "Perfekt": "Ideal",
    "perfekt": "ideal", "Unglaublich": "Beeindruckend", "unglaublich": "beeindruckend",
    "Günstig": "Preiswert", "günstig": "preiswert", "Kostenloser Versand": "",
    # 法语
    "Meilleur": "Excellent", "meilleur": "excellent", "N°1": "", "N° 1": "",
    "Garanti": "Vérifié", "garanti": "vérifié", "Parfait": "Idéal", "parfait": "idéal",
    "Incroyable": "Remarquable", "incroyable": "remarquable", "Pas cher": "Abordable",
    "Livraison gratuite": "", "Remise": "",
    # 西语
    "Mejor": "Excelente", "mejor": "excelente", "N.º1": "", "Garantizado": "Verificado",
    "garantizado": "verificado", "Perfecto": "Ideal", "perfecto": "ideal",
    "Increíble": "Destacable", "increíble": "destacable", "Barato": "Económico",
    "barato": "económico", "Envío gratis": "", "Descuento": "",
    # 意语
    "Migliore": "Eccellente", "migliore": "eccellente", "N.1": "",
    "Garantito": "Verificato", "garantito": "verificato",
    "Perfetto": "Ideale", "perfetto": "ideale", "Incredibile": "Notevole",
    "incredibile": "notevole", "Economico": "Conveniente", "economico": "conveniente",
    "Spedizione gratuita": "", "Sconto": "",
}


_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
_TRAILING_PREPOSITIONS = {
    # 英文：介词尾绝不合法
    "for", "to", "in", "on", "at", "with", "by", "from", "of",
    "and", "or", "the", "a", "an", "as", "but", "nor",
    # 德语
    "für", "zur", "zum", "mit", "und", "oder", "bei", "von", "auf",
    "im", "am", "ins", "vom", "ans", "aufs", "durch", "gegen",
    # 法语
    "pour", "avec", "dans", "sur", "sous", "sans", "chez", "et", "ou",
    "de", "du", "des", "au", "aux",
    # 西班牙语
    "para", "con", "por", "sin", "entre", "sobre", "y", "o",
    "del", "al",
    # 意大利语
    "per", "di", "con", "su", "tra", "fra", "e", "ed",
    "del", "della", "nel", "nella", "dei", "degli", "delle",
    "al", "ai", "dal", "da", "in", "a",
}


def _has_chinese(text: str) -> bool:
    """检测字符串是否包含中文汉字"""
    return bool(_CHINESE_RE.search(text))


def _safe_front70(raw: str, max_chars: int = 66):
    """词边界安全截断：如果 ≤max_chars 直接返回；否则回溯到最后一个空格处截断。
    
    返回 None 表示无法安全截断（前 max_chars 内无空格），调用方应触发重试。
    """
    raw = raw.strip()
    if len(raw) <= max_chars:
        return raw
    # 回溯到最后一个空格，截断到完整单词
    clip = raw[:max_chars]
    last_space = clip.rfind(" ")
    if last_space > 10:  # 至少前面有 10 个字符的实词内容
        return clip[:last_space].strip()
    # 极端情况：前 max_chars 内没有空格，返回 None 触发重试
    return None


def _validate_and_clean_output(parsed: dict, original_title: str, country: str = "") -> OptimizedTitleOutput:
    front_70 = parsed.get("front_70", original_title[:70])
    rest = parsed.get("rest", "")
    ai_tags = parsed.get("ai_tags", [])
    description_snippet = parsed.get("description_snippet", "")

    # ── 第一层：违禁词清洗 ──
    for banned, replacement in _BANNED_MAP_GLOBAL.items():
        front_70 = front_70.replace(banned, replacement)
        rest = rest.replace(banned, replacement)
        description_snippet = description_snippet.replace(banned, replacement)

    front_70 = re.sub(r'\s+', ' ', front_70).strip()
    rest = re.sub(r'\s+', ' ', rest).strip()
    description_snippet = re.sub(r'\s+', ' ', description_snippet).strip()

    # ── 第 1.5 层：填充词切除（浪费标题空间的废话词）──
    _FILLER_PATTERNS = [
        r'(?i)\bone\s*size\b', r'(?i)\bfree\s*size\b',
        r'(?i)\bfree\s*shipping\b', r'(?i)\bhigh\s*quality\b',
        r'(?i)\bbest\s*quality\b', r'(?i)\btop\s*quality\b',
        r'(?i)\bnew\s*arrival[s]?\b', r'(?i)\bhot\s*sale\b',
        r'(?i)\b100%\b', r'(?i)\bpremium\s*quality\b',
        # 德语填充词
        r'(?i)\bEinheitsgröße\b', r'(?i)\bHohe Qualität\b',
        r'(?i)\bKostenloser Versand\b',
        # 法语填充词
        r'(?i)\bTaille unique\b', r'(?i)\bHaute Qualité\b',
        r'(?i)\bLivraison gratuite\b',
        # 西语填充词
        r'(?i)\bTalla única\b', r'(?i)\bAlta Calidad\b',
        r'(?i)\bEnvío gratis\b',
        # 意语填充词
        r'(?i)\bTaglia Unica\b', r'(?i)\bAlta Qualità\b',
        r'(?i)\bSpedizione gratuita\b',
    ]
    for pattern in _FILLER_PATTERNS:
        front_70 = re.sub(pattern, '', front_70)
        rest = re.sub(pattern, '', rest)
    front_70 = re.sub(r'\s+', ' ', front_70).strip()
    rest = re.sub(r'\s+', ' ', rest).strip()

    # ── 第二层：中文泄漏检测（三层分级）──
    market_is_cn = country.upper() in ("CN", "HK", "TW", "SG", "")

    if not market_is_cn:
        # Tier A — 核心字段有中文 → 必须重试
        if _has_chinese(front_70):
            raise ValueError(f"front_70 contains Chinese characters (forbidden for market {country}): '{front_70[:60]}'")
        if any(_has_chinese(t) for t in (ai_tags or [])):
            raise ValueError(f"ai_tags contains Chinese characters (forbidden for market {country}): {[t[:30] for t in ai_tags if _has_chinese(t)]}")

        # Tier B — 次要字段有中文 → 零 token 静默删除中文片段
        if _has_chinese(rest):
            rest = _CHINESE_RE.sub("", rest)
            rest = re.sub(r"\s+", " ", rest).strip().rstrip(",")
        if _has_chinese(description_snippet):
            description_snippet = _CHINESE_RE.sub("", description_snippet)
            description_snippet = re.sub(r"\s+", " ", description_snippet).strip()

    # ── 第三层：词边界安全截断（不允许单词中途断裂）──
    safe = _safe_front70(front_70, max_chars=66)
    if safe is None:
        raise ValueError(f"front_70 cannot be safely truncated at word boundary: '{front_70[:80]}'")
    was_truncated = (len(front_70) > 66)
    front_70 = safe

    # ── 第四层：尾词不能是介词（截断后可能暴露介词尾）──
    words = front_70.split()
    while words and words[-1].lower().strip(",.!?;:'\"()[]{}") in _TRAILING_PREPOSITIONS:
        words.pop()
    if not words:
        raise ValueError(f"front_70 reduced to empty after stripping prepositions")
    front_70 = " ".join(words)

    # ── 第五层：截断标记 — 若 LLM 产出 >66 被截断，触发重试用更短提示 ──
    if was_truncated:
        raise ValueError(f"scene_truncated: LLM produced >66 chars, scene words may be lost. Retry with tighter budget.")

    if len(description_snippet) > 300:
        description_snippet = description_snippet[:300].rsplit(" ", 1)[0]

    # ── Tag 格式清洗 ──
    _TAG_NORMALIZE_RE = re.compile(r"[_\-]+")
    _TAG_BANNED_MAP = {"cremation gift": "cadeau cremaillere", "cremation": "cremaillere"}
    _TAG_BANNED_SORTED = sorted(_TAG_BANNED_MAP.items(), key=lambda x: -len(x[0]))
    normalized = []
    for t in (ai_tags or []):
        t = t.strip().lower()
        if not t:
            continue
        # 1) 黑名单拦截（长词优先）
        for bad, good in _TAG_BANNED_SORTED:
            if bad in t:
                t = t.replace(bad, good)
        # 2) 下划线 / 连字符 → 空格
        t = _TAG_NORMALIZE_RE.sub(" ", t)
        # 3) 去重空格
        t = re.sub(r"\s+", " ", t).strip()
        if t and t not in normalized:
            normalized.append(t)
    ai_tags = normalized[:5]

    # ── 标题内斜杠清理 ──
    front_70 = re.sub(r"(?<=\w)/(?=\w)", " & ", front_70)
    rest = re.sub(r"(?<=\w)/(?=\w)", " & ", rest)

    return OptimizedTitleOutput(
        front_70=front_70, rest=rest, ai_tags=ai_tags, description_snippet=description_snippet,
    )


# ─────────────────────────────────────────────
# LLM 调用
# ─────────────────────────────────────────────

def _llm_generate_structured(client: OpenAI, prompt: str) -> dict:
    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a JSON-only output machine. Output ONLY valid JSON. No markdown, no explanations."},
                    {"role": "user", "content": prompt},
                ],
                temperature=LLM_TEMPERATURE,
                max_tokens=600,
            )
            raw = response.choices[0].message.content.strip()
            return _extract_json_from_llm_output(raw)
        except (json.JSONDecodeError, ValueError) as e:
            if attempt < LLM_MAX_RETRIES:
                delay = LLM_RETRY_DELAY_SECONDS[min(attempt, len(LLM_RETRY_DELAY_SECONDS) - 1)]
                print(f"  ⚠ JSON parse failed (attempt {attempt+1}): {str(e)[:60]}，retry in {delay}s...")
                prompt += "\n\n[Previous output was invalid JSON. Output ONLY pure JSON, no markdown wrapping.]"
                time.sleep(delay)
            else:
                raise
    raise RuntimeError("LLM structured output all retries failed")


# ─────────────────────────────────────────────
# 主优化函数（多国语版本）
# ─────────────────────────────────────────────

def optimize(
    original_title: str,
    description: str = "",
    original_category: str = "",
    material: str = "",
    color: str = "",
    attributes: dict = None,
    gpc_path: str = "",
    country: str = None,
    target_season: str = None,
) -> dict:
    """对单个国家生成优化标题

    Returns:
        {
            "optimized_title": "完整标题（front_70 + rest）",
            "front_70": "...",
            "rest": "...",
            "char_count": 128,
            "ai_tags": ["wireless", "earbuds"],
            "description_snippet": "AEO semantic description...",
            "country": "US",
            "model": "qwen-plus",
        }
    """
    if country is None:
        country = DEFAULT_COUNTRY

    client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)

    cultural_context = get_cultural_context(
        country=country, cn_category=original_category,
        gpc_path=gpc_path, season=target_season or season_for_date(),
    )
    formula_instruction = _get_formula_instruction(original_category, gpc_path)
    attr_str = ", ".join(f"{k}: {v}" for k, v in (attributes or {}).items()) if attributes else "N/A"

    prompt = _build_prompt(
        country=country, formula_instruction=formula_instruction,
        cultural_context=f"LOCAL CULTURAL & SEO CONTEXT:\n{cultural_context}" if cultural_context else "",
        original_title=original_title, description=description or "N/A",
        original_category=original_category or "N/A",
        material=material or "N/A", color=color or "N/A",
        gpc_path=gpc_path or "N/A", attributes=attr_str,
    )

    last_err_hint = ""
    for eval_attempt in range(LLM_MAX_RETRIES + 1):
        try:
            if eval_attempt > 0:
                retry_hint = last_err_hint if last_err_hint else "Previous output was invalid."
                prompt = f"{prompt}\n\n[RETRY — {retry_hint} Output ONLY valid JSON.]"

            raw_parsed = _llm_generate_structured(client, prompt)
            output = _validate_and_clean_output(raw_parsed, original_title, country)
            last_err_hint = ""  # success → clear

            full_title = output.front_70.strip()
            if output.rest.strip():
                full_title = f"{full_title} {output.rest.strip()}"
            if len(full_title) > TITLE_MAX_LENGTH:
                full_title = full_title[:TITLE_MAX_LENGTH].rsplit(" ", 1)[0]

            return {
                "optimized_title": full_title,
                "front_70": output.front_70,
                "rest": output.rest,
                "char_count": len(full_title),
                "ai_tags": output.ai_tags,
                "description_snippet": output.description_snippet,
                "country": country.upper(),
                "model": LLM_MODEL,
            }

        except Exception as e:
            if eval_attempt >= LLM_MAX_RETRIES:
                break
            err_msg = str(e)
            if "Chinese characters" in err_msg:
                last_err_hint = f"STRICTLY NO Chinese characters in front_70. Translate EVERY word to native {country.upper()} language."
                prompt = _build_prompt(  # rebuild with reinforced hint
                    country=country, formula_instruction=formula_instruction,
                    cultural_context=f"LOCAL CULTURAL & SEO CONTEXT:\n{cultural_context}\n\nCRITICAL REMINDER: Output 100% native {country.upper()} language. ZERO Chinese characters allowed. Category: {original_category} ONLY — do NOT borrow features from other categories.",
                    original_title=original_title, description=description or "N/A",
                    original_category=original_category or "N/A",
                    material=material or "N/A", color=color or "N/A",
                    gpc_path=gpc_path or "N/A", attributes=attr_str,
                )
            elif "scene_truncated" in err_msg:
                last_err_hint = "CRITICAL: Your front_70 was TOO LONG. Shrink to ≤60 chars. Drop SCENE first if present, then color/material — KEEP CORE CATEGORY + key function. NEVER end on a preposition."
                prompt = _build_prompt(  # rebuild with tighter budget
                    country=country, formula_instruction=formula_instruction,
                    cultural_context=f"LOCAL CULTURAL & SEO CONTEXT:\n{cultural_context}\n\nRETRY RULE: front_70 budget is now ≤60 chars. Scene words MUST fit. Drop filler words.",
                    original_title=original_title, description=description or "N/A",
                    original_category=original_category or "N/A",
                    material=material or "N/A", color=color or "N/A",
                    gpc_path=gpc_path or "N/A", attributes=attr_str,
                )
            else:
                last_err_hint = "Previous output was invalid JSON or failed validation. Output ONLY pure JSON with no markdown wrapping."
            time.sleep(1)

    # 兜底 — 用完整违禁词清洗 + 安全词边界截断
    fallback_title = original_title[:TITLE_MAX_LENGTH]
    # #3: 对齐 _BANNED_MAP_GLOBAL，而非仅 7 个前缀
    for banned, replacement in _BANNED_MAP_GLOBAL.items():
        fallback_title = fallback_title.replace(banned, replacement)
    fallback_title = re.sub(r'\s+', ' ', fallback_title).strip()

    # #2: 词边界安全截断（与 _validate_and_clean_output 一致）
    front_70 = fallback_title
    if len(front_70) > 70:
        front_70 = front_70[:70].rsplit(" ", 1)[0]

    return {
        "optimized_title": fallback_title,
        "front_70": front_70,
        "rest": "",
        "char_count": len(fallback_title),
        "ai_tags": [],
        "description_snippet": description or "",
        "country": country.upper(),
        "model": "fallback_original",
    }


def optimize_multi_country(
    original_title: str,
    countries: list[str],
    description: str = "",
    original_category: str = "",
    material: str = "",
    color: str = "",
    attributes: dict = None,
    gpc_path: str = "",
    target_season: str = None,
) -> dict:
    """对多个国家批量生成优化标题

    Returns:
        {
            "optimized_titles": {"US": "...", "DE": "...", ...},
            "ai_tags_by_lang": {"US": [...], "DE": [...], ...},
            "description_snippets": {"US": "...", "DE": "...", ...},
            "per_country": [{"country": "US", ...}, ...],
        }
    """
    optimized_titles = {}
    ai_tags_by_lang = {}
    description_snippets = {}
    per_country = []

    for country in countries:
        result = optimize(
            original_title=original_title, description=description,
            original_category=original_category, material=material,
            color=color, attributes=attributes, gpc_path=gpc_path,
            country=country, target_season=target_season,
        )
        optimized_titles[country.upper()] = result["optimized_title"]
        ai_tags_by_lang[country.upper()] = result["ai_tags"]
        description_snippets[country.upper()] = result["description_snippet"]
        per_country.append(result)

    return {
        "optimized_titles": optimized_titles,
        "ai_tags_by_lang": ai_tags_by_lang,
        "description_snippets": description_snippets,
        "per_country": per_country,
    }


# ─────────────────────────────────────────────
# Platform-specific rewrite (Approach-3 layer 3)
# ─────────────────────────────────────────────

_PLATFORM_PREFIX = {
    "google": "",
    "meta": "",
    "tiktok": "",
}


def rewrite_for_platform(
    title: str,
    description: str = "",
    platform: str = "google",
    language: str = "US",
    tags: list = None,
    gpc_path: str = "",
    gpc_code: str = "",
    color: str = "",
    size: str = "",
) -> dict:
    """Rewrite language-skeleton copy into a platform asset.

    Google: keep Shopping front_70 discipline (truncate to 150).
    Meta: commerce-catalog friendly, slightly shorter hook.
    TikTok: short shoppable ecommerce phrasing.

    Pure transform by default (no LLM) so layered pipeline stays billable
    and testable; set ADFEED_PLATFORM_LLM=1 to call the model later.
    """
    from .title_guard import polish_feed_title

    plat = (platform or "google").lower()
    base_title = (title or "").strip()
    base_desc = (description or "").strip()
    tags = list(tags or [])

    # 品类卖点纪律 + 轻量变体差异（完整变体色在 Feed 层再增强）
    base_title = polish_feed_title(
        base_title,
        color=color,
        size=size,
        gpc_path=gpc_path,
        gpc_code=gpc_code,
    )

    if plat == "meta":
        # Commerce: punchy, under ~100 chars preferred
        out_title = base_title
        if len(out_title) > 100:
            out_title = out_title[:97].rstrip() + "..."
        out_desc = base_desc[:5000] if base_desc else base_title
    elif plat == "tiktok":
        # Short shoppable
        out_title = base_title
        if len(out_title) > 80:
            out_title = out_title[:77].rstrip() + "..."
        # Light TikTok cue without spammy emojis
        if out_title and not out_title.lower().startswith("shop"):
            pass
        out_desc = (base_desc or base_title)[:1000]
    else:
        # Google Shopping
        out_title = base_title[:150] if len(base_title) > 150 else base_title
        out_desc = base_desc[:5000] if base_desc else base_title

    return {
        "platform": plat,
        "language": language.upper(),
        "title": out_title,
        "description": out_desc,
        "tags": tags,
    }


# 向后兼容
optimize_title = optimize
