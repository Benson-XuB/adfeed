"""S6a: sensitive lexicon soften + adult=yes (no LLM).

P0 tiers:
  soft  → AUTOFIX rewrite only (no adult)
  adult → optional rewrite + force adult=yes
  block → FATAL (+ optional soften); do not pretend safe to advertise

Lexicon is the operable asset; S6b LLM soften remains out of scope.
"""
from __future__ import annotations

import re
from typing import Any

from .feed_quality import QualityEvent

# Shown when Feed text is softened or adult is forced — merchant should align PDP.
LP_SYNC_HINT = (
    "Feed text was adjusted for compliance — update Shopify title/description to match the landing page."
)


# severity: soft | adult | block (alias: fatal)
# force_adult: only for adult-tier strong signals (not plain underwear)
SENSITIVE_LEXICON: list[dict[str, Any]] = [
    # ── SOFT: knives / weapons wording (sellable outdoor framing) ──
    {
        "id": "SEN01",
        "match": r"tactical\s+combat\s+knife",
        "replace_title": "Outdoor Camping Tool",
        "replace_desc": "outdoor camping tool",
        "severity": "soft",
        "message": "Tactical/self-defense knife wording softened to outdoor camping tool",
    },
    {
        "id": "SEN02",
        "match": r"combat\s+knife",
        "replace_title": "Outdoor Camping Tool",
        "replace_desc": "outdoor camping tool",
        "severity": "soft",
        "message": "combat knife softened to Outdoor Camping Tool",
    },
    {
        "id": "SEN03",
        "match": r"tactical\s+knife",
        "replace_title": "Outdoor Camping Tool",
        "replace_desc": "outdoor camping tool",
        "severity": "soft",
        "message": "tactical knife softened to Outdoor Camping Tool",
    },
    {
        "id": "SEN04",
        "match": r"self[\s-]?defense",
        "replace_title": "outdoor",
        "replace_desc": "outdoor use",
        "severity": "soft",
        "message": "self defense wording softened",
    },
    {
        "id": "SEN05",
        "match": r"战术(?:防身)?刀",
        "replace_title": "Outdoor Camping Tool",
        "replace_desc": "户外野营工具",
        "severity": "soft",
        "message": "Chinese tactical-knife wording softened",
    },
    {
        "id": "SEN06",
        "match": r"防身刀",
        "replace_title": "Outdoor Camping Tool",
        "replace_desc": "户外野营工具",
        "severity": "soft",
        "message": "self-defense knife wording softened to outdoor camping tool",
    },
    {
        "id": "SEN07",
        "match": r"\bkarambit\b",
        "replace_title": "Outdoor Camping Tool",
        "replace_desc": "outdoor camping tool",
        "severity": "soft",
        "message": "karambit wording softened to outdoor tool",
    },
    # ── ADULT: lingerie / sexy — strong signals only (not plain underwear/shapewear) ──
    {
        "id": "SEN10",
        "match": r"\bsexy\b",
        "replace_title": "",
        "replace_desc": "",
        "force_adult": True,
        "severity": "adult",
        "message": "sexy wording softened and marked adult",
    },
    {
        "id": "SEN11",
        "match": r"\blingerie\b",
        "force_adult": True,
        "severity": "adult",
        "message": "lingerie category marked adult=yes",
    },
    {
        "id": "SEN12",
        "match": r"情趣内衣|性感内衣",
        "replace_title": "Women's Underwear Set",
        "replace_desc": "women's underwear",
        "force_adult": True,
        "severity": "adult",
        "message": "adult lingerie wording softened and marked adult",
    },
    {
        "id": "SEN14",
        "match": r"\bintimates?\b",
        "force_adult": True,
        "severity": "adult",
        "gpc_hint": r"underwear|lingerie|intimates?|apparel|clothing",
        "message": "intimates category marked adult=yes",
    },
    {
        "id": "SEN15",
        "match": r"\berotic\b|情趣用品|情趣",
        "replace_title": "Adult Lifestyle",
        "replace_desc": "adult lifestyle product",
        "force_adult": True,
        "severity": "adult",
        "message": "erotic wording softened and marked adult",
    },
    {
        "id": "SEN16",
        "match": r"\bboudoir\b",
        "force_adult": True,
        "severity": "adult",
        "message": "boudoir wording marked adult=yes",
    },
    # ── SOFT: massage gun / 筋膜枪 dirty translations (no adult by default) ──
    {
        "id": "SEN20",
        "match": r"intimate\s+massage\s+gun",
        "replace_title": "Deep Tissue Muscle Massage Gun",
        "replace_desc": "deep tissue muscle recovery massage gun",
        "severity": "soft",
        "message": "massage-gun sensitive wording softened to muscle-recovery semantics",
    },
    {
        "id": "SEN21",
        "match": r"bedroom\s+pleasure",
        "replace_title": "muscle recovery",
        "replace_desc": "muscle recovery",
        "severity": "soft",
        "message": "adult-oriented massage description softened",
    },
    {
        "id": "SEN22",
        "match": r"\badult\s+massage\s+gun\b",
        "replace_title": "Deep Tissue Massage Gun",
        "replace_desc": "deep tissue massage gun",
        "severity": "soft",
        "message": "adult massage gun wording softened",
    },
    {
        "id": "SEN23",
        "match": r"for\s+couples",
        "replace_title": "for athletes",
        "replace_desc": "for athletes",
        "gpc_hint": r"massage|percussion|recovery",
        "title_hint": r"massage\s+gun",
        "severity": "soft",
        "message": "massage-gun couples wording softened",
    },
    {
        "id": "SEN24",
        "match": r"情侣",
        "replace_title": "运动员",
        "replace_desc": "运动恢复",
        "title_hint": r"筋膜枪|按摩枪|massage\s+gun",
        "severity": "soft",
        "message": "massage-gun couples wording softened",
    },
    {
        "id": "SEN25",
        "match": r"bedroom\s+massage\s+gun|情侣筋膜枪|情趣按摩",
        "replace_title": "Deep Tissue Muscle Massage Gun",
        "replace_desc": "deep tissue muscle recovery massage gun",
        "severity": "soft",
        "message": "adult-oriented massage-gun dirty translation softened",
    },
    # ── BLOCK: likely prohibited — FATAL, do not treat as green-path ──
    {
        "id": "SEN90",
        "match": r"\bswitchblade\b",
        "replace_title": "Outdoor Tool",
        "replace_desc": "outdoor tool",
        "severity": "block",
        "message": "Likely prohibited knife (switchblade): softened and flagged high risk — do not advertise on GMC",
    },
    {
        "id": "SEN91",
        "match": r"ballistic\s+knife|弹射刀|弹簧刀",
        "replace_title": "Outdoor Tool",
        "replace_desc": "outdoor tool",
        "severity": "block",
        "message": "Likely prohibited knife wording: softened and flagged high risk — do not advertise on GMC",
    },
    {
        "id": "SEN92",
        "match": r"butterfly\s+knife|\bbalisong\b",
        "replace_title": "Outdoor Tool",
        "replace_desc": "outdoor tool",
        "severity": "block",
        "message": "Likely prohibited knife (butterfly/balisong) — do not advertise on GMC",
    },
    {
        "id": "SEN93",
        "match": r"管制刀具|弹簧跳刀",
        "replace_title": "Outdoor Tool",
        "replace_desc": "户外工具",
        "severity": "block",
        "message": "Restricted knife wording: flagged high risk — do not advertise on GMC",
    },
]


def _sku(row: dict) -> str:
    return str(row.get("SKU") or row.get("sku") or row.get("id") or "")


def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


def _normalize_severity(raw: str) -> str:
    s = (raw or "soft").strip().lower()
    if s in ("fatal", "block", "prohibit"):
        return "block"
    if s == "adult":
        return "adult"
    return "soft"


def _event_level(severity: str) -> str:
    if severity == "block":
        return "FATAL"
    return "AUTOFIX"


def _with_lp_hint(suggestion: str = "") -> str:
    base = (suggestion or "").strip()
    if LP_SYNC_HINT in base:
        return base
    if not base:
        return LP_SYNC_HINT
    return f"{base} {LP_SYNC_HINT}"


def _entry_applies(entry: dict, text: str, gpc_path: str, title: str) -> bool:
    """Return True if match hits and optional gpc/title hints pass."""
    if not _compile(entry["match"]).search(text):
        return False
    gpc_hint = entry.get("gpc_hint")
    if gpc_hint and not _compile(gpc_hint).search(gpc_path):
        return False
    title_hint = entry.get("title_hint")
    if title_hint and not (
        _compile(title_hint).search(title) or _compile(title_hint).search(text)
    ):
        return False
    return True


def _replace_field(value: str, pattern: str, replacement: str | None) -> tuple[str, bool]:
    if replacement is None:
        return value, False
    rx = _compile(pattern)
    if not rx.search(value):
        return value, False
    if replacement == "":
        new = rx.sub(" ", value)
        new = re.sub(r"\s{2,}", " ", new).strip()
        new = re.sub(r"\s+,", ",", new)
        return new, new != value
    new = rx.sub(replacement, value)
    return new, new != value


def apply_sensitive_compliance(row: dict) -> list[QualityEvent]:
    """Mutate title/desc (+ adult) from lexicon; return QualityEvents."""
    events: list[QualityEvent] = []
    sku = _sku(row)

    title_key = "优化后标题" if "优化后标题" in row else ("标题" if "标题" in row else "title")
    desc_key = "描述" if "描述" in row else "description"
    title = str(row.get(title_key) or "")
    desc = str(row.get(desc_key) or "")
    gpc_path = str(row.get("GPC路径") or row.get("gpc_path") or "")

    force_adult = False
    adult_message = "Injected adult=yes for sensitive category (proactive compliance)"

    for entry in SENSITIVE_LEXICON:
        blob = f"{title} {desc}"
        if not _entry_applies(entry, blob, gpc_path, title):
            continue

        severity = _normalize_severity(str(entry.get("severity", "soft")))
        rule_id = entry["id"]
        pattern = entry["match"]

        before_title, before_desc = title, desc
        changed = False

        if "replace_title" in entry:
            title, c = _replace_field(title, pattern, entry["replace_title"])
            changed = changed or c
        if "replace_desc" in entry:
            desc, c = _replace_field(desc, pattern, entry["replace_desc"])
            changed = changed or c

        if entry.get("force_adult") and severity == "adult":
            force_adult = True
            adult_message = entry.get("message") or adult_message

        if changed:
            events.append(QualityEvent(
                level=_event_level(severity),
                rule_id=rule_id,
                field="g:title" if before_title != title else "g:description",
                sku=sku,
                message=entry.get("message") or f"Sensitive term softened ({rule_id})",
                suggestion=_with_lp_hint(""),
                before=before_title if before_title != title else before_desc,
                after=title if before_title != title else desc,
            ))
        elif entry.get("force_adult") and severity == "adult":
            events.append(QualityEvent(
                level="WARN",
                rule_id=rule_id,
                field="g:adult",
                sku=sku,
                message=entry.get("message") or f"Adult signal detected ({rule_id})",
                suggestion=_with_lp_hint("Will mark adult=yes"),
                before="",
                after="",
            ))
        elif severity == "block":
            # matched but no text rewrite configured
            events.append(QualityEvent(
                level="FATAL",
                rule_id=rule_id,
                field="g:title",
                sku=sku,
                message=entry.get("message") or f"Sensitive high-risk term ({rule_id})",
                suggestion=_with_lp_hint("Do not advertise on GMC — review product compliance manually"),
                before=before_title,
                after=title,
            ))

    if title != str(row.get(title_key) or ""):
        row[title_key] = title
    if desc != str(row.get(desc_key) or ""):
        row[desc_key] = desc

    if force_adult:
        before_adult = str(row.get("adult") or "no")
        if before_adult.lower() not in ("yes", "true"):
            row["adult"] = "yes"
            events.append(QualityEvent(
                level="AUTOFIX",
                rule_id="AD01",
                field="g:adult",
                sku=sku,
                message=adult_message,
                suggestion=_with_lp_hint("Ads will be adult-only to protect account from misclassification"),
                before=before_adult,
                after="yes",
            ))
        elif not any(e.rule_id == "AD01" for e in events):
            events.append(QualityEvent(
                level="AUTOFIX",
                rule_id="AD01",
                field="g:adult",
                sku=sku,
                message=adult_message,
                suggestion=_with_lp_hint(""),
                before="yes",
                after="yes",
            ))

    return events
