"""CSV-driven regression suite — 支持大规模样本批量测试 + 分国别汇总报告"""
import sys, os, csv, io, time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adfeed.title_optimizer import optimize, _has_chinese
from adfeed.cultural_context import guess_category_from_title

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_samples.csv")

def load_samples(path: str) -> list[dict]:
    """从 CSV 加载样本，跳过注释和空行"""
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    # 跳过注释行
    lines = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    samples = []
    for row in reader:
        samples.append({
            "cn_category": row["cn_category"].strip(),
            "original_title": row["original_title"].strip(),
            "material": row["material"].strip(),
            "color": row["color"].strip(),
            "description": row["description"].strip(),
            "country": row["country"].strip().upper(),
        })
    return samples

def check(r: dict) -> dict:
    """单条结果质量检查"""
    f70 = r["front_70"]
    tags = r["ai_tags"]
    rest = r.get("rest", "")
    desc = r.get("description_snippet", "")

    issues = []

    # 中文泄漏
    if _has_chinese(f70) or any(_has_chinese(t) for t in tags):
        issues.append("CN_LEAK")
    if _has_chinese(rest) or _has_chinese(desc):
        issues.append("CN_DESC")

    # tags 下划线/连字符
    if any("_" in t or "-" in t for t in tags):
        issues.append("TAG_FORMAT")

    # cremation 语义错误
    if any("cremation" in t for t in tags):
        issues.append("CREMATION")

    # 场景介词缺失 (US:for, DE:für, FR:pour, ES:para, IT:per)
    preps = {"US": "for", "DE": "f", "FR": "pour", "ES": "para", "IT": "per"}
    expected = preps.get(r["country"])
    if expected and expected not in f70.lower() and len(tags) > 0:
        issues.append("NO_PREP")

    # 70 字符溢出
    if len(f70) > 70:
        issues.append(f"OVERFLOW({len(f70)})")

    # 截断检测
    last_word = f70.rsplit(" ", 1)[-1].lower().strip(",.!;:")
    trailing_preps = {"for","to","in","on","at","with","by","from","of","and","or","the","a","an",
                      "für","zur","zum","mit","und","oder","bei","von","auf","im","am","ins",
                      "pour","avec","dans","sur","sous","sans","chez","et","ou","de","du","des",
                      "para","con","por","sin","entre","sobre","y","o","del","al",
                      "per","di","con","su","tra","fra","e","ed","a","da"}
    if last_word in trailing_preps:
        issues.append(f"TAIL_PREP({last_word})")

    if not issues:
        issues.append("OK")
    return {"issues": issues, "char_count": len(f70), "tag_count": len(tags), "model": r.get("model","?")}

def main():
    samples = load_samples(CSV_PATH)
    print(f"📋 已加载 {len(samples)} 条样本，开始回归...")
    print()

    start = time.time()
    results: list[tuple[int, dict, dict]] = []  # (idx, raw_result, check_result)
    by_country = defaultdict(lambda: {"total": 0, "ok": 0, "issues": []})

    for idx, s in enumerate(samples, 1):
        # 代发卖家无分类 → 从标题推断品类
        category = s["cn_category"]
        if not category or category.lower() in ("nan", "none", ""):
            category = guess_category_from_title(s["original_title"])
        r = optimize(
            original_title=s["original_title"],
            description=s["description"],
            original_category=category,
            material=s["material"],
            color=s["color"],
            country=s["country"],
        )
        ck = check(r)
        results.append((idx, r, ck))

        # 实时进度
        flag = "✅" if ck["issues"] == ["OK"] else "❌"
        issues_str = " ".join(ck["issues"]) if ck["issues"] != ["OK"] else ""
        print(f"  [{idx:2d}/{len(samples)}] {r['country']} {flag} "
              f"f70({ck['char_count']:2d}ch) tags({ck['tag_count']}) "
              f"model={ck['model']:20s} {issues_str}")

        country = r["country"]
        by_country[country]["total"] += 1
        if ck["issues"] == ["OK"]:
            by_country[country]["ok"] += 1
        else:
            by_country[country]["issues"].append((idx, r, ck))

    elapsed = time.time() - start

    # ── 汇总报告 ──
    print()
    print("=" * 100)
    print(f"  汇总报告 ({len(samples)} samples, {elapsed:.1f}s, ~{elapsed/len(samples):.1f}s/sample)")
    print("=" * 100)

    total_ok = sum(v["ok"] for v in by_country.values())
    total_cnt = sum(v["total"] for v in by_country.values())
    print(f"  整体通过率: {total_ok}/{total_cnt} ({100*total_ok//total_cnt}%)")
    print()

    all_issue_types = defaultdict(int)
    for _, _, ck in results:
        for iss in ck["issues"]:
            if iss != "OK":
                all_issue_types[iss] += 1

    print(f"  问题分布: {dict(all_issue_types)}" if all_issue_types else "  问题分布: 无")
    print()

    # 分国别
    for country in sorted(by_country.keys()):
        d = by_country[country]
        pct = 100 * d["ok"] // d["total"] if d["total"] else 0
        bar = "█" * (d["ok"] * 20 // d["total"]) if d["total"] else ""
        print(f"  {country:6s} {bar:<20s} {d['ok']}/{d['total']} ({pct}%)")

    # 详细失败项
    all_fails = [(idx, country, r, ck) for country, d in by_country.items() for idx, r, ck in d["issues"]]
    if all_fails:
        print()
        print("─" * 100)
        print("  ⚠️ 失败详情")
        print("─" * 100)
        for idx, country, r, ck in all_fails:
            print(f"  [#{idx}] {country} {ck['issues']}")
            print(f"    f70 ({len(r['front_70'])}ch): {r['front_70']}")
            print(f"    tags: {r['ai_tags']}")

    # ── 全量明细 ──
    print()
    print("=" * 100)
    print("  全量明细")
    print("=" * 100)
    for idx, r, ck in results:
        status = "✅" if ck["issues"] == ["OK"] else "❌"
        print(f"\n[{idx}] {r['country']} {status} model={ck['model']}")
        print(f"  full: {r['optimized_title']}")
        print(f"  f70:  {r['front_70']}")
        print(f"  rest: {r['rest']}")
        print(f"  tags: {r['ai_tags']}")
        print(f"  desc: {r['description_snippet'][:180]}")

    print()
    print("=" * 100)
    if all_issue_types:
        print(f"  REGRESSION FAILED — {len(all_issue_types)} issue types detected")
    else:
        print(f"  ALL CLEAN — {total_ok}/{total_cnt} passed, ready for gray-scale launch")
    print("=" * 100)

if __name__ == "__main__":
    main()
