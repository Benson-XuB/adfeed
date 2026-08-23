"""AdFeed AI — 商品图片 AI 处理模块

使用阿里云 DashScope 万相（wanx2.1-imageedit）模型处理 1688 来源的商品图片：
- 去除中文/英文水印和文字
- 替换背景为纯白色（Google Shopping 合规）
- 图片超分辨率增强

处理后图片保存到本地，后续可上传到 Cloudflare R2。
复用现有 DASHSCOPE_API_KEY，无需额外购买服务。

成本：0.14 元/张（约 $0.02/张）
"""

import os
import time
import hashlib
import requests
from pathlib import Path
from typing import Optional

from .config import DASHSCOPE_API_KEY

# ─────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────

# DashScope 万相图像编辑 API
_WANX_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/image-synthesis"
_WANX_TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

# 模型名称
_WANX_IMAGE_EDIT_MODEL = "wanx2.1-imageedit"

# 处理后的图片存储目录
BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_IMAGES_DIR = BASE_DIR / "data" / "processed_images"

# 轮询配置
_POLL_INTERVAL = 2  # 秒
_POLL_TIMEOUT = 60  # 秒

# 缓存：同一张图片不重复处理（URL hash → 处理后的本地路径）
_processed_cache: dict[str, str] = {}


# ─────────────────────────────────────────────────
# 核心 API 调用
# ─────────────────────────────────────────────────

def _submit_task(function: str, base_image_url: str,
                 prompt: str = "", mask_image_url: str = "") -> str:
    """提交万相图像编辑异步任务，返回 task_id"""
    headers = {
        "X-DashScope-Async": "enable",
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": _WANX_IMAGE_EDIT_MODEL,
        "input": {
            "function": function,
            "base_image_url": base_image_url,
        },
        "parameters": {"n": 1},
    }
    if prompt:
        body["input"]["prompt"] = prompt
    if mask_image_url:
        body["input"]["mask_image_url"] = mask_image_url

    resp = requests.post(_WANX_API_URL, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if "output" not in data:
        raise RuntimeError(f"万相 API 返回异常: {data}")

    task_id = data["output"]["task_id"]
    return task_id


def _poll_task(task_id: str) -> str:
    """轮询任务直到完成，返回结果图片 URL"""
    headers = {"Authorization": f"Bearer {DASHSCOPE_API_KEY}"}
    url = _WANX_TASK_URL.format(task_id=task_id)
    start = time.time()

    while time.time() - start < _POLL_TIMEOUT:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("output", {}).get("task_status", "")

        if status == "SUCCEEDED":
            results = data["output"].get("results", [])
            if results:
                return results[0].get("url", "")
            raise RuntimeError(f"任务成功但无结果: {data}")
        elif status == "FAILED":
            msg = data.get("output", {}).get("message", "未知错误")
            raise RuntimeError(f"万相任务失败: {msg}")
        elif status in ("PENDING", "RUNNING"):
            time.sleep(_POLL_INTERVAL)
        else:
            raise RuntimeError(f"未知任务状态: {status}")

    raise TimeoutError(f"万相任务超时 ({_POLL_TIMEOUT}s): {task_id}")


def _download_image(url: str, save_path: Path) -> Path:
    """下载图片到本地"""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(resp.content)
    return save_path


def _url_hash(url: str) -> str:
    """生成 URL 的短 hash 作为文件名"""
    return hashlib.md5(url.encode()).hexdigest()[:12]


# ─────────────────────────────────────────────────
# 公开接口
# ─────────────────────────────────────────────────

def remove_watermark(image_url: str, store_id: str = "",
                     product_id: str = "") -> Optional[str]:
    """去除图片中的文字水印（中英文）

    Args:
        image_url: 原始图片 URL（Shopify CDN 或任意可访问 URL）
        store_id: 店铺 ID（用于本地存储路径）
        product_id: 产品 ID（用于本地存储路径）

    Returns:
        处理后的本地文件路径，如果处理失败返回 None
    """
    if not image_url:
        return None

    # 缓存检查
    cache_key = f"wm:{image_url}"
    if cache_key in _processed_cache:
        return _processed_cache[cache_key]

    # 本地存储路径
    rel_dir = f"{store_id}/{product_id}" if store_id and product_id else "default"
    filename = f"{_url_hash(image_url)}_nowm.png"
    save_path = PROCESSED_IMAGES_DIR / rel_dir / filename

    if save_path.exists():
        _processed_cache[cache_key] = str(save_path)
        return str(save_path)

    try:
        print(f"  [ImageAI] 去水印: {image_url[:60]}...")
        task_id = _submit_task(
            function="remove_watermark",
            base_image_url=image_url,
            prompt="去除图像中的文字",
        )
        result_url = _poll_task(task_id)

        if result_url:
            _download_image(result_url, save_path)
            _processed_cache[cache_key] = str(save_path)
            print(f"  [ImageAI] ✅ 去水印完成 → {save_path.name}")
            return str(save_path)
        else:
            print(f"  [ImageAI] ❌ 去水印返回空 URL")
            return None

    except Exception as e:
        print(f"  [ImageAI] ❌ 去水印失败: {e}")
        return None


def replace_white_background(image_url: str, store_id: str = "",
                             product_id: str = "") -> Optional[str]:
    """将图片背景替换为纯白色

    Args:
        image_url: 原始图片 URL
        store_id: 店铺 ID
        product_id: 产品 ID

    Returns:
        处理后的本地文件路径，失败返回 None
    """
    if not image_url:
        return None

    cache_key = f"bg:{image_url}"
    if cache_key in _processed_cache:
        return _processed_cache[cache_key]

    rel_dir = f"{store_id}/{product_id}" if store_id and product_id else "default"
    filename = f"{_url_hash(image_url)}_whitebg.png"
    save_path = PROCESSED_IMAGES_DIR / rel_dir / filename

    if save_path.exists():
        _processed_cache[cache_key] = str(save_path)
        return str(save_path)

    try:
        print(f"  [ImageAI] 换白底: {image_url[:60]}...")
        task_id = _submit_task(
            function="description_edit",
            base_image_url=image_url,
            prompt="将图片背景替换为纯白色，保持产品主体不变",
        )
        result_url = _poll_task(task_id)

        if result_url:
            _download_image(result_url, save_path)
            _processed_cache[cache_key] = str(save_path)
            print(f"  [ImageAI] ✅ 换白底完成 → {save_path.name}")
            return str(save_path)
        else:
            print(f"  [ImageAI] ❌ 换白底返回空 URL")
            return None

    except Exception as e:
        print(f"  [ImageAI] ❌ 换白底失败: {e}")
        return None


def process_product_image(image_url: str, store_id: str = "",
                          product_id: str = "",
                          remove_wm: bool = True,
                          white_bg: bool = False) -> Optional[str]:
    """完整的产品图片处理流水线

    默认只去水印。换白底可选（耗时更长）。

    Args:
        image_url: 原始图片 URL
        store_id: 店铺 ID
        product_id: 产品 ID
        remove_wm: 是否去水印（默认 True）
        white_bg: 是否换白底（默认 False，因为可能影响产品真实感）

    Returns:
        最终处理后的本地文件路径，失败返回原始 URL
    """
    if not DASHSCOPE_API_KEY:
        return None

    current_url = image_url
    result_path = None

    # Step 1: 去水印
    if remove_wm:
        result = remove_watermark(current_url, store_id, product_id)
        if result:
            result_path = result
            # 如果后续要换白底，用处理后的结果继续
            # 但万相 API 需要公网 URL，所以本地文件无法直接传入
            # 这里简化处理：只执行第一步

    # Step 2: 换白底（需要公网 URL，暂不支持链式处理）
    # 如果后续接入 R2，可以先上传再去白底
    if white_bg and result_path is None:
        result = replace_white_background(current_url, store_id, product_id)
        if result:
            result_path = result

    return result_path


def batch_process_images(image_urls: list[str], store_id: str = "",
                         product_id: str = "",
                         remove_wm: bool = True,
                         white_bg: bool = False) -> dict[str, str]:
    """批量处理产品图片

    Args:
        image_urls: 原始图片 URL 列表
        store_id: 店铺 ID
        product_id: 产品 ID
        remove_wm: 是否去水印
        white_bg: 是否换白底

    Returns:
        {原始URL: 处理后本地路径} 映射
    """
    results = {}
    for url in image_urls:
        if not url:
            continue
        result = process_product_image(
            url, store_id, product_id,
            remove_wm=remove_wm, white_bg=white_bg,
        )
        results[url] = result or url  # 失败时保留原始 URL
    return results


# ─────────────────────────────────────────────────
# 检测函数：判断图片是否需要 AI 处理
# ─────────────────────────────────────────────────

# 批发/阿里系 CDN — 大概率含水印或中文贴纸
_RISKY_IMG_DOMAINS = (
    "alicdn.com",
    "1688.com",
    "taobao.com",
    "tmall.com",
    "img.alibaba.com",
    "cdn.temu.com",
    "img.dhgate.com",
    "cjdropshipping.com",
)
_RISKY_IMG_KEYWORDS = ("watermark", "水印")


def classify_image_risk(url: str) -> dict:
    """Domain/heuristic risk flag for feed main images.

    Returns:
        {"risky": bool, "reason": str}
    """
    if not url or not str(url).strip():
        return {"risky": False, "reason": "empty"}

    url_lower = str(url).lower()

    for d in _RISKY_IMG_DOMAINS:
        if d in url_lower:
            return {"risky": True, "reason": f"domain:{d}"}

    for kw in _RISKY_IMG_KEYWORDS:
        if kw in url_lower:
            return {"risky": True, "reason": f"keyword:{kw}"}

    # Shopify CDN is usually clean — never auto-risky
    if "cdn.shopify.com" in url_lower:
        return {"risky": False, "reason": "shopify_cdn"}

    return {"risky": False, "reason": ""}


def try_clean_main_image(
    image_url: str,
    *,
    sku: str = "",
    store_id: str = "",
    product_id: str = "",
) -> dict:
    """Attempt watermark removal; emit AUTOFIX IMG01 or WARN IMG02 (never FATAL).

    Monkeypatch ``process_product_image`` / ``remove_watermark`` in tests to
    avoid live DashScope calls.

    Returns:
        {"ok": bool, "url": str, "events": list[QualityEvent]}
    """
    from .feed_quality import QualityEvent

    events = []
    original = image_url or ""
    if not original:
        events.append(QualityEvent(
            "WARN", "IMG02", "g:image_link", sku or "",
            "Main image is empty — cannot remove watermark",
            suggestion="Upload at least one product image",
            before="", after="",
        ))
        return {"ok": False, "url": original, "events": events}

    try:
        result = process_product_image(
            original,
            store_id=store_id,
            product_id=product_id,
            remove_wm=True,
            white_bg=False,
        )
        if not result:
            # Fallback to remove_watermark alone (also monkeypatch target)
            result = remove_watermark(original, store_id=store_id, product_id=product_id)

        if result and result != original:
            # Prefer R2 public URL when configured
            try:
                from .config import R2_ENABLED
                if R2_ENABLED:
                    r2_url = upload_to_r2(result, store_id=store_id, product_id=product_id)
                    if r2_url:
                        result = r2_url
            except Exception:
                pass

            # Only accept public http(s) URLs — never AUTOFIX with local filesystem paths
            if not str(result).startswith("http"):
                events.append(QualityEvent(
                    "WARN", "IMG02", "g:image_link", sku or "",
                    "Main image may contain watermark — processing failed, replace manually",
                    suggestion="Replace with a clean product photo",
                    before=original, after=original,
                ))
                return {"ok": False, "url": original, "events": events}

            events.append(QualityEvent(
                "AUTOFIX", "IMG01", "g:image_link", sku or "",
                "Watermark removed and main image replaced",
                before=original, after=str(result),
            ))
            return {"ok": True, "url": str(result), "events": events}

        events.append(QualityEvent(
            "WARN", "IMG02", "g:image_link", sku or "",
            "Main image may contain watermark — processing failed, replace manually",
            suggestion="Replace with a clean product photo",
            before=original, after=original,
        ))
        return {"ok": False, "url": original, "events": events}

    except Exception as e:
        events.append(QualityEvent(
            "WARN", "IMG02", "g:image_link", sku or "",
            f"Main image may contain watermark — processing failed, replace manually ({e})",
            suggestion="Replace with a clean product photo",
            before=original, after=original,
        ))
        return {"ok": False, "url": original, "events": events}


def image_clean_quota_skip_event(sku: str = "", image_url: str = ""):
    """WARN when job image-clean quota is exhausted."""
    from .feed_quality import QualityEvent
    return QualityEvent(
        "WARN", "IMG02", "g:image_link", sku or "",
        "Skipped image processing (quota)",
        suggestion="Raise IMAGE_CLEAN_MAX_PER_JOB or generate in batches",
        before=image_url or "", after=image_url or "",
    )


def needs_image_processing(image_url: str) -> bool:
    """检测图片是否需要 AI 处理（委托 classify_image_risk）。"""
    return bool(classify_image_risk(image_url).get("risky"))


def get_processed_image_url(local_path: str, cdn_base_url: str = "") -> str:
    """将本地处理后的图片路径转换为可访问的 URL

    如果配置了 CDN（如 Cloudflare R2），返回 CDN URL。
    否则返回本地文件路径（开发环境用）。

    Args:
        local_path: 本地文件路径
        cdn_base_url: CDN 基础 URL（如 https://images.yourdomain.com）

    Returns:
        可访问的图片 URL
    """
    if not local_path:
        return ""

    if cdn_base_url:
        # 提取相对路径
        rel = Path(local_path).relative_to(PROCESSED_IMAGES_DIR)
        return f"{cdn_base_url}/{rel}"

    # 开发模式：返回本地路径
    return local_path


# ─────────────────────────────────────────────────
# Cloudflare R2 上传
# ─────────────────────────────────────────────────

def _get_r2_client():
    """获取 R2 S3 客户端"""
    from .config import R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY

    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        raise ValueError("R2 配置不完整，请检查 .env 中的 R2_* 配置项")

    import boto3

    endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def upload_to_r2(local_path: str, store_id: str = "", product_id: str = "") -> Optional[str]:
    """上传处理后的图片到 Cloudflare R2

    Args:
        local_path: 本地图片路径
        store_id: 店铺 ID（用于 R2 路径）
        product_id: 产品 ID（用于 R2 路径）

    Returns:
        R2 公开 URL，失败返回 None
    """
    from .config import R2_BUCKET_NAME, R2_PUBLIC_URL, R2_ENABLED

    if not R2_ENABLED:
        return None

    if not local_path or not Path(local_path).exists():
        return None

    try:
        s3 = _get_r2_client()

        # 构建 R2 对象 key
        filename = Path(local_path).name
        if store_id and product_id:
            key = f"{store_id}/{product_id}/{filename}"
        else:
            key = f"default/{filename}"

        # 检测 Content-Type
        suffix = Path(local_path).suffix.lower()
        content_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "image/png")

        # 上传
        print(f"  [R2] 上传: {key}")
        s3.upload_file(
            local_path,
            R2_BUCKET_NAME,
            key,
            ExtraArgs={"ContentType": content_type},
        )

        # 生成公开 URL
        if R2_PUBLIC_URL:
            public_url = f"{R2_PUBLIC_URL.rstrip('/')}/{key}"
        else:
            # 使用 R2 默认公开 URL 格式
            from .config import R2_ACCOUNT_ID
            public_url = f"https://pub-{R2_ACCOUNT_ID}.r2.dev/{key}"

        print(f"  [R2] ✅ 上传完成 → {public_url}")
        return public_url

    except Exception as e:
        print(f"  [R2] ❌ 上传失败: {e}")
        return None


def process_and_upload_image(image_url: str, store_id: str = "",
                             product_id: str = "",
                             remove_wm: bool = True,
                             white_bg: bool = False) -> Optional[str]:
    """处理图片并上传到 R2

    完整流程：下载 → 去水印 → 上传 R2 → 返回公开 URL

    Args:
        image_url: 原始图片 URL
        store_id: 店铺 ID
        product_id: 产品 ID
        remove_wm: 是否去水印
        white_bg: 是否换白底

    Returns:
        R2 公开 URL，失败返回原始 URL
    """
    from .config import R2_ENABLED

    # 先本地处理
    local_path = process_product_image(
        image_url, store_id, product_id,
        remove_wm=remove_wm, white_bg=white_bg,
    )

    if not local_path:
        return image_url  # 处理失败，返回原始 URL

    # 如果启用 R2，上传并返回公开 URL
    if R2_ENABLED:
        r2_url = upload_to_r2(local_path, store_id, product_id)
        if r2_url:
            return r2_url

    # R2 未启用或上传失败，返回本地路径
    return local_path

