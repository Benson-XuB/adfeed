"""通用 1688 供应商数据导入器 — 零配置，靠数值分布自动识别列角色。

支持三种输入模式：
    Excel:    python3 _ingest_universal.py /path/to/报价表.xlsx
    CSV:      python3 _ingest_universal.py /path/to/导出.csv
    纯标题:   python3 _ingest_universal.py /path/to/产品列表.txt

参数：
    --sample N      采样条数 (default: 35, 0=全部)
    --countries US,DE,FR  目标国家 (default: US,DE,FR,ES,IT)
    --output PATH   输出 CSV 路径 (default: _test_samples.csv)
    --seed N        随机种子 (default: 42)
"""
import os, sys, csv, re, random, zipfile, xml.etree.ElementTree as ET, io
from pathlib import Path
from typing import Optional
from collections import Counter

OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_samples.csv")
DEFAULT_COUNTRIES = ["US", "DE", "FR", "ES", "IT"]
DEFAULT_SAMPLE = 35

# ═══════════════════════════════════════════════════
# 列值检测器 — 不依赖列名，只看数值分布
# ═══════════════════════════════════════════════════

_COLOR_KEYWORDS = [
    "黑色", "白色", "红色", "蓝色", "绿色", "黄色", "粉色", "紫色", "灰色", "棕色",
    "橙色", "米色", "卡其", "银色", "金色", "透明", "杏色", "肤色", "咖啡",
    "黑", "白", "红", "蓝", "绿", "黄", "粉", "紫", "灰", "棕",
    "black", "white", "red", "blue", "green", "yellow", "pink", "grey", "gray",
    "brown", "silver", "gold", "navy", "beige", "clear",
    "星耀", "豆沙", "树莓", "海岩", "香鲸", "芭比", "可可", "蜜桃", "象牙", "阳光",
    "酱茄", "蜜柚", "灰湖", "粉钻", "冰融", "梅浆", "昌荣", "紫西", "蒸馏",
    "schwarz", "weiß", "rot", "blau", "grün", "giallo", "negro", "blanco",
]

_MATERIAL_KEYWORDS = [
    "聚酯纤维", "氨纶", "棉", "涤纶", "锦纶", "腈纶", "羊毛", "真丝", "亚麻",
    "蕾丝", "雪纺", "牛津布", "帆布", "牛仔", "皮革", "PU", "PVC",
    "不锈钢", "铝合金", "塑料", "ABS", "PP", "PE", "TPE", "TPU", "PET",
    "硅胶", "橡胶", "亚克力", "玻璃", "陶瓷", "木质", "实木", "竹", "藤",
    "锌合金", "钛钢", "铜", "铁", "金属", "锌", "镍", "银", "金",
    "无纺布", "短毛绒", "珊瑚绒", "法兰绒", "水晶绒",
    "不锈钢", "316", "304", "201", "锌合金", "ABS", "PC",
    "polyester", "cotton", "leather", "nylon", "spandex", "silk", "wool",
    "stainless", "aluminum", "plastic", "silicone", "acrylic", "ceramic",
    "bamboo", "wood", "canvas", "oxford", "mesh", "steel", "metal",
    "钢管", "烤漆", "镀锌", "粉末涂", "环氧", "电镀", "喷漆",
    "18K", "925", "纯银", "镀金", "包金",
]

_SIZE_PATTERN = re.compile(
    r"^[\d\s\.\,x×\*\-–~]+(cm|mm|m|inch|\"|g|kg|ml|L|l)\s*$",  # 纯尺寸值
    re.IGNORECASE,
)

_PRICE_PATTERN = re.compile(r"^[￥¥]?\d+\.?\d{0,2}$")


_NON_TITLE_PATTERNS = [
    re.compile(r"^(PID|SKU|FX-|ERP-)\d+$", re.IGNORECASE),
    re.compile(r".*\.(com|jpg|png|jpeg|gif|bmp).*$"),
    re.compile(r"^https?://"),
]

_KNOWN_CATEGORIES = {
    "美容个护", "珠宝饰品", "母婴玩具", "宠物用品", "厨房餐饮", "办公文具",
    "汽车用品", "3C数码", "服装鞋帽", "箱包", "运动户外", "家居生活",
    "美容", "饰品", "母婴", "宠物", "厨房", "办公",
}


def _likely_title(values: list[str]) -> float:
    """评分：标题列特征 = 长中文文本，非 URL/PID/SKU/品类名"""
    if not values:
        return 0
    score = 0
    for v in values:
        if not v or v == "nan":
            continue
        # 强惩罚
        if any(pat.match(v) for pat in _NON_TITLE_PATTERNS):
            score -= 5
            continue
        if v in _KNOWN_CATEGORIES or len(v) <= 6 and v in _KNOWN_CATEGORIES:
            score -= 3
            continue
        # 正向评分
        if len(v) >= 8 and re.search(r"[\u4e00-\u9fff]", v):
            score += 3  # 长中文 → 强标题
        elif len(v) >= 4 and re.search(r"[\u4e00-\u9fff]", v):
            score += 2
        elif len(v) >= 10:
            score += 1
        if _PRICE_PATTERN.match(v.strip()):
            score -= 5
    return score / max(len(values), 1)


def _likely_material(values: list[str]) -> float:
    if not values:
        return 0
    hits = 0
    for v in values:
        for kw in _MATERIAL_KEYWORDS:
            if kw in v:
                hits += 1
                break
    return hits / max(len(values), 1)


def _likely_color(values: list[str]) -> float:
    if not values:
        return 0
    # 取每行的第一段颜色（去换行）
    hits = 0
    for v in values:
        first = v.split("\n")[0].split("|")[0].strip()
        for kw in _COLOR_KEYWORDS:
            if kw in first:
                hits += 1
                break
    return hits / max(len(values), 1)


def _likely_size(values: list[str]) -> float:
    if not values:
        return 0
    hits = 0
    for v in values:
        if _SIZE_PATTERN.search(v):
            hits += 1
    return hits / max(len(values), 1)


def _likely_price(values: list[str]) -> float:
    if not values:
        return 0
    hits = 0
    for v in values:
        v = v.strip().replace("价格：", "").replace("￥", "").replace("¥", "").replace(",", "")
        if _PRICE_PATTERN.match(v):
            hits += 1
    return hits / max(len(values), 1)


# ═══════════════════════════════════════════════════
# Excel 读取（xlsx + xls 通用）
# ═══════════════════════════════════════════════════

def read_xlsx(path: str) -> list[dict]:
    with zipfile.ZipFile(path) as z:
        sheets = sorted(
            [n for n in z.namelist() if n.endswith(".xml") and "/sheet" in n and "worksheet" in n],
            key=lambda n: int("".join(ch for ch in n.split("/")[-1] if ch.isdigit()) or 0),
        )
        sheet = z.read(sheets[0])
        ss = []
        if "xl/sharedStrings.xml" in z.namelist():
            t = ET.fromstring(z.read("xl/sharedStrings.xml"))
            ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for si in t.findall(".//s:t", ns):
                ss.append(si.text or "")
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(sheet)
    rows = []
    for re_elem in root.findall(".//s:row", ns):
        cells = {}
        for c in re_elem.findall("s:c", ns):
            ref = c.get("r")
            col = "".join(ch for ch in ref if ch.isalpha())
            ct = c.get("t")
            v = c.find("s:v", ns)
            val = (v.text or "") if v is not None else ""
            if ct == "s" and val.isdigit():
                val = ss[int(val)] if int(val) < len(ss) else ""
            elif ct == "inlineStr":
                # openpyxl 生成的 xlsx 用 inlineStr 直接嵌文字
                is_elem = c.find("s:is", ns)
                if is_elem is not None:
                    t_elem = is_elem.find("s:t", ns)
                    val = (t_elem.text or "") if t_elem is not None else ""
            elif ct == "str":
                # 直接字符串
                val = v.text if v is not None else ""
            cells[col] = val
        rows.append(cells)
    return rows


def read_xls(path: str) -> list[dict]:
    import xlrd
    wb = xlrd.open_workbook(path)
    sheet = wb.sheet_by_index(0)
    rows = []
    for ri in range(sheet.nrows):
        cells = {}
        for ci in range(sheet.ncols):
            v = str(sheet.cell_value(ri, ci)).strip()
            if v and v != "nan":
                cells[chr(65 + ci)] = v
        rows.append(cells)
    return rows


# ═══════════════════════════════════════════════════
# 自动列角色识别
# ═══════════════════════════════════════════════════

def classify_columns(rows: list[dict]) -> dict:
    """优先级式列分类：price > size > material > color > title > skip（Excel 入口）"""
    if len(rows) < 2:
        return {}
    all_cols = set()
    for r in rows[1:]:
        all_cols.update(r.keys())
    col_values = {}
    for col in sorted(all_cols):
        vals = [rows[ri].get(col, "") for ri in range(1, len(rows)) if rows[ri].get(col, "")]
        col_values[col] = vals
    return classify_columns_from_values(col_values)


# ═══════════════════════════════════════════════════
# CSV 读取（含自动列识别）
# ═══════════════════════════════════════════════════

def _sniff_delimiter(first_chunk: str) -> str:
    """自动检测 CSV 分隔符"""
    try:
        dialect = csv.Sniffer().sniff(first_chunk)
        return dialect.delimiter
    except csv.Error:
        pass
    # 按常见分隔符统计，取出现最多的
    best, best_count = ",", 0
    for delim in [",", "\t", "|", ";"]:
        cnt = first_chunk.count(delim)
        if cnt > best_count:
            best, best_count = delim, cnt
    return best


def read_csv(path: str) -> tuple[list[dict], dict]:
    """读取 CSV 文件，自动识别列角色。

    Returns (rows, roles) — rows 是 list[dict{col: value}]（含表头），
    roles 是 {col_letter: role}（A=第0列, B=第1列...）
    """
    import codecs
    with codecs.open(path, "r", encoding="utf-8-sig") as f:
        first_chunk = f.read(4096)
        f.seek(0)
        delimiter = _sniff_delimiter(first_chunk)
        reader = csv.reader(f, delimiter=delimiter)
        raw_rows = list(reader)

    if not raw_rows:
        return [], {}

    header = [h.strip() for h in raw_rows[0]]
    data_rows = raw_rows[1:]

    # 转成 {col_letter: value} 格式
    rows_out = []
    col_map = {i: chr(65 + i) for i in range(len(header))}  # 0→A, 1→B...

    for data_row in data_rows:
        if not data_row or all(not c or not c.strip() for c in data_row):
            continue
        row_dict = {}
        for i, val in enumerate(data_row):
            if i < len(col_map):
                row_dict[col_map[i]] = val.strip()
        if row_dict:
            rows_out.append(row_dict)

    # 构建 roles — 数值分布识别
    all_cols = list(col_map.values())
    col_values = {}
    for col in all_cols:
        vals = [rows_out[ri].get(col, "") for ri in range(len(rows_out)) if rows_out[ri].get(col, "")]
        col_values[col] = vals

    roles = classify_columns_from_values(col_values)

    print(f"引擎: CSV ({len(header)}列, delimiter='{delimiter}')")
    print(f"识别: title={[c for c,r in roles.items() if r=='title']} "
          f"material={[c for c,r in roles.items() if r=='material']} "
          f"color={[c for c,r in roles.items() if r=='color']} "
          f"size={[c for c,r in roles.items() if r=='size']}")

    return rows_out, roles


def classify_columns_from_values(col_values: dict) -> dict:
    """优先级式列分类（与 Excel 逻辑完全一致，提取为独立函数）"""
    if not col_values:
        return {}

    result = {}
    assigned = set()

    for col, vals in col_values.items():
        if _likely_price(vals) >= 0.3:
            result[col] = "price"
            assigned.add(col)
    for col, vals in col_values.items():
        if col in assigned:
            continue
        if _likely_size(vals) >= 0.25:
            result[col] = "size"
            assigned.add(col)
    for col, vals in col_values.items():
        if col in assigned:
            continue
        # 材质阈值 0.4 — 避免标题含"棉""铝合金"等词误判为材质列
        if _likely_material(vals) >= 0.4:
            result[col] = "material"
            assigned.add(col)
    for col, vals in col_values.items():
        if col in assigned:
            continue
        if _likely_color(vals) >= 0.15:
            result[col] = "color"
            assigned.add(col)
    for col, vals in col_values.items():
        if col in assigned:
            continue
        # 标题：有长中文文本且未被以上角色认领
        if _likely_title(vals) >= 1.0:
            result[col] = "title"
            assigned.add(col)
    for col in col_values:
        if col not in result:
            result[col] = "skip"

    # ── 阶段 7: 材质/标题歧义消歧 — 标题分远超材质分的列优先判定为标题 ──
    for col, vals in col_values.items():
        if result.get(col) == "material":
            title_score = _likely_title(vals)
            material_score = _likely_material(vals)
            # 标题特征远强于材质特征 → 纠偏为标题
            if title_score > 2.0 and title_score > material_score * 3:
                result[col] = "title"

    return result


def read_plaintext(path: str) -> list[str]:
    """读取纯文本文件，每行一个标题"""
    titles = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and len(line) >= 3:
                titles.append(line)
    print(f"引擎: 纯文本 ({len(titles)} 行，每行一个标题)")
    return titles


def read_any(path: str) -> list[dict]:
    """自动识别文件类型并读取为 rows（list[dict]），用于 API 预览"""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in (".xlsx",):
        return read_xlsx(str(p))
    elif ext in (".xls",):
        return read_xls(str(p))
    elif ext in (".csv",):
        return read_csv(str(p), delimiter=",")
    else:
        titles = read_plaintext(str(p))
        return [{chr(65): t} for t in titles]


def _build_samples_from_structured(rows: list[dict], roles: dict,
                                    title_cols: list, material_cols: list,
                                    color_cols: list, size_cols: list,
                                    category_name: str) -> list[dict]:
    """从已分类的 Excel/CSV 行中构建样本"""
    samples = []
    for ri in range(1, len(rows)):
        r = rows[ri]

        title_parts = []
        for c in title_cols:
            v = r.get(c, "").strip()
            # 跳过 URL、短标识符、纯数字列（这些不是真正标题）
            if not v or v.startswith("=DISPIMG") or v == category_name:
                continue
            if "https://" in v or ".jpg" in v or ".png" in v:
                continue
            if re.match(r"^(PID|SKU|FX-|ERP-)\d+$", v):
                continue
            title_parts.append(v)

        if not title_parts and category_name:
            size_part = color_part = ""
            for c in size_cols:
                v = r.get(c, "").strip()
                if v and not v.startswith("=DISPIMG"):
                    size_part = v; break
            for c in color_cols:
                v = r.get(c, "").strip().split("\n")[0]
                if v and not v.startswith("=DISPIMG"):
                    color_part = v; break
            extras = " ".join(filter(None, [size_part, color_part]))
            title_parts = [f"{category_name} {extras}" if extras else category_name]

        if not title_parts and size_cols:
            for c in size_cols:
                v = r.get(c, "").strip()
                if v and re.search(r"\d+", v):
                    title_parts = [f"{category_name} {v}" if category_name else v]
                    break

        title = " ".join(title_parts).strip()
        if not title:
            continue

        material_parts = [r.get(c, "").strip() for c in material_cols
                         if r.get(c, "").strip() and not r.get(c, "").startswith("=DISPIMG")]
        material = " | ".join(material_parts)[:200]

        color_parts = [r.get(c, "").strip().split("\n")[0] for c in color_cols
                      if r.get(c, "").strip() and not r.get(c, "").startswith("=DISPIMG")]
        color = " | ".join(color_parts)[:120]

        desc_parts = [r.get(c, "").strip() for c in size_cols if r.get(c, "").strip()]
        description = " | ".join(desc_parts)[:500] if desc_parts else ""

        samples.append({
            "cn_category": "",
            "original_title": title,
            "material": material,
            "color": color,
            "description": description,
        })
    return samples


def ingest(file_path: str, sample_size: int = None, countries: list = None,
           output: str = None, seed: int = 42):
    """通用导入器 — 支持 Excel (.xlsx/.xls), CSV, 纯文本 (.txt)"""
    if countries is None:
        countries = DEFAULT_COUNTRIES
    if sample_size is None:
        sample_size = DEFAULT_SAMPLE
    if output is None:
        output = OUTPUT_CSV
    random.seed(seed)

    ext = Path(file_path).suffix.lower()

    # ── 模式 1: Excel ──
    if ext in (".xlsx", ".xls"):
        if ext == ".xls":
            rows = read_xls(file_path)
            print("引擎: xlrd (.xls)")
        else:
            rows = read_xlsx(file_path)
            print("引擎: raw XML (.xlsx)")

        total = len(rows)
        print(f"行数: {total} (含表头 {len(rows[0]) if rows else 0} 列)")
        roles = classify_columns(rows)
        category_name = ""
        if rows:
            r0 = rows[0]
            first_col = sorted(r0.keys())[0] if r0 else None
            if first_col:
                v = r0.get(first_col, "").strip()
                if v and len(v) >= 2 and not any(kw in v for kw in
                    ["材质", "颜色", "尺码", "价格", "尺寸", "规格", "图片", "产品", "报价"]):
                    category_name = v
        if category_name and "图片" in category_name:
            category_name = ""

        title_cols = [c for c, r in roles.items() if r == "title"]
        material_cols = [c for c, r in roles.items() if r == "material"]
        color_cols = [c for c, r in roles.items() if r == "color"]
        size_cols = [c for c, r in roles.items() if r == "size"]

        samples = _build_samples_from_structured(rows, roles, title_cols, material_cols,
                                                  color_cols, size_cols, category_name)

    # ── 模式 2: CSV ──
    elif ext == ".csv":
        rows, roles = read_csv(file_path)
        title_cols = [c for c, r in roles.items() if r == "title"]
        material_cols = [c for c, r in roles.items() if r == "material"]
        color_cols = [c for c, r in roles.items() if r == "color"]
        size_cols = [c for c, r in roles.items() if r == "size"]
        # CSV 无表头品名
        samples = _build_samples_from_structured(rows, roles, title_cols, material_cols,
                                                  color_cols, size_cols, "")

    # ── 模式 3: 纯文本（每行一个标题）──
    elif ext in (".txt", ""):
        titles = read_plaintext(file_path)
        samples = []
        for t in titles:
            samples.append({
                "cn_category": "",
                "original_title": t.strip(),
                "material": "",
                "color": "",
                "description": "",
            })

    else:
        # 兜底：尝试自动判断
        titles = read_plaintext(file_path)
        samples = []
        for t in titles:
            samples.append({
                "cn_category": "",
                "original_title": t.strip(),
                "material": "",
                "color": "",
                "description": "",
            })

    print(f"有效样本: {len(samples)}")

    # ── 去重 ──
    seen = set()
    unique = []
    for s in samples:
        key = s["original_title"][:80]
        if key not in seen:
            seen.add(key)
            unique.append(s)
    print(f"去重后: {len(unique)}")

    # ── 采样 ──
    if sample_size and len(unique) > sample_size:
        unique = random.sample(unique, sample_size)
        print(f"采样: {len(unique)}")

    # ── 分配国家 ──
    for i, s in enumerate(unique):
        s["country"] = countries[i % len(countries)]

    # ── 写入 ──
    with open(output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["cn_category", "original_title", "material", "color", "description", "country"])
        w.writeheader()
        w.writerows(unique)

    print(f"\n✅ 写入 {output} ({len(unique)} 条)")
    dist = {}
    for s in unique:
        dist[s["country"]] = dist.get(s["country"], 0) + 1
    print(f"   国别: {dict(sorted(dist.items()))}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Universal 1688 supplier data importer")
    parser.add_argument("path", help="File path (.xlsx/.xls/.csv/.txt)")
    parser.add_argument("--sample", type=int, default=None, help="Sample size (0=all)")
    parser.add_argument("--output", default=None, help="Output CSV path")
    parser.add_argument("--countries", default="US,DE,FR,ES,IT", help="Comma-separated countries")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    countries = [c.strip().upper() for c in args.countries.split(",")]
    sample = args.sample if args.sample is not None else DEFAULT_SAMPLE
    ingest(args.path, sample, countries, args.output, args.seed)
