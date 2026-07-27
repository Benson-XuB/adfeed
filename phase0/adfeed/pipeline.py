"""AdFeed AI — 核心流水线编排器 v2.2（并行多国原生语种版本）

每条新品对目标国家逐一调用各自语种的 AI 生成原生标题。
集成：产品记忆库增量同步 + MD5 去重 + GPC 匹配 + 多国语标题生成 + 合规检查 + 多国 Feed XML 输出。
v2.2: ThreadPoolExecutor 并行处理行级 AI 调用，200 条从 10 分钟降到 ~25 秒。
"""

import json
import os
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

# ── GPC 匹配引擎（ChromaDB 优先，关键词回退） ──
_gpc_match_fn = None
_gpc_load_fn = None

try:
    from .gpc_vector_engine import match as _vmatch, load_taxonomy as _vload
    _vload()
    _gpc_match_fn = _vmatch
    _gpc_load_fn = _vload
    gpc_source = "chromadb_vector"
    print("[Pipeline] ChromaDB vector GPC engine loaded")
except Exception as e:
    from .gpc_matcher import match as _kmatch, load_taxonomy as _kload
    _gpc_match_fn = _kmatch
    _gpc_load_fn = _kload
    gpc_source = f"keyword (chromadb not available)"
    print(f"[Pipeline] GPC fallback: {gpc_source}")

gpc_match = _gpc_match_fn
load_gpc_taxonomy = _gpc_load_fn

from .title_optimizer import optimize_multi_country
from .compliance_engine import check_and_clean, infer_product_attributes, scan_image_watermarks, infer_energy_efficiency_class
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
        products_data: list[dict] = None) -> dict:
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
    print(f"\n[2/6] Init GPC engine ({gpc_source})...")
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
            "identifier_exists": "no", "gtin": "", "mpn": "",
            "additional_images": additional_images_raw,
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

    # ── Step 4: 生成输出文件（每个国家独立 Feed） ──
    print(f"\n[4/6] Generating feed XMLs...")

    for country in countries:
        # 为每个国家构建独立的 DataFrame
        rows_for_country = []
        for r in results:
            country_upper = country.upper()
            opt_title = r.get("optimized_titles", {}).get(country_upper, r.get("original_title", ""))
            desc_snippet = r.get("description_snippets", {}).get(country_upper, r.get("description", ""))
            ai_tags = r.get("ai_tags_by_lang", {}).get(country_upper, [])

            rows_for_country.append({
                "SKU": r["sku"],
                "优化后标题": opt_title,
                "标题": r["original_title"],
                "描述": desc_snippet,
                "GPC代码": r.get("gpc_code", ""),
                "GPC路径": r.get("gpc_path", ""),
                "材质": "",
                "颜色": "",
                "尺码": r.get("size", ""),
                "brand": r.get("brand", ""),
                "item_group_id": r.get("item_group_id", ""),
                "gender": r.get("gender", "unisex"),
                "age_group": r.get("age_group", "adult"),
                "identifier_exists": "no",
                "gtin": "",
                "匹配置信度": r.get("gpc_confidence", 0),
                "合规状态": str(r.get("compliance", {}).get(country_upper, {}).get("status", "pass")),
                "违规详情": str(r.get("compliance", {}).get(country_upper, {}).get("count", 0)),
                "ai_tags": ", ".join(ai_tags) if ai_tags else "",
                "description_snippet": desc_snippet,
                "水印检测": "OK" if r.get("watermark_clean", True) else "有水印",
            })

        country_df = pd.DataFrame(rows_for_country)
        feed_path = Path(str(FEED_OUTPUT_XML).replace("feed_us", f"feed_{country.lower()}"))
        xml = generate_feed_xml(country_df, country)
        feed_path.parent.mkdir(parents=True, exist_ok=True)
        feed_path.write_text(xml, encoding="utf-8")
        print(f"  [{country}] Feed XML: {feed_path.name} ({len(country_df)} SKU, {len(xml.encode('utf-8')):,} bytes)")

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
    if file_md5 and file_md5 != "mock_data":
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
