"""AdFeed AI — 核心流水线编排器 v3.0（脏词过滤 + 属性标准化 + 并行多国原生语种）

每条新品对目标国家逐一调用各自语种的 AI 生成原生标题。
集成：脏词清洗 + 属性标准化 + 产品记忆库增量同步 + MD5 去重 + GPC 匹配 + 多国语标题生成 + 合规检查 + 多国 Feed XML 输出。
v3.0: 集成 dirty_word_filter + attribute_normalizer，全面消灭中文泄漏和脏词污染。
"""

import json
import os
import re
import time
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from .config import (
    MOCK_SKU_COUNT, FEED_OUTPUT_XML, COMPARISON_REPORT, SUMMARY_JSON,
    DEFAULT_COUNTRY, ensure_dirs, validate,
)
from .mock_data import generate as generate_mock, save as save_mock

# 并行度：LLM API 是 I/O-bound，8-12 个 worker 通常足够
DEFAULT_MAX_WORKERS = int(os.environ.get("ADFEED_PARALLEL_WORKERS", "8"))

# ── GPC 匹配引擎（方案C：关键词 + LLM 兜底） ──
from .gpc_matcher import match as gpc_match, load_taxonomy as load_gpc_taxonomy
print("[Pipeline] GPC engine: keyword + LLM fallback (Plan C)")

from .title_optimizer import optimize_multi_country, rewrite_for_platform
from .compliance_engine import check_and_clean, infer_product_attributes, scan_image_watermarks, infer_energy_efficiency_class
from .dirty_word_filter import clean_dirty_words
from .attribute_normalizer import normalize_all_attributes
from .variant_expander import expand_variants
from .feed_generator import generate as generate_feed_xml, generate_comparison_report
from .product_memory import (
    classify_row, save_new_product, update_price_inventory,
    update_multi_country_titles, get_stats as get_memory_stats,
    lookup, cny_to_usd,
)
from .dedup_lock import (
    check_file as check_dedup, record_file as record_dedup,
    check_row as check_row_dedup, record_row as record_row_dedup,
)
from .cultural_context import season_for_date, resolve_category, get_search_prefix, guess_category_from_title


def run(excel_path: str = None, countries: list[str] = None,
        force: bool = False, use_mock: bool = False, max_rows: int = None,
        max_workers: int = None, progress_callback=None,
        products_data: list[dict] = None, feed_dir: str = None) -> dict:
    """完整清洗流程入口 v2.2 — 并行多国原生语种版本

    Args:
        excel_path: 输入 Excel 文件路径
        countries: 目标国家列表，默认 ["US"]
        force: 跳过去重强制执行
        use_mock: 使用模拟数据
        max_rows: 最多处理行数（配额截断），None = 全部
        max_workers: 并行线程数，默认 8
        progress_callback: 进度回调 (done_rows, total_rows) -> None
        products_data: 直接传入产品数据列表（如来自 Shopify），优先于 excel_path
        feed_dir: 自定义 Feed 输出目录（如 feeds/{store_id}），None 则用默认路径
    """
    if countries is None:
        countries = [DEFAULT_COUNTRY]

    ensure_dirs()
    validate()

    start_time = time.time()
    print("=" * 60)
    print(f"  AdFeed AI — v2.1 Multi-Country Engine ({', '.join(countries)})")
    print("=" * 60)

    # ── Step 1: 加载数据 ──
    print("\n[1/6] Loading product data...")
    if products_data:
        # 从外部数据源（如 Shopify）直接传入产品数据
        df = pd.DataFrame(products_data)
        file_md5 = "shopify_import"
        print(f"  Loaded from products_data: {len(df)} SKU")
    elif excel_path and Path(excel_path).exists() and not use_mock:
        dedup_result = check_dedup(excel_path, force=force)
        if dedup_result["is_duplicate"]:
            print(f"  DUPLICATE FILE! MD5: {dedup_result['md5'][:12]}...")
            print(f"  Previous: {dedup_result['previous_at']}")
            return {
                "status": "duplicate", "md5": dedup_result["md5"],
                "previous_task_id": dedup_result["previous_task_id"],
                "previous_at": dedup_result["previous_at"],
            }
        df = pd.read_excel(excel_path)
        if max_rows and len(df) > max_rows:
            df = df.head(max_rows)
            print(f"  Loaded: {excel_path} ({len(df)} SKU) — quota limit applied")
        else:
            print(f"  Loaded: {excel_path} ({len(df)} SKU)")
        file_md5 = dedup_result["md5"]
    else:
        if excel_path and not use_mock:
            print(f"  File not found: {excel_path}，using mock data")
        df = generate_mock(count=MOCK_SKU_COUNT)
        save_mock(df)
        file_md5 = "mock_data"
        print(f"  Generated mock data: {len(df)} SKU")

    total = len(df)
    print(f"  Total: {total} SKU, targeting {len(countries)} countries")

    # ── Step 2: 初始化 GPC ──
    print(f"\n[2/6] Init GPC engine (keyword + LLM fallback)...")
    load_gpc_taxonomy()
    print(f"  GPC engine ready")

    # ── Step 3: 并行处理所有行 ──
    workers = max_workers or DEFAULT_MAX_WORKERS
    print(f"\n[3/6] Processing {total} SKU x {len(countries)} countries ({workers} workers)...")

    # 预处理：构建 (idx, row_dict) 列表供多线程使用
    row_list = []
    for i, (_, row) in enumerate(df.iterrows(), 1):
        row_list.append((i, {k: str(row.get(k, "")) for k in df.columns}))

    results_lock = Lock()
    stats_lock = Lock()
    stats = {
        "ai_processed": 0, "ai_country_calls": 0, "skipped_old": 0,
        "price_updated": 0, "dedup_skipped": 0, "partial_reclean": 0,
        "compliance_warnings": 0, "watermark_flagged": 0,
        "tokens_estimated": 0, "tokens_saved": 0,
    }
    results = []
    done_count = [0]  # 用列表包装实现跨闭包修改

    def _process_one(idx_total: tuple) -> dict:
        """处理单行的完整逻辑（线程安全）"""
        i, row = idx_total
        sku = row.get("SKU", f"SKU{i:04d}")
        title = row.get("标题", "")
        if not title:
            for k in ["标题", "产品名称", "product_name", "名称", "品名"]:
                if row.get(k, ""):
                    title = str(row[k])
                    break
        desc = row.get("描述", "")
        category = row.get("分类", "")
        if not category or category.lower() in ("nan", "none", ""):
            category = guess_category_from_title(title)
        brand = row.get("品牌", row.get("brand", ""))
        material = row.get("材质", "")
        color = row.get("颜色", "")
        size = row.get("尺码", row.get("size", ""))
        image_url = row.get("图片链接", "")
        additional_images_raw = row.get("附加图片", row.get("additional_images", ""))
        spec_raw = row.get("规格", row.get("specification", row.get("specs", "")))
        price_raw = row.get("价格", 0)
        try:
            price_cny = float(price_raw) if price_raw else 0.0
        except (ValueError, TypeError):
            price_cny = 0.0
        inventory_raw = row.get("库存", row.get("inventory", 1))
        try:
            inventory = int(inventory_raw)
        except (ValueError, TypeError):
            inventory = 1

        print(f"  [{i}/{total}] {sku}: {title[:30]}...", end=" ")

        # ── v3.0: 脏词预清洗（在 AI 调用前切除 1688/速卖通污染词）──
        dirty_result = clean_dirty_words(title, desc)
        if dirty_result["dirty_count"] > 0:
            title = dirty_result["clean_title"] or title
            desc = dirty_result["clean_description"] or desc
            print(f"[🧹{dirty_result['dirty_count']}w]", end=" ")

        # 行级去重
        row_dedup = check_row_dedup(sku, title, price_cny)
        if row_dedup and not force:
            print(f"SKIP (dedup)")
            with stats_lock:
                stats["dedup_skipped"] += 1
                stats["tokens_saved"] += 5000 * len(countries)
            existing = lookup(sku)
            return {
                "sku": sku, "original_title": title,
                "optimized_titles": existing.get("optimized_titles", {}),
                "gpc_code": existing.get("gpc_code", ""), "gpc_path": existing.get("gpc_path", ""),
                "ai_tags_by_lang": existing.get("ai_tags_by_lang", {}),
                "description_snippets": existing.get("description_snippets", {}),
                "action": "dedup_skip",
                "price_usd": existing.get("price_usd", 0),
                "inventory": inventory, "image_url": image_url,
                "color": color, "material": material, "category": category,
                "brand": brand, "additional_images": additional_images_raw,
                "gender": existing.get("gender", "unisex"),
                "age_group": existing.get("age_group", "adult"),
                "size": size, "spec": spec_raw,
            }

        # 产品记忆库增量检查
        classification = classify_row(
            product_id=sku, title=title, price_cny=price_cny,
            inventory=inventory, description=desc, category=category,
            material=material, color=color, image_url=image_url,
            target_countries=countries,
        )

        if classification["action"] == "skip":
            print("SKIP (no change, 0 Token)")
            with stats_lock:
                stats["skipped_old"] += 1
                stats["tokens_saved"] += 5000 * len(countries)
            existing = classification["existing"]
            return {
                "sku": sku, "original_title": title,
                "optimized_titles": existing.get("optimized_titles", {}),
                "gpc_code": existing.get("gpc_code", ""), "gpc_path": existing.get("gpc_path", ""),
                "ai_tags_by_lang": existing.get("ai_tags_by_lang", {}),
                "description_snippets": existing.get("description_snippets", {}),
                "action": "skip",
                "price_usd": existing.get("price_usd", 0),
                "inventory": inventory, "image_url": image_url,
                "color": color, "material": material, "category": category,
                "brand": brand, "additional_images": additional_images_raw,
                "gender": existing.get("gender", "unisex"),
                "age_group": existing.get("age_group", "adult"),
                "size": size, "spec": spec_raw,
            }

        if classification["action"] == "price_inventory_update":
            update_price_inventory(sku, price_cny, inventory)
            print(f"PRICE/INV UPDATE (0 Token)")
            with stats_lock:
                stats["price_updated"] += 1
                stats["tokens_saved"] += 5000 * len(countries)
            existing = classification["existing"]
            return {
                "sku": sku, "original_title": title,
                "optimized_titles": existing.get("optimized_titles", {}),
                "gpc_code": existing.get("gpc_code", ""), "gpc_path": existing.get("gpc_path", ""),
                "ai_tags_by_lang": existing.get("ai_tags_by_lang", {}),
                "description_snippets": existing.get("description_snippets", {}),
                "action": "price_update",
                "price_usd": classification["price_usd"],
                "inventory": inventory, "image_url": image_url,
                "color": color, "material": material, "category": category,
                "brand": brand, "additional_images": additional_images_raw,
                "gender": existing.get("gender", "unisex"),
                "age_group": existing.get("age_group", "adult"),
                "size": size, "spec": spec_raw,
            }

        # ── 需要 AI 清洗 ──
        needs_countries = classification["needs_reclean_for"]
        is_full_clean = classification["action"] == "ai_full_clean"

        gpc = gpc_match(title=title, category=category, material=material)
        print(f"GPC:{gpc['gpc_code'][:8]}|{gpc['confidence']:.2f} [{len(needs_countries)}c]", end=" ")

        multi = optimize_multi_country(
            original_title=title, countries=needs_countries,
            description=desc, original_category=category,
            material=material, color=color,
            gpc_path=gpc["gpc_path"],
            target_season=season_for_date(),
        )
        optimized_titles = multi["optimized_titles"]
        ai_tags_by_lang = multi["ai_tags_by_lang"]
        description_snippets = multi["description_snippets"]
        tokens_this_row = 5000 * len(needs_countries)

        # 合规检查
        comp_results = {}
        total_violations = 0
        for c in needs_countries:
            ct = optimized_titles.get(c, title)
            comp = check_and_clean(ct, country=c)
            comp_results[c] = comp
            if comp["status"] == "warning":
                with stats_lock:
                    stats["compliance_warnings"] += 1
            total_violations += comp["count"]

        flag = f"⚠{total_violations}v" if total_violations > 0 else "OK"

        # 属性推断
        attr = infer_product_attributes(
            category_key=resolve_category(category, gpc.get("gpc_path", "")),
            gpc_path=gpc.get("gpc_path", ""),
            original_title=title,
            color=color, material=material,
            search_prefix=get_search_prefix("US", category, gpc.get("gpc_path", "")),
            size=size,
        )

        # 能效等级
        energy_class = infer_energy_efficiency_class(gpc.get("gpc_path", ""), title)

        # 水印检测
        all_urls = [image_url]
        if additional_images_raw:
            all_urls.extend(u.strip() for u in additional_images_raw.split(",") if u.strip())
        watermark_report = scan_image_watermarks(all_urls)
        if not watermark_report["clean"]:
            print("💧", end=" ")
            with stats_lock:
                stats["watermark_flagged"] += 1

        # 存入产品记忆库
        if is_full_clean:
            save_new_product(
                product_id=sku, title=title, price_cny=price_cny,
                inventory=inventory, description=desc, category=category,
                brand=brand, material=material, color=color, size=size,
                size_system="", size_type="",
                gender=attr["gender"], age_group=attr["age_group"],
                identifier_exists="no", gtin="", mpn="",
                item_group_id=attr["item_group_id"],
                image_url=image_url, additional_images=additional_images_raw,
                sale_price_usd=0, sale_price_effective_date="",
                custom_label_0="", custom_label_1="", custom_label_2="",
                custom_label_3="", custom_label_4="",
                shipping_country="", shipping_price=0, shipping_weight="",
                min_handling_time=0, max_handling_time=0,
                adult="no", multipack=0, is_bundle="no", tax="",
                energy_efficiency_class=energy_class,
                unit_pricing_measure="", unit_pricing_base_measure="",
                gpc_code=gpc["gpc_code"], gpc_path=gpc["gpc_path"],
                optimized_titles=optimized_titles,
                ai_tags_by_lang=ai_tags_by_lang,
                description_snippets=description_snippets,
                target_countries=countries,
            )
        else:
            update_multi_country_titles(
                product_id=sku,
                optimized_titles=optimized_titles,
                ai_tags_by_lang=ai_tags_by_lang,
                description_snippets=description_snippets,
            )

        record_row_dedup(sku, title, price_cny, file_md5)

        with stats_lock:
            stats["ai_country_calls"] += len(needs_countries)
            stats["tokens_estimated"] += 5000 * len(needs_countries)
            if is_full_clean:
                stats["ai_processed"] += 1
            else:
                stats["partial_reclean"] += 1

        print(f"{flag} ({tokens_this_row:,}T)")

        return {
            "sku": sku, "original_title": title,
            "optimized_titles": optimized_titles,
            "gpc_code": gpc["gpc_code"], "gpc_path": gpc["gpc_path"],
            "gpc_confidence": gpc["confidence"],
            "ai_tags_by_lang": ai_tags_by_lang,
            "description_snippets": description_snippets,
            "compliance": comp_results,
            "action": classification["action"],
            "price_usd": classification["price_usd"],
            "tokens_this_row": tokens_this_row,
            "item_group_id": attr["item_group_id"],
            "size": size, "gender": attr["gender"],
            "age_group": attr["age_group"],
            "color": color, "material": material, "category": category,
            "identifier_exists": "no", "gtin": "", "mpn": "",
            "image_url": image_url,
            "inventory": inventory,
            "additional_images": additional_images_raw,
            "spec": spec_raw,
            "watermark_clean": watermark_report["clean"],
            "brand": brand,
        }

    # 使用 ThreadPoolExecutor 并行处理
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process_one, r): r[0] for r in row_list}
        for future in as_completed(futures):
            try:
                result = future.result()
                with results_lock:
                    results.append(result)
                    done_count[0] = len(results)
                    if progress_callback:
                        progress_callback(done_count[0], total)
            except Exception as e:
                idx = futures[future]
                print(f"  [{idx}/{total}] ERROR: {e}")
                with results_lock:
                    done_count[0] += 1

    # 按原始顺序排序（保证输出稳定）
    results.sort(key=lambda r: r.get("sku", ""))

    # ── Step 4: 变体展开 + 生成输出文件（每个国家独立 Feed） ──
    print(f"\n[4/6] Expanding variants & generating feed XMLs...")

    # Step 4a: 变体展开 — 每个产品结果展开为 variant 级别行
    all_variant_rows = []  # (variant_row_dict, result_dict) 对
    total_variants = 0
    for r in results:
        # 构建产品级行数据（含 AI 优化结果）
        product_row = {
            "SKU": r["sku"],
            "标题": r["original_title"],
            "描述": r.get("description_snippets", {}).get("US", ""),
            "价格": r.get("price_usd", 0),
            "库存": r.get("inventory", 1),
            "图片链接": r.get("image_url", ""),
            "颜色": r.get("color", ""),
            "尺码": r.get("size", ""),
            "材质": r.get("material", ""),
            "分类": r.get("category", ""),
            "品牌": r.get("brand", ""),
            "规格": r.get("spec", ""),  # 1688 格式规格字段（变体展开用）
            "item_group_id": r.get("item_group_id", ""),
            "gender": r.get("gender", "unisex"),
            "age_group": r.get("age_group", "adult"),
            "附加图片": r.get("additional_images", ""),
        }
        # 传递 AI 优化结果（所有 variant 共享）
        for country in countries:
            cu = country.upper()
            product_row[f"_opt_title_{cu}"] = r.get("optimized_titles", {}).get(cu, r["original_title"])
            product_row[f"_desc_{cu}"] = r.get("description_snippets", {}).get(cu, "")
            product_row[f"_tags_{cu}"] = r.get("ai_tags_by_lang", {}).get(cu, [])

        variants = expand_variants(product_row)
        for v in variants:
            v["_result_ref"] = r  # 保留对原始结果的引用
        all_variant_rows.extend(variants)
        total_variants += len(variants)

    print(f"  Variants: {len(results)} products → {total_variants} variant rows")

    # Step 4b: 为每个国家生成 Feed XML
    for country in countries:
        country_upper = country.upper()
        rows_for_country = []
        for v in all_variant_rows:
            r = v["_result_ref"]
            opt_title = v.get(f"_opt_title_{country_upper}", v.get("标题", ""))
            desc_snippet = v.get(f"_desc_{country_upper}", "")
            ai_tags = v.get(f"_tags_{country_upper}", [])

            # ── v3.0: 属性标准化（颜色/尺码/材质翻译为 GMC 标准值）──
            raw_attrs = {
                "color": v.get("颜色", v.get("color", "")),
                "size": v.get("尺码", v.get("size", "")),
                "material": v.get("材质", ""),
                "gender": v.get("gender", ""),
                "age_group": v.get("age_group", ""),
                "title": v.get("标题", ""),
                "category": v.get("分类", ""),
            }
            normalized_attrs = normalize_all_attributes(raw_attrs, country=country_upper)

            # 变体级 SKU / link / item_group_id
            variant_sku = v.get("variant_id", v.get("SKU", r["sku"]))
            item_group_id = v.get("item_group_id", r.get("item_group_id", r["sku"]))
            variant_link = v.get("链接", "")
            if not variant_link:
                variant_link = f"/products/{variant_sku}"

            rows_for_country.append({
                "SKU": variant_sku,
                "优化后标题": opt_title,
                "标题": v.get("标题", r["original_title"]),
                "描述": desc_snippet,
                "GPC代码": r.get("gpc_code", ""),
                "GPC路径": r.get("gpc_path", ""),
                "材质": normalized_attrs.get("material", ""),
                "颜色": normalized_attrs.get("color", ""),
                "尺码": normalized_attrs.get("size", ""),
                "品牌": v.get("品牌", r.get("brand", "")),
                "item_group_id": item_group_id,
                "gender": normalized_attrs.get("gender", "unisex"),
                "age_group": normalized_attrs.get("age_group", "adult"),
                "identifier_exists": "no",
                "gtin": "",
                # v3.0: 价格/库存/图片必须透传给 feed_generator
                "价格": v.get("价格", r.get("price_usd", 0)),
                "库存": v.get("库存", r.get("inventory", 1)),
                "图片链接": v.get("图片链接", r.get("image_url", "")),
                "附加图片": v.get("附加图片", r.get("additional_images", "")),
                "链接": variant_link,
                "匹配置信度": r.get("gpc_confidence", 0),
                "合规状态": str(r.get("compliance", {}).get(country_upper, {}).get("status", "pass")),
                "违规详情": str(r.get("compliance", {}).get(country_upper, {}).get("count", 0)),
                "ai_tags": ", ".join(ai_tags) if ai_tags else "",
                "description_snippet": desc_snippet,
                "水印检测": "OK" if r.get("watermark_clean", True) else "有水印",
                # v3.0: custom_label 注入 AI 标签
                "custom_label_0": ai_tags[0] if len(ai_tags) > 0 else "",
                "custom_label_1": ai_tags[1] if len(ai_tags) > 1 else "",
                "custom_label_2": "",  # 价格区间标签（在 feed_generator 中填充）
                "custom_label_3": "",  # 季节性标签（在 feed_generator 中填充）
                "custom_label_4": "",  # 利润率标签（在 feed_generator 中填充）
            })

        country_df = pd.DataFrame(rows_for_country)
        if feed_dir:
            # 店铺模式：输出到自定义目录
            feed_path = Path(feed_dir) / f"{country.lower()}.xml"
        else:
            feed_path = Path(str(FEED_OUTPUT_XML).replace("feed_us", f"feed_{country.lower()}"))
        xml = generate_feed_xml(country_df, country)
        feed_path.parent.mkdir(parents=True, exist_ok=True)
        feed_path.write_text(xml, encoding="utf-8")
        print(f"  [{country}] Feed XML: {feed_path} ({len(country_df)} variants, {len(xml.encode('utf-8')):,} bytes)")

    # 对比报告（用 US 作为默认展示）
    report_df = pd.DataFrame([
        {
            "SKU": r["sku"],
            "原始标题": r["original_title"],
            "优化后标题_US": r.get("optimized_titles", {}).get("US", ""),
            "优化后标题_DE": r.get("optimized_titles", {}).get("DE", ""),
            "优化后标题_FR": r.get("optimized_titles", {}).get("FR", ""),
            "原始分类": "",
            "GPC代码": r.get("gpc_code", ""),
            "GPC路径": r.get("gpc_path", ""),
            "匹配置信度": r.get("gpc_confidence", 0),
            "合规状态": str(r.get("compliance", {}).get("US", {}).get("status", "pass")),
            "违规详情": str(r.get("compliance", {}).get("US", {}).get("count", 0)),
            "处理动作": r.get("action", ""),
            "Token消耗": r.get("tokens_this_row", 0),
        }
        for r in results
    ])
    generate_comparison_report(report_df, COMPARISON_REPORT)

    # ── Step 5: 记录去重 ──
    print(f"\n[5/6] Recording dedup...")
    if file_md5 and file_md5 not in ("mock_data", "shopify_import") and excel_path:
        record_dedup(excel_path, f"task_{int(time.time())}", total)

    # ── Step 6: 摘要 ──
    elapsed = time.time() - start_time
    memory_stats = get_memory_stats()

    summary = {
        "total_sku": total,
        "total_countries": len(countries),
        "total_country_calls": stats["ai_country_calls"],
        "ai_full_clean": stats["ai_processed"],
        "partial_reclean": stats["partial_reclean"],
        "skipped_old": stats["skipped_old"],
        "price_updated": stats["price_updated"],
        "dedup_skipped": stats["dedup_skipped"],
        "compliance_warnings": stats["compliance_warnings"],
        "watermark_flagged": stats["watermark_flagged"],
        "tokens_estimated": stats["tokens_estimated"],
        "tokens_saved": stats["tokens_saved"],
        "time_seconds": round(elapsed, 1),
        "product_memory_stats": memory_stats,
        "countries": countries,
    }

    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    ac = stats["ai_country_calls"]
    ap = stats["ai_processed"]
    pr = stats["partial_reclean"]
    so = stats["skipped_old"]
    pu = stats["price_updated"]
    ds = stats["dedup_skipped"]
    te = stats["tokens_estimated"]
    ts_saved = stats["tokens_saved"]

    print(f"\n[6/6] {'=' * 60}")
    print(f"  DONE — {elapsed:.1f}s")
    print(f"  {total} SKU x {len(countries)} countries = {ac} AI calls")
    print(f"  AI cleaned: {ap} full + {pr} partial")
    print(f"  Skipped: {so} old + {pu} price/inv updates + {ds} dedup")
    print(f"  Tokens est: {te:,}  |  Saved: {ts_saved:,}")
    print(f"  Output: {FEED_OUTPUT_XML}")
    print(f"  Report: {COMPARISON_REPORT}")
    print(f"  Memory: {memory_stats['total_products']} products stored")
    print(f"{'=' * 60}\n")

    return summary


# ─────────────────────────────────────────────────
# 三段式流水线：段2 — AI 异步清洗
# ─────────────────────────────────────────────────

def optimize_for_store(store_id: str, product_ids: list[str] = None,
                       countries: list[str] = None, max_workers: int = None) -> dict:
    """段2: AI 异步清洗 — 读取 raw 产品 → GPC匹配 + 标题优化 → 回写 DB

    Args:
        store_id: 店铺 ID
        product_ids: 指定产品 ID 列表，None 则处理所有 raw 产品
        countries: 目标国家，默认 ["US"]
        max_workers: 并行线程数

    Returns:
        {"processed": N, "success": N, "failed": N}
    """
    from . import store_db
    from .cultural_context import season_for_date, resolve_category, get_search_prefix
    from .compliance_engine import check_and_clean, infer_product_attributes, infer_energy_efficiency_class

    if countries is None:
        countries = [DEFAULT_COUNTRY]

    store = store_db.get_store(store_id)
    if not store:
        raise ValueError(f"Store not found: {store_id}")

    # 加载 GPC
    load_gpc_taxonomy()

    # 获取待处理产品
    if product_ids:
        products = [store_db.get_product(pid) for pid in product_ids]
        products = [p for p in products if p is not None]
    else:
        # 获取所有 raw 状态的产品
        products = store_db.get_store_products_by_status(store_id, ai_status="raw")

    if not products:
        return {"processed": 0, "success": 0, "failed": 0, "message": "No raw products to process"}

    # 标记为 processing
    store_db.batch_set_ai_status([p.id for p in products], "processing")

    print(f"\n[Optimize] Processing {len(products)} products for store {store_id}...")

    workers = max_workers or DEFAULT_MAX_WORKERS
    success_count = 0
    fail_count = 0

    def _process_one(product):
        """处理单个产品的 AI 清洗（完整 pipeline：脏词→GPC→标题→属性→回写）"""
        raw_title = product.title or ""
        raw_desc = product.description or ""
        category = product.product_type or ""
        material = product.material or ""
        brand = product.brand or store.default_brand or ""
        color = ""
        size = ""

        # ── 1. 脏词预清洗（1688 污染词必须在 AI 调用前切除）──
        dirty_result = clean_dirty_words(raw_title, raw_desc)
        if dirty_result["dirty_count"] > 0:
            title = dirty_result["clean_title"] or raw_title
            desc = dirty_result["clean_description"] or raw_desc
            print(f"  [{product.id[:12]}] 🧹{dirty_result['dirty_count']} dirty words cleaned")
        else:
            title = raw_title
            desc = raw_desc

        # ── 2. GPC 品类匹配 ──
        gpc = gpc_match(title=title, category=category, material=material)

        # ── 3. 标题优化（多语种）──
        try:
            multi = optimize_multi_country(
                original_title=title, countries=countries,
                description=desc,
                original_category=category,
                material=material,
                gpc_path=gpc["gpc_path"],
                target_season=season_for_date(),
            )
            optimized_title = multi["optimized_titles"].get(countries[0], title)
            cleaned_title = json.dumps(multi["optimized_titles"], ensure_ascii=False)
            cleaned_desc = json.dumps(multi["description_snippets"], ensure_ascii=False)
        except Exception as e:
            print(f"  [WARN] AI title optimization failed for {product.id[:12]}: {e}")
            optimized_title = title
            cleaned_title = None
            cleaned_desc = None

        # ── 4. 属性推断（gender/age_group，从标题+品类+GPC推断）──
        attr = infer_product_attributes(
            category_key=resolve_category(category, gpc.get("gpc_path", "")),
            gpc_path=gpc.get("gpc_path", ""),
            original_title=title,
            color=color, material=material,
            search_prefix=get_search_prefix("US", category, gpc.get("gpc_path", "")),
            size=size,
        )

        # ── 5. 回写 DB（含 gender/age_group）──
        store_db.update_product_ai_result(
            product_id=product.id,
            optimized_title=optimized_title,
            gpc_code=gpc["gpc_code"],
            gpc_path=gpc["gpc_path"],
            gpc_confidence=gpc["confidence"],
            gpc_source=gpc["source"],
            cleaned_title=cleaned_title,
            cleaned_description=cleaned_desc,
            gender=attr.get("gender"),
            age_group=attr.get("age_group"),
        )
        return True

    # 并行处理
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process_one, p): p for p in products}
        for future in as_completed(futures):
            try:
                future.result()
                success_count += 1
            except Exception as e:
                product = futures[future]
                print(f"  [ERROR] {product.id[:12]}: {e}")
                fail_count += 1
                # 标记为 error
                store_db.batch_set_ai_status([product.id], "error")

    print(f"[Optimize] Done: {success_count} success, {fail_count} failed")
    return {
        "processed": len(products),
        "success": success_count,
        "failed": fail_count,
    }


def optimize_layered(
    store_id: str,
    product_ids: list[str],
    platforms: list[str] = None,
    languages: list[str] = None,
    remove_watermarks: bool = False,
    job_id: str = None,
    progress_callback=None,
) -> dict:
    """Approach-3: shared GPC/attrs → per-language skeleton → per-platform rewrite.

    Writes `product_assets` rows and returns debit units for successful combos.
    Watermark processing runs only when remove_watermarks=True.
    """
    from . import store_db
    from . import quota as quota_mod
    from .cultural_context import season_for_date, resolve_category, get_search_prefix

    platforms = [p.lower() for p in (platforms or ["google"])]
    languages = [l.upper() for l in (languages or ["US"])]
    valid = {"google", "meta", "tiktok"}
    platforms = [p for p in platforms if p in valid] or ["google"]

    store = store_db.get_store(store_id)
    if not store:
        raise ValueError(f"Store not found: {store_id}")

    load_gpc_taxonomy()

    products = []
    for pid in product_ids or []:
        p = store_db.get_product(pid)
        if p is None:
            # Resolve by shopify_product_id within store
            for cand in store_db.get_store_products(store_id):
                if cand.shopify_product_id == pid or cand.id == pid:
                    p = cand
                    break
        if p:
            products.append(p)

    ok_units = 0
    fail_units = 0
    debit_units = []  # (sku, platform, language)
    assets_written = 0
    done = 0
    total = len(products) * len(platforms) * len(languages)

    for product in products:
        try:
            raw_title = product.title or ""
            raw_desc = product.description or ""
            dirty = clean_dirty_words(raw_title, raw_desc)
            title = dirty["clean_title"] or raw_title
            desc = dirty["clean_description"] or raw_desc
            category = product.product_type or ""
            material = product.material or ""

            # ── Layer 1: shared once ──
            gpc = gpc_match(title=title, category=category, material=material)
            attr = infer_product_attributes(
                category_key=resolve_category(category, gpc.get("gpc_path", "")),
                gpc_path=gpc.get("gpc_path", ""),
                original_title=title,
                color="", material=material,
                search_prefix=get_search_prefix("US", category, gpc.get("gpc_path", "")),
                size="",
            )
            store_db.update_product_ai_result(
                product_id=product.id,
                optimized_title=title,
                gpc_code=gpc.get("gpc_code"),
                gpc_path=gpc.get("gpc_path"),
                gpc_confidence=gpc.get("confidence", 0),
                gpc_source=gpc.get("source"),
                gender=attr.get("gender"),
                age_group=attr.get("age_group"),
            )
            store_db.update_product(product.id, feed_enabled=1, ai_status="ready")

            # Optional watermark path
            if remove_watermarks and product.image_url:
                try:
                    from .image_processor import process_and_upload_image
                    process_and_upload_image(
                        product.image_url,
                        store_id=store_id,
                        product_id=product.id,
                        remove_wm=True,
                        white_bg=False,
                    )
                except Exception as e:
                    print(f"  [WARN] watermark skip {product.id[:12]}: {e}")

            # ── Layer 2: per language skeleton ──
            try:
                multi = optimize_multi_country(
                    original_title=title,
                    countries=languages,
                    description=desc,
                    original_category=category,
                    material=material,
                    gpc_path=gpc.get("gpc_path", ""),
                    target_season=season_for_date(),
                )
            except Exception as e:
                print(f"  [WARN] language pass failed {product.id[:12]}: {e}")
                multi = {
                    "optimized_titles": {lang: title for lang in languages},
                    "description_snippets": {lang: desc for lang in languages},
                    "ai_tags_by_lang": {lang: [] for lang in languages},
                }

            # ── Layer 3: per platform × language ──
            sku = product.shopify_product_id or product.id
            for lang in languages:
                skel_title = multi["optimized_titles"].get(lang, title)
                skel_desc = multi["description_snippets"].get(lang, desc)
                tags = multi.get("ai_tags_by_lang", {}).get(lang, [])
                for plat in platforms:
                    try:
                        rewritten = rewrite_for_platform(
                            title=skel_title,
                            description=skel_desc,
                            platform=plat,
                            language=lang,
                            tags=tags,
                        )
                        store_db.upsert_product_asset(
                            store_id=store_id,
                            product_id=product.id,
                            platform=plat,
                            language=lang,
                            title=rewritten["title"],
                            description=rewritten["description"],
                            tags=rewritten.get("tags") or [],
                        )
                        quota_mod.debit_quota(
                            store_id, plat, lang, job_id=job_id, sku=str(sku),
                        )
                        debit_units.append((str(sku), plat, lang))
                        ok_units += 1
                        assets_written += 1
                    except Exception as e:
                        print(f"  [ERROR] asset {plat}/{lang}: {e}")
                        fail_units += 1
                    done += 1
                    if progress_callback:
                        progress_callback(done, total)
        except Exception as e:
            print(f"  [ERROR] product {product.id[:12]}: {e}")
            fail_units += len(platforms) * len(languages)
            done += len(platforms) * len(languages)
            if progress_callback:
                progress_callback(done, total)

    return {
        "processed": len(products),
        "ok_units": ok_units,
        "fail_units": fail_units,
        "assets_written": assets_written,
        "debit_units": debit_units,
        "platforms": platforms,
        "languages": languages,
    }


# ─────────────────────────────────────────────────
# 材质推断 — 基于 GPC 品类 + 产品标题关键词
# ─────────────────────────────────────────────────

# GPC 代码 → 默认材质映射
_GPC_MATERIAL_MAP = {
    "4174": "Cotton",          # Jeans / 牛仔裤
    "2271": "Polyester",       # Dresses / 连衣裙
    "209": "Cotton",           # Socks / 袜子
    "5423": "Polyester",       # Jumpsuits / 连体衣
    "5598": "Polyester",       # Outerwear / 外套
    "6228": "Polyester",       # Skirts / 裙子
    "3913": "Polyester",       # Belts/Accessories
    "207": "Polyester",        # Shorts / 短裤
    "502999": "Polyester",     # Tops / 上衣
}

# 标题关键词 → 材质覆盖
_TITLE_MATERIAL_KEYWORDS = {
    "denim": "Denim", "jean": "Denim", "cotton": "Cotton",
    "silk": "Silk", "linen": "Linen", "wool": "Wool",
    "leather": "Leather", "polyester": "Polyester",
    "spandex": "Spandex", "nylon": "Nylon",
}


def _infer_material(gpc_code: str, title: str, existing_material: str) -> str:
    """推断材质：已有值 > 标题关键词 > GPC 默认值"""
    if existing_material:
        return existing_material
    title_lower = title.lower()
    for kw, mat in _TITLE_MATERIAL_KEYWORDS.items():
        if kw in title_lower:
            return mat
    return _GPC_MATERIAL_MAP.get(gpc_code, "")


# 尺码标准化映射
_SIZE_NORMALIZE = {
    "2XL": "XXL", "3XL": "XXXL",
    "2xl": "XXL", "3xl": "XXXL",
}

# 颜色标准化 — 非标准长句颜色值 → GMC 标准色
_COLOR_NORMALIZE = {
    "one pair of mixed colors": "Multicolor",
    "mixed colors": "Multicolor",
}


def _normalize_size(raw: str) -> str:
    """统一尺码：标准码保留；营销长句清空。"""
    if not raw:
        return ""
    s = raw.strip()
    s = _SIZE_NORMALIZE.get(s, s)
    # 营销长句 / 脏词尺码
    if len(s) > 24:
        return ""
    if re.search(r"[*\[\]【】]|anti-odor|breathable|nude|fits most|wedding", s, re.I):
        return ""
    # 允许多词标准尺码
    if re.match(
        r"^(XS|S|M|L|XL|XXL|XXXL|XXXXL|2XL|3XL|4XL|One Size|Free Size|"
        r"One size fits all|\d{1,3}(?:\.\d)?(?:\s?(?:cm|mm|in|inch))?|"
        r"[A-Za-z]{1,12}(?:\s*/\s*[A-Za-z0-9]{1,8})?)$",
        s,
        re.I,
    ):
        return s
    # 简单色码组合如 "Blue / S" 不应出现在 size 字段——若含空格且不像 One Size，丢弃
    if " " in s and not re.match(r"^One Size", s, re.I):
        # 允许 "US 8" / "EU 40"
        if re.match(r"^(US|EU|UK|CN)\s?\d+", s, re.I):
            return s
        return ""
    return s


def _normalize_color(raw: str) -> str:
    """标准化颜色值：长句描述 → GMC 标准色名"""
    if not raw:
        return ""
    lower = raw.strip().lower()
    if lower in _COLOR_NORMALIZE:
        return _COLOR_NORMALIZE[lower]
    # 过长颜色描述清空
    if len(raw.strip()) > 40:
        return ""
    return raw.strip()


# ─────────────────────────────────────────────────
# 品牌规范化 — 处理 1688 厂名、大牌敏感词、空品牌
# ─────────────────────────────────────────────────

# 大牌敏感词字典 — 触发时警告，防止 IP 封号
_SENSITIVE_BRANDS = {
    # 奢侈品
    "nike", "adidas", "gucci", "louis vuitton", "lv", "chanel", "prada",
    "hermes", "dior", "burbery", "versace", "fendi", "balenciaga",
    # 运动/潮牌
    "puma", "reebok", "new balance", "converse", "vans", "supreme",
    "off-white", "stussy", "champion", "north face", "patagonia",
    # 快时尚
    "zara", "h&m", "uniqlo", "shein", "temu",
    # 电子
    "apple", "samsung", "sony", "huawei", "xiaomi", "dyson",
    # 珠宝/手表
    "rolex", "cartier", "tiffany", "pandora", "swarovski",
}

# 中文厂名关键词
_FACTORY_KEYWORDS_ZH = ["厂", "公司", "批发", "经销", "商行", "工坊", "工作室", "经营部"]

# 拼音厂名特征词
_FACTORY_KEYWORDS_EN = ["factory", "manufacturer", "wholesale", "supplier", "industrial",
                        "trading", "import", "export", "co., ltd", "co.,ltd"]


def _is_shop_handle_brand(name: str) -> bool:
    """myshopify 子域 / 随机 handle 不能当品牌（会污染标题前缀）。"""
    if not name:
        return True
    n = name.strip()
    low = n.lower()
    if ".myshopify.com" in low or low.endswith(".com"):
        return True
    # qx2kd5-s7 这类无空格 handle
    if " " not in n and re.match(r"^[a-z0-9][a-z0-9\-]{3,40}$", low):
        # 含数字+连字符的商店 handle
        if re.search(r"\d", low) and "-" in low:
            return True
    return False


def _normalize_brand(brand: str, shop_name: str, default_brand: str = None) -> tuple[str, str]:
    """品牌规范化。

    Returns:
        (clean_brand, status) — status: "ok" | "replaced" | "sensitive_warning"
    """
    # 可用的店铺展示名：排除 myshopify handle
    clean_shop = ""
    if default_brand and not _is_shop_handle_brand(default_brand):
        clean_shop = default_brand.strip()
    elif shop_name and not _is_shop_handle_brand(shop_name):
        clean_shop = shop_name.strip()

    if not brand or not brand.strip():
        return clean_shop, "replaced" if clean_shop else "replaced"

    brand_stripped = brand.strip()
    brand_lower = brand_stripped.lower()

    # 1. 大牌敏感词检测 — 保留原值但警告
    if brand_lower in _SENSITIVE_BRANDS:
        return brand_stripped, "sensitive_warning"

    # 2. 中文厂名检测（含中文汉字）→ 替换
    if any(ord(c) > 0x4e00 for c in brand_stripped):
        return clean_shop, "replaced"

    # 3. 拼音/英文厂名检测 → 替换
    if any(kw in brand_lower for kw in _FACTORY_KEYWORDS_EN):
        return clean_shop, "replaced"

    # 4. 品牌本身就是店铺 handle → 清空，避免标题前缀污染
    if _is_shop_handle_brand(brand_stripped):
        return clean_shop, "replaced"

    # 5. 保留看起来像真实品牌的英文名（含空格或纯字母品牌）
    if re.search(r"[A-Za-z]", brand_stripped) and not _is_shop_handle_brand(brand_stripped):
        return brand_stripped, "ok"

    return clean_shop, "replaced"


# ─────────────────────────────────────────────────
# 变体图片智能映射 — 补救 1688 导入工具未关联变体图片的问题
# ─────────────────────────────────────────────────

def _fetch_shopify_product_images(shopify_domain: str, access_token: str,
                                   shopify_product_id: str) -> list[str]:
    """从 Shopify API 拉取产品的所有图片 URL（按上传顺序）"""
    import requests
    if not shopify_domain or not access_token or not shopify_product_id:
        return []
    try:
        url = f"https://{shopify_domain}/admin/api/2024-10/products/{shopify_product_id}.json"
        headers = {"X-Shopify-Access-Token": access_token}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            images = data.get("product", {}).get("images", [])
            return [img["src"] for img in images if img.get("src")]
    except Exception as e:
        print(f"  [Warn] 拉取 Shopify 图片失败: {e}")
    return []


def _build_color_image_map(colors: list[str], all_images: list[str]) -> dict[str, str]:
    """将颜色列表按顺序映射到图片列表

    假设：前 N 张图对应 N 个颜色（1688 导入工具的上传顺序），剩余为细节图。
    """
    if not colors or not all_images:
        return {}
    mapping = {}
    for i, color in enumerate(colors):
        if i < len(all_images):
            mapping[color] = all_images[i]
    return mapping


# ─────────────────────────────────────────────────
# 三段式流水线：段3 — Feed XML 生成（纯静态读取）
# ─────────────────────────────────────────────────

def generate_feed_for_store(store_id: str, countries: list[str] = None,
                            skip_out_of_stock: bool = False,
                            platforms: list[str] = None,
                            product_ids: list[str] = None) -> dict:
    """段3: Feed XML 生成 — 只读 feed_enabled=1 且 ai_status=ready 的产品

    不调用任何 AI，纯静态数据拼装，毫秒级完成。

    Args:
        store_id: 店铺 ID
        countries: 目标国家，默认从 feed_configs 读取
        skip_out_of_stock: True 时跳过库存=0的变体，不输出到 Feed
        platforms: 目标平台列表，可选值: ["google", "meta", "tiktok"]
                   默认只生成 Google Feed

    Returns:
        {"feed_urls": [...], "total_items": N}
    """
    from . import store_db
    from .config import FEEDS_DIR, PUBLIC_BASE_URL
    from .feed_generator import generate as generate_feed_xml
    from .multi_platform_feeds import (
        save_meta_feed, save_tiktok_feed, durable_feed_path, durable_feed_url,
    )

    store = store_db.get_store(store_id)
    if not store:
        raise ValueError(f"Store not found: {store_id}")

    # 确定目标国家
    if not countries:
        configs = store_db.get_store_feed_configs(store_id)
        countries = [fc.country for fc in configs] if configs else [DEFAULT_COUNTRY]

    # 确定目标平台（默认只生成 Google）
    if not platforms:
        platforms = ["google"]
    platforms = [p.lower() for p in platforms]
    valid_platforms = {"google", "meta", "tiktok"}
    platforms = [p for p in platforms if p in valid_platforms]
    if not platforms:
        platforms = ["google"]

    # 读取已处理的产品（feed_enabled=1, ai_status=ready）
    products = store_db.get_feed_products(store_id)
    if product_ids:
        allow = set(product_ids)
        products = [p for p in products if p.id in allow]
    if not products:
        print(f"[FeedGen] No feed-enabled products for store {store_id}")
        return {"feed_urls": [], "total_items": 0, "message": "No feed-enabled products"}

    print(f"\n[FeedGen] Generating feed for {store.shop_name} — {len(products)} products, {len(countries)} countries, platforms: {', '.join(platforms)}")

    feed_urls = []
    site_url = store.site_url or PUBLIC_BASE_URL
    public_base = PUBLIC_BASE_URL
    total_items = 0

    for country in countries:
        cu = country.upper()
        rows = []

        for p in products:
            # 获取变体
            variants = store_db.get_product_variants(p.id)
            if not variants:
                # 无变体，用产品本身作为单行
                variants_data = [{
                    "sku": p.shopify_product_id or p.id,
                    "title": "",
                    "color": "",
                    "size": "",
                    "price": 0,
                    "inventory": 0,
                    "image_url": p.image_url or "",
                }]
                additional_imgs = []
            else:
                variants_data = [
                    {
                        "sku": v.sku,
                        "title": v.title or "",
                        "color": v.color or "",
                        "size": v.size or "",
                        "price": v.price,
                        "inventory": v.inventory,
                        "image_url": v.image_url or p.image_url or "",
                    }
                    for v in variants
                ]

                # ── 变体图片补救：检测是否需要从 Shopify 拉取完整图片并映射 ──
                unique_imgs = set(vd["image_url"] for vd in variants_data if vd["image_url"])
                colors = []
                for vd in variants_data:
                    c = vd.get("color", "")
                    if c and c not in colors:
                        colors.append(c)

                additional_imgs = []
                # 回退获取 access_token：store DB > 环境变量
                shop_token = store.access_token or os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
                if len(unique_imgs) <= 1 and len(colors) > 1 and store.shopify_domain and shop_token:
                    # 所有变体共用同一张图 + 有多个颜色 → 需要补救
                    all_imgs = _fetch_shopify_product_images(
                        store.shopify_domain, shop_token, p.shopify_product_id
                    )
                    if len(all_imgs) > 1:
                        color_img_map = _build_color_image_map(colors, all_imgs)
                        # 更新变体的 image_url
                        for vd in variants_data:
                            c = vd.get("color", "")
                            if c in color_img_map:
                                vd["image_url"] = color_img_map[c]
                        # 剩余图片作为附加图片
                        color_count = len(colors)
                        additional_imgs = all_imgs[color_count:] if len(all_imgs) > color_count else []
                        print(f"  [ImageMap] {p.title[:30]}: {len(colors)}色 → {len(all_imgs)}图, 映射成功")

            # ── 图片 AI 处理：去水印/换白底 + R2 上传 ──
            from .config import IMAGE_AI_ENABLED, IMAGE_AI_REMOVE_WATERMARK, IMAGE_AI_WHITE_BACKGROUND, R2_ENABLED
            from .image_processor import needs_image_processing, process_and_upload_image

            if IMAGE_AI_ENABLED:
                # 收集需要处理的图片 URL
                urls_to_process = set()
                for vd in variants_data:
                    img_url = vd.get("image_url", "")
                    if img_url and needs_image_processing(img_url):
                        urls_to_process.add(img_url)

                # 批量处理 + 上传 R2
                processed_map = {}  # 原始URL → 处理后URL
                for img_url in urls_to_process:
                    result_url = process_and_upload_image(
                        img_url,
                        store_id=store_id,
                        product_id=p.id,
                        remove_wm=IMAGE_AI_REMOVE_WATERMARK,
                        white_bg=IMAGE_AI_WHITE_BACKGROUND,
                    )
                    if result_url:
                        processed_map[img_url] = result_url

                # 更新变体图片 URL
                if processed_map:
                    for vd in variants_data:
                        img_url = vd.get("image_url", "")
                        if img_url in processed_map:
                            vd["image_url"] = processed_map[img_url]
                    r2_status = " + R2" if R2_ENABLED else ""
                    print(f"  [ImageAI{r2_status}] {p.title[:30]}: 处理了 {len(processed_map)} 张图片")

            # 解析多语种标题（fallback）；platform assets applied below
            cleaned_title_dict = {}
            if p.cleaned_title:
                try:
                    cleaned_title_dict = json.loads(p.cleaned_title)
                except json.JSONDecodeError:
                    pass
            opt_title = cleaned_title_dict.get(cu, p.optimized_title or p.title)

            # 构建绝对 URL
            product_link = f"{site_url}/products/{p.handle}" if p.handle else f"{site_url}/products/{p.id}"

            for v_data in variants_data:
                variant_sku = v_data["sku"]
                # URL 参数中 SKU 不能含空格
                safe_sku = variant_sku.replace(" ", "-")
                variant_link = f"{product_link}?variant={safe_sku}"
                variant_image = v_data.get("image_url") or p.image_url or ""

                # 材质推断：已有值 > 标题关键词 > GPC 默认
                inferred_material = _infer_material(p.gpc_code or "", p.title or "", p.material or "")
                # 品牌规范化：中文厂名/拼音厂名/空品牌 → 店铺名，大牌检测警告
                clean_brand, brand_status = _normalize_brand(
                    p.brand, store.shop_name, store.default_brand
                )
                if brand_status == "sensitive_warning":
                    print(f"  [BrandWarn] 敏感品牌: {clean_brand} — 产品 {p.title[:30]}")
                elif brand_status == "replaced":
                    pass  # 静默替换，不输出日志

                rows.append({
                    "SKU": variant_sku,
                    "优化后标题": opt_title,
                    "标题": p.title or "",
                    "描述": p.description or "",
                    "GPC代码": p.gpc_code or "",
                    "GPC路径": p.gpc_path or "",
                    "材质": inferred_material,
                    "颜色": _normalize_color(v_data.get("color", "")),
                    "尺码": _normalize_size(v_data.get("size", "")),
                    "品牌": clean_brand,
                    "item_group_id": p.shopify_product_id or p.id,
                    "gender": p.gender or "unisex",
                    "age_group": p.age_group or "adult",
                    "identifier_exists": "no",
                    "gtin": "",
                    "价格": v_data.get("price", 0),
                    "库存": v_data.get("inventory", 0),
                    "图片链接": variant_image,
                    "附加图片": json.dumps(additional_imgs) if additional_imgs else (p.additional_images or ""),
                    "链接": variant_link,
                    "匹配置信度": p.gpc_confidence or 0,
                    "合规状态": "pass",
                    "违规详情": "0",
                    "ai_tags": "",
                    "description_snippet": "",
                    "水印检测": "OK",
                    "custom_label_0": "",
                    "custom_label_1": "",
                    "custom_label_2": "",
                    "custom_label_3": "",
                    "custom_label_4": "",
                    "_product_id": p.id,
                })

        if not rows:
            continue

        # Durable feeds: FEEDS_DIR/{store_id}/{platform}/{lang}.{xml|csv}
        for plat in platforms:
            plat_rows = []
            for row in rows:
                r = dict(row)
                asset = store_db.get_product_asset_by_key(
                    r.get("_product_id", ""), plat, cu,
                )
                if asset and asset.title:
                    r["优化后标题"] = asset.title
                    if asset.description:
                        r["描述"] = asset.description
                plat_rows.append(r)

            feed_path = durable_feed_path(FEEDS_DIR, store_id, plat, cu)
            if plat == "google":
                country_df = pd.DataFrame(plat_rows)
                xml = generate_feed_xml(country_df, cu, skip_out_of_stock=skip_out_of_stock)
                feed_path.parent.mkdir(parents=True, exist_ok=True)
                feed_path.write_text(xml, encoding="utf-8")
                item_count = xml.count("<item>")
            elif plat == "meta":
                item_count = save_meta_feed(
                    plat_rows, feed_path, store.shop_name or "", site_url, cu,
                )
            else:
                item_count = save_tiktok_feed(
                    plat_rows, feed_path, store.shop_name or "",
                )

            total_items += item_count
            feed_url = durable_feed_url(public_base, store_id, plat, cu)
            store_db.save_feed_file(
                store_id=store_id, country=cu, platform=plat,
                file_path=str(feed_path), feed_url=feed_url,
                item_count=item_count,
            )
            feed_urls.append({
                "platform": plat,
                "country": cu,
                "language": cu,
                "url": feed_url,
                "items": item_count,
            })
            print(f"  [{plat}/{cu}] Feed: {item_count} items → {feed_url}")

    print(f"[FeedGen] Total: {total_items} items across {len(feed_urls)} feeds\n")
    return {
        "feed_urls": feed_urls,
        "total_items": total_items,
        "products_used": len(products),
    }


# ─────────────────────────────────────────────────
# 店铺模式：从 DB 读取 → 清洗 → 持久化 Feed
# ─────────────────────────────────────────────────

def run_for_store(store_id: str, countries: list[str] = None,
                  force: bool = False, max_workers: int = None,
                  progress_callback=None) -> dict:
    """从 store_db 读取店铺产品 → 执行清洗流程 → 持久化 Feed XML

    Args:
        store_id: 店铺 ID
        countries: 目标国家列表，默认从 feed_configs 读取
        force: 跳过去重强制执行
        max_workers: 并行线程数
        progress_callback: 进度回调

    Returns:
        summary dict + feed_urls 列表
    """
    from . import store_db
    from .config import FEEDS_DIR

    # ── 1. 获取店铺信息 ──
    store = store_db.get_store(store_id)
    if not store:
        raise ValueError(f"Store not found: {store_id}")

    print(f"\n{'=' * 60}")
    print(f"  Store Pipeline: {store.shop_name or store.shopify_domain}")
    print(f"  Store ID: {store_id}")
    print(f"{'=' * 60}")

    # ── 2. 确定目标国家 ──
    if not countries:
        configs = store_db.get_store_feed_configs(store_id)
        if configs:
            countries = [fc.country for fc in configs]
        else:
            countries = [DEFAULT_COUNTRY]
            # 自动创建默认 Feed 配置
            for c in countries:
                store_db.upsert_feed_config(store_id, c)

    # ── 3. 从 DB 读取产品 ──
    products = store_db.get_store_products(store_id)
    if not products:
        print(f"  [WARN] No active products for store {store_id}")
        return {
            "status": "no_products", "store_id": store_id,
            "total_sku": 0, "countries": countries,
        }

    # 转换为 pipeline 标准格式
    products_data = []
    for p in products:
        variants = store_db.get_product_variants(p.id)
        # 取第一个变体的价格/库存作为主值（兼容单变体场景）
        main_price = variants[0].price if variants else 0
        main_inventory = variants[0].inventory if variants else 0
        main_sku = variants[0].sku if variants else p.id

        products_data.append({
            "SKU": main_sku,
            "标题": p.title or "",
            "描述": p.description or "",
            "分类": p.product_type or "",
            "品牌": p.brand or store.default_brand or "",
            "材质": p.material or "",
            "颜色": "",
            "尺码": "",
            "图片链接": p.image_url or "",
            "附加图片": p.additional_images or "",
            "价格": main_price,
            "库存": main_inventory,
            "链接": f"/products/{p.handle}" if p.handle else "",
            "_product_id": p.id,               # 内部引用
            "_shopify_product_id": p.shopify_product_id,
            "_existing_gpc_code": p.gpc_code,
            "_existing_gpc_path": p.gpc_path,
        })

    print(f"  Loaded {len(products_data)} products from DB")

    # ── 4. 确定 Feed 输出目录 ──
    feed_output_dir = str(FEEDS_DIR / store_id)

    # ── 5. 执行标准清洗流程 ──
    summary = run(
        countries=countries,
        force=force,
        max_workers=max_workers,
        progress_callback=progress_callback,
        products_data=products_data,
        feed_dir=feed_output_dir,
    )

    # ── 6. 后处理：回写 DB ──
    print(f"\n[Post] Saving results back to store_db...")

    # 6a: 记录生成的 Feed 文件
    feed_urls = []
    site_url = store.site_url or f"https://api.deltfu.com"
    for country in countries:
        cu = country.upper()
        feed_path = Path(feed_output_dir) / f"{cu.lower()}.xml"
        if feed_path.exists():
            feed_url = f"{site_url}/feeds/{store_id}/{cu.lower()}.xml"
            # 统计 variant 数量
            item_count = 0
            try:
                content = feed_path.read_text(encoding="utf-8")
                item_count = content.count("<entry>")  # Atom format
                if item_count == 0:
                    item_count = content.count("<item>")  # RSS format
            except Exception:
                pass

            store_db.save_feed_file(
                store_id=store_id, country=cu,
                file_path=str(feed_path), feed_url=feed_url,
                item_count=item_count,
            )
            feed_urls.append({"country": cu, "url": feed_url, "items": item_count})
            print(f"  [{cu}] Feed saved: {item_count} items → {feed_url}")

    summary["feed_urls"] = feed_urls
    summary["store_id"] = store_id

    print(f"\n{'=' * 60}")
    print(f"  Store Pipeline DONE — {store.shop_name or store.shopify_domain}")
    print(f"  Feeds: {len(feed_urls)} countries")
    for fu in feed_urls:
        print(f"    {fu['country']}: {fu['url']} ({fu['items']} items)")
    print(f"{'=' * 60}\n")

    return summary
