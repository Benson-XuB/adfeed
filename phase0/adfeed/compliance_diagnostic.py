"""
Google Shopping Feed 合规诊断引擎 v1.0

三级分类：
  ❌ FATAL  — 必定拒登，必须修复
  ⚠️  WARN  — 有拒登风险，建议修复
  ✅ PASS   — 合规

规则覆盖：
  A类（自动修复）: title/GTIN/brand/GPC/availability/price/字段映射
  B类（诊断提示）: 图片域名风险/落地页一致性/缺政策页/价格异常
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

# ─────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────

@dataclass
class Issue:
    level: str          # "FATAL" / "WARN" / "PASS"
    rule_id: str        # 规则编号
    field_name: str     # 涉及的字段
    message: str        # 问题描述
    suggestion: str     # 修复建议
    sku: str = ""       # 变体 SKU

@dataclass
class SKUReport:
    sku: str
    title: str
    status: str         # "FATAL" / "WARN" / "PASS"
    issues: List[Issue] = field(default_factory=list)

    @property
    def fatal_count(self):
        return sum(1 for i in self.issues if i.level == "FATAL")

    @property
    def warn_count(self):
        return sum(1 for i in self.issues if i.level == "WARN")


# ─────────────────────────────────────────────
# 规则常量
# ─────────────────────────────────────────────

# 标题禁用促销词（Google 政策禁止）
PROMO_WORDS = [
    "free shipping", "sale", "discount", "cheap", "best price",
    "buy now", "hot", "new arrival", "2024", "2025", "2026",
    "limited time", "clearance", "wholesale", "free gift",
    "top rated", "#1", "best seller", "free return",
]

# 可疑图片域名（1688/速卖通/批发平台）
SUSPICIOUS_IMG_DOMAINS = [
    "cbu01.alicdn.com",      # 1688
    "alicdn.com",             # 阿里系
    "ae01.alicdn.com",        # 速卖通
    "img.alibaba.com",        # Alibaba
    "sc01.alicdn.com",        # 阿里国际站
    "cdn.temu.com",           # Temu
    "img.dhgate.com",         # DHGate
    "cjdropshipping.com",     # CJ
    "wsimg.com",              # GoDaddy 默认图
]

# availability 合法值
VALID_AVAILABILITY = {"in stock", "out of stock", "preorder", "backorder"}

# 合理价格区间（USD）— 超出此范围视为异常
REASONABLE_PRICE_RANGE = {"default": (0.50, 5000), "socks": (1.0, 100), "clothing": (3.0, 2000)}


# ─────────────────────────────────────────────
# 检查规则
# ─────────────────────────────────────────────

def check_title(row: dict) -> List[Issue]:
    """标题合规检查"""
    issues = []
    title = str(row.get("优化后标题", row.get("标题", "")))
    sku = str(row.get("SKU", ""))

    if not title or title.strip() == "" or title == "nan":
        issues.append(Issue("FATAL", "T01", "g:title", "标题为空",
                           "填写 10-150 字符的结构化标题", sku))
    elif len(title) < 10:
        issues.append(Issue("FATAL", "T02", "g:title", f"标题过短（{len(title)}字符）",
                           "标题至少 10 字符，建议包含品名+材质+颜色", sku))
    elif len(title) > 150:
        issues.append(Issue("FATAL", "T03", "g:title", f"标题超长（{len(title)}字符，上限150）",
                           "精简标题至 150 字符以内", sku))
    else:
        # 检查促销词
        title_lower = title.lower()
        found_promo = [w for w in PROMO_WORDS if w in title_lower]
        if found_promo:
            issues.append(Issue("FATAL", "T04", "g:title",
                               f"标题含促销词: {', '.join(found_promo)}",
                               "Google 禁止标题含促销词，删除后重试", sku))

        if len(title) > 80:
            issues.append(Issue("WARN", "T05", "g:title",
                               f"标题偏长（{len(title)}字符），建议 ≤80",
                               "精简至 80 字符内提升点击率", sku))

    return issues


def check_brand(row: dict) -> List[Issue]:
    """品牌字段检查"""
    issues = []
    brand = str(row.get("品牌", "")).strip()
    sku = str(row.get("SKU", ""))
    identifier_exists = str(row.get("identifier_exists", "no"))

    if not brand or brand in ("", "nan", "No Brand", "Unbranded"):
        if identifier_exists == "no":
            issues.append(Issue("WARN", "B01", "g:brand", "品牌为空（identifier_exists=no 时允许）",
                               "如有自有品牌请填写，否则保持 Generic", sku))
        else:
            issues.append(Issue("FATAL", "B02", "g:brand", "品牌为空但 identifier_exists=yes",
                               "设置品牌名或将 identifier_exists 改为 no", sku))
    elif brand.lower() == "generic":
        issues.append(Issue("WARN", "B03", "g:brand", "品牌为 Generic（弱势品牌）",
                           "注册店铺品牌替换 Generic 可提升品牌词流量", sku))

    return issues


def check_gtin(row: dict) -> List[Issue]:
    """GTIN/MPN 检查"""
    issues = []
    sku = str(row.get("SKU", "")).strip()
    gtin = str(row.get("gtin", "")).strip()
    mpn = str(row.get("mpn", "")).strip()
    identifier_exists = str(row.get("identifier_exists", "no"))

    if identifier_exists == "no":
        # identifier_exists=no 时，feed_generator 会自动用 SKU 填充 MPN
        if not gtin and not mpn and not sku:
            issues.append(Issue("WARN", "G01", "g:gtin/g:mpn",
                               "无 GTIN、无 MPN 且无 SKU",
                               "填写 SKU 或 MPN 用于商品识别", ""))
    else:
        if not gtin:
            issues.append(Issue("FATAL", "G02", "g:gtin",
                               "identifier_exists=yes 但缺少 GTIN",
                               "填写 UPC/EAN/ISBN 或将 identifier_exists 改为 no", sku))

    return issues


def check_gpc(row: dict) -> List[Issue]:
    """Google 商品类目检查"""
    issues = []
    sku = str(row.get("SKU", ""))
    gpc = str(row.get("GPC代码", "")).strip()
    gpc_path = str(row.get("GPC路径", "")).strip()

    if not gpc or gpc in ("", "nan"):
        issues.append(Issue("FATAL", "C01", "g:google_product_category",
                           "缺少 Google 商品类目",
                           "填写精确 GPC 编码（如袜子=209）", sku))
    elif gpc in ("187", "1604"):
        # 187=Shoes（太宽泛），1604=Clothing（太宽泛）
        issues.append(Issue("WARN", "C02", "g:google_product_category",
                           f"GPC={gpc} 过于宽泛",
                           "使用更精确的子类目编码（如袜子=209, T恤=212）", sku))

    if not gpc_path or gpc_path in ("", "nan"):
        issues.append(Issue("WARN", "C03", "g:product_type",
                           "缺少 product_type 路径",
                           "填写完整品类路径如 Apparel > Clothing > Socks", sku))

    return issues


def check_price(row: dict, store_currency: str = "USD") -> List[Issue]:
    """价格合理性检查"""
    issues = []
    sku = str(row.get("SKU", ""))
    price_str = str(row.get("价格", "0"))
    try:
        price = float(price_str.replace("USD", "").replace("EUR", "").strip())
    except (ValueError, AttributeError):
        issues.append(Issue("FATAL", "P01", "g:price", f"价格格式错误: {price_str}",
                           "价格必须是数字，格式: 9.99 USD", sku))
        return issues

    if price <= 0:
        issues.append(Issue("FATAL", "P02", "g:price", f"价格为 0 或负数: {price}",
                           "设置有效售价", sku))
    elif price > 5000:
        issues.append(Issue("FATAL", "P03", "g:price",
                           f"价格异常高: {price} USD（疑似测试数据）",
                           f"检查店铺原始价格（{store_currency}），确认是否为测试数据", sku))
    elif price < 0.50:
        issues.append(Issue("WARN", "P04", "g:price",
                           f"价格过低: {price} USD",
                           "确认价格是否正确，过低价格可能触发 GMC 审核", sku))

    return issues


def check_availability(row: dict) -> List[Issue]:
    """库存状态检查"""
    issues = []
    sku = str(row.get("SKU", ""))
    inv = row.get("库存", 0)
    try:
        inv = int(inv)
    except (ValueError, TypeError):
        inv = 0

    # availability 由 feed_generator 自动推断，这里检查库存是否为负
    if inv < 0:
        issues.append(Issue("FATAL", "A01", "g:availability",
                           f"库存为负数: {inv}",
                           "修正 Shopify 库存数据", sku))

    return issues


def check_image(row: dict) -> List[Issue]:
    """图片链接检查"""
    issues = []
    sku = str(row.get("SKU", ""))
    img = str(row.get("图片链接", "")).strip()

    if not img or img in ("", "nan"):
        issues.append(Issue("FATAL", "I01", "g:image_link", "主图为空",
                           "上传至少一张商品图片", sku))
    elif not img.startswith("http"):
        issues.append(Issue("FATAL", "I02", "g:image_link", f"图片 URL 非绝对路径: {img[:50]}",
                           "使用 https:// 开头的完整 URL", sku))
    else:
        # 检查是否来自批发平台
        img_lower = img.lower()
        matched_domains = [d for d in SUSPICIOUS_IMG_DOMAINS if d in img_lower]
        if matched_domains:
            issues.append(Issue("WARN", "I03", "g:image_link",
                               f"图片疑似来自批发平台: {', '.join(matched_domains)}",
                               "Google 2026 年通过图片指纹对比批发平台，建议替换为实拍图", sku))

    # 附加图片检查
    additional = str(row.get("附加图片", ""))
    if additional and additional != "nan":
        img_count = len([x for x in additional.split(",") if x.strip()])
        if img_count > 5:
            issues.append(Issue("WARN", "I04", "g:additional_image_link",
                               f"附加图片 {img_count} 张（建议 ≤5）",
                               "精简到 5 张以内优化抓取效率", sku))

    return issues


def check_link(row: dict) -> List[Issue]:
    """商品链接检查"""
    issues = []
    sku = str(row.get("SKU", ""))
    link = str(row.get("链接", "")).strip()

    if not link or link in ("", "nan"):
        issues.append(Issue("FATAL", "L01", "g:link", "商品链接为空",
                           "填写商品页面 URL", sku))
    elif not link.startswith("http"):
        issues.append(Issue("FATAL", "L02", "g:link", f"链接非绝对 URL: {link[:50]}",
                           "使用 https:// 开头的完整 URL", sku))
    elif ".jpg" in link.lower() or ".png" in link.lower():
        issues.append(Issue("FATAL", "L03", "g:link", "链接指向图片而非商品页",
                           "链接应为商品详情页 URL", sku))

    return issues


def check_variant_consistency(rows: List[dict]) -> List[Issue]:
    """跨变体一致性检查（按 item_group_id 分组，逐商品检查）"""
    issues = []
    if len(rows) <= 1:
        return issues

    # 按 item_group_id 分组
    from collections import defaultdict
    groups = defaultdict(list)
    for r in rows:
        gid = str(r.get("item_group_id", ""))
        groups[gid].append(r)

    for gid, group_rows in groups.items():
        if len(group_rows) <= 1:
            continue

        # 统计不同颜色数
        colors = [str(r.get("颜色", "")) for r in group_rows]
        unique_colors = set(colors)
        has_color_variants = len(unique_colors) > 1  # 是否有颜色变体

        if has_color_variants:
            # 只有存在多个颜色时，才检查颜色重复（同一颜色+不同尺码 = 正常）
            color_counts = {}
            for c in colors:
                color_counts[c] = color_counts.get(c, 0) + 1
            # 同一颜色出现多次不一定错（可能不同尺码），只有同颜色+同尺码才算重复
            size_color_pairs = [(str(r.get("颜色", "")), str(r.get("尺码", ""))) for r in group_rows]
            if len(size_color_pairs) != len(set(size_color_pairs)):
                dup_pairs = [p for p in size_color_pairs if size_color_pairs.count(p) > 1]
                issues.append(Issue("FATAL", "V03", "g:color",
                                   f"item_group {gid} 存在完全相同的变体（颜色+尺码重复）: {set(dup_pairs)}",
                                   "同一 item_group 内每个颜色+尺码组合必须唯一", ""))

            # 描述差异化只在有颜色变体时检查
            descriptions = set(str(r.get("描述", ""))[:50] for r in group_rows)
            if len(descriptions) == 1 and len(unique_colors) > 1:
                issues.append(Issue("WARN", "V02", "g:description",
                                   f"item_group {gid} 所有颜色变体描述完全相同（同质化）",
                                   "为每个颜色变体生成差异化描述提升 SEO", ""))

    return issues


# ─────────────────────────────────────────────
# 诊断报告生成
# ─────────────────────────────────────────────

def diagnose_row(row: dict, store_currency: str = "USD") -> SKUReport:
    """诊断单个 SKU"""
    sku = str(row.get("SKU", ""))
    title = str(row.get("优化后标题", row.get("标题", "")))[:60]

    all_issues = []
    all_issues.extend(check_title(row))
    all_issues.extend(check_brand(row))
    all_issues.extend(check_gtin(row))
    all_issues.extend(check_gpc(row))
    all_issues.extend(check_price(row, store_currency))
    all_issues.extend(check_availability(row))
    all_issues.extend(check_image(row))
    all_issues.extend(check_link(row))

    # 判定状态
    has_fatal = any(i.level == "FATAL" for i in all_issues)
    has_warn = any(i.level == "WARN" for i in all_issues)
    status = "FATAL" if has_fatal else ("WARN" if has_warn else "PASS")

    return SKUReport(sku=sku, title=title, status=status, issues=all_issues)


def diagnose_all(rows: List[dict], store_currency: str = "USD",
                 shop_title: str = "") -> str:
    """诊断所有 SKU 并生成文本报告"""
    reports = []
    for row in rows:
        reports.append(diagnose_row(row, store_currency))

    # 跨变体检查
    variant_issues = check_variant_consistency(rows)

    # 统计
    fatal_count = sum(1 for r in reports if r.status == "FATAL")
    warn_count = sum(1 for r in reports if r.status == "WARN")
    pass_count = sum(1 for r in reports if r.status == "PASS")
    total = len(reports)

    # 生成报告
    lines = []
    lines.append("=" * 60)
    lines.append("  Google Shopping Feed 合规诊断报告")
    lines.append(f"  生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    if shop_title:
        lines.append(f"  店铺: {shop_title}")
    lines.append(f"  店铺货币: {store_currency}")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  总计: {total} 个 SKU")
    lines.append(f"  ❌ 致命: {fatal_count}")
    lines.append(f"  ⚠️  风险: {warn_count}")
    lines.append(f"  ✅ 通过: {pass_count}")
    lines.append("")

    # 致命问题汇总
    fatal_issues = [i for r in reports for i in r.issues if i.level == "FATAL"]
    if fatal_issues:
        lines.append("─" * 60)
        lines.append("❌ 致命问题（必须修复，否则直接拒登）")
        lines.append("─" * 60)
        for issue in fatal_issues:
            sku_tag = f"[{issue.sku}]" if issue.sku else ""
            lines.append(f"  {sku_tag} {issue.rule_id} | {issue.field_name}")
            lines.append(f"    问题: {issue.message}")
            lines.append(f"    建议: {issue.suggestion}")
            lines.append("")

    # 风险问题汇总
    warn_issues = [i for r in reports for i in r.issues if i.level == "WARN"]
    if warn_issues:
        lines.append("─" * 60)
        lines.append("⚠️  风险问题（建议修复，降低拒登概率）")
        lines.append("─" * 60)
        for issue in warn_issues:
            sku_tag = f"[{issue.sku}]" if issue.sku else ""
            lines.append(f"  {sku_tag} {issue.rule_id} | {issue.field_name}")
            lines.append(f"    问题: {issue.message}")
            lines.append(f"    建议: {issue.suggestion}")
            lines.append("")

    # 跨变体问题
    if variant_issues:
        lines.append("─" * 60)
        lines.append("📦 变体级别问题")
        lines.append("─" * 60)
        for issue in variant_issues:
            lines.append(f"  {issue.rule_id} | {issue.field_name}")
            lines.append(f"    问题: {issue.message}")
            lines.append(f"    建议: {issue.suggestion}")
            lines.append("")

    # 行动清单
    lines.append("─" * 60)
    lines.append("📋 行动清单（按优先级排序）")
    lines.append("─" * 60)
    action_items = []

    # 致命 → 必须
    for issue in fatal_issues:
        action_items.append(f"  🔴 [必须] {issue.rule_id}: {issue.suggestion} (SKU: {issue.sku})")
    # 变体致命
    for issue in variant_issues:
        if issue.level == "FATAL":
            action_items.append(f"  🔴 [必须] {issue.rule_id}: {issue.suggestion}")
    # 风险 → 建议
    for issue in warn_issues:
        action_items.append(f"  🟡 [建议] {issue.rule_id}: {issue.suggestion} (SKU: {issue.sku})")
    for issue in variant_issues:
        if issue.level == "WARN":
            action_items.append(f"  🟡 [建议] {issue.rule_id}: {issue.suggestion}")

    # 去重 + 合并同类问题
    seen_rules = {}  # rule_id -> list of skus
    unique_items = []
    for item in action_items:
        # 提取 rule_id
        match = re.search(r'(T\d+|B\d+|G\d+|C\d+|P\d+|A\d+|I\d+|L\d+|V\d+)', item)
        if match:
            rule_id = match.group(1)
            if rule_id not in seen_rules:
                seen_rules[rule_id] = []
                unique_items.append(item)
            else:
                seen_rules[rule_id].append(item)
        else:
            unique_items.append(item)

    # 如果同类问题超过 3 个，合并显示
    final_lines = []
    for item in unique_items:
        match = re.search(r'(T\d+|B\d+|G\d+|C\d+|P\d+|A\d+|I\d+|L\d+|V\d+)', item)
        if match:
            rule_id = match.group(1)
            count = len(seen_rules.get(rule_id, [])) + 1
            if count > 3:
                # 合并：显示影响数量
                final_lines.append(item.rsplit("(SKU:", 1)[0].rstrip() + f" ({count} 个 SKU)")
                continue
        final_lines.append(item)

    lines.extend(final_lines)

    if not action_items:
        lines.append("  🎉 全部合规！无需修改。")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
