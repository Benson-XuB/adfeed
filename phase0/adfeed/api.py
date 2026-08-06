"""FastAPI 路由 — 上传、处理、导出、账户"""
import os, json, uuid, tempfile, asyncio, time, logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("adfeed-api")

from .db import (
    User, Job, get_user, list_jobs, get_job, create_job, update_job,
    get_user_by_email, increment_quota,
    get_shopify_connection, delete_shopify_connection,
)
from .auth import (
    create_jwt, decode_jwt, google_login, send_magic_link_email,
    verify_magic_link_and_login, get_google_auth_url,
)
from .config import DATA_DIR, OUTPUT_DIR
from .shopify_auth import require_store
from .store_db import Store as StoreModel


# ── App ──

app = FastAPI(title="AdFeed AI", version="0.3.0", request_max_size=200 * 1024 * 1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://deltfu.com",
        os.getenv("FRONTEND_URL", "http://localhost:3000"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed_ms}ms)")
    return response


@app.get("/api/health")
async def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


# ═══════════════ Shopify App APIs (session required) ═══════════════

@app.get("/api/app/billing/status")
async def app_billing_status(store: StoreModel = Depends(require_store)):
    """Return plan + quota for the authenticated shop."""
    return {
        "store_id": store.id,
        "shop_domain": store.shopify_domain,
        "shop_name": store.shop_name,
        "plan": store.plan,
        "billing_status": store.billing_status,
        "quota_total": store.quota_total,
        "quota_used": store.quota_used,
        "quota_remaining": store.quota_remaining,
        "subscription_id": store.subscription_id,
    }


@app.get("/api/app/products")
async def app_list_products(store: StoreModel = Depends(require_store)):
    """List products for the shop (live Shopify pull when token present)."""
    from . import store_db
    from .shopify_client import fetch_shopify_products

    products = []
    source = "cache"

    if store.access_token:
        try:
            data = await fetch_shopify_products(
                shop_domain=store.shopify_domain,
                access_token=store.access_token,
                limit=250,
            )
            products = [
                {
                    "id": str(p.get("shopify_id") or p.get("SKU") or ""),
                    "title": p.get("标题") or p.get("title") or "",
                    "image_url": p.get("图片链接") or p.get("image_url") or "",
                    "price": p.get("价格") or p.get("price") or 0,
                    "status": "active",
                }
                for p in data.get("products", [])
            ]
            source = "shopify"
        except Exception as e:
            logger.warning(f"Shopify product pull failed: {e}")

    if not products:
        cached = store_db.get_store_products(store.id)
        products = [
            {
                "id": p.shopify_product_id or p.id,
                "title": p.title,
                "image_url": p.image_url or "",
                "price": 0,
                "status": p.status,
            }
            for p in cached
        ]
        source = "cache"

    return {
        "store_id": store.id,
        "shop_domain": store.shopify_domain,
        "source": source,
        "products": products,
        "count": len(products),
    }


# ── Models ──

class MagicLinkRequest(BaseModel):
    email: EmailStr

class MagicLinkVerifyRequest(BaseModel):
    token: str

class GoogleCallbackRequest(BaseModel):
    code: str
    state: str = "login"


# ── Auth Dependency ──

async def current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    # 也支持 cookie
    token = None
    if credentials:
        token = credentials.credentials
    if not token:
        token = request.cookies.get("adfeed_token")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="token 已过期")

    user = get_user(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


# ═══════════════ Auth Routes ═══════════════

@app.get("/api/auth/google/url")
async def google_auth_url():
    return {"url": get_google_auth_url()}


@app.post("/api/auth/google/callback")
async def google_callback(body: GoogleCallbackRequest):
    result = await google_login(body.code)
    if not result:
        raise HTTPException(400, "Google 认证失败")

    user, token = result
    resp = JSONResponse({
        "token": token,
        "user": {
            "id": user.id, "email": user.email, "name": user.name,
            "avatar_url": user.avatar_url, "plan": user.plan,
            "quota_total": user.quota_total, "quota_used": user.quota_used,
        },
    })
    resp.set_cookie("adfeed_token", token, httponly=True, max_age=86400*7, samesite="lax")
    return resp


@app.post("/api/auth/magic-link")
async def request_magic_link(body: MagicLinkRequest):
    from .db import create_magic_link
    token = create_magic_link(body.email)
    await send_magic_link_email(body.email, token)
    return {"ok": True, "message": "Magic link 已发送至您的邮箱"}


@app.get("/api/auth/magic-link/verify")
async def verify_magic_link(token: str):
    result = verify_magic_link_and_login(token)
    if not result:
        raise HTTPException(400, "链接无效或已过期")

    user, jwt_token = result
    resp = JSONResponse({
        "token": jwt_token,
        "user": {
            "id": user.id, "email": user.email, "name": user.name,
            "avatar_url": user.avatar_url, "plan": user.plan,
            "quota_total": user.quota_total, "quota_used": user.quota_used,
        },
    })
    resp.set_cookie("adfeed_token", jwt_token, httponly=True, max_age=86400*7, samesite="lax")
    return resp


@app.get("/api/auth/me")
async def me(user: User = Depends(current_user)):
    return {
        "id": user.id, "email": user.email, "name": user.name,
        "avatar_url": user.avatar_url, "plan": user.plan,
        "quota_total": user.quota_total, "quota_used": user.quota_used,
        "quota_remaining": user.quota_remaining,
    }


# ═══════════════ Upload ═══════════════

UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".txt"}


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    countries: str = Form('["US"]'),
    user: User = Depends(current_user),
):
    # 校验扩展名
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件类型: {ext}。支持: {', '.join(ALLOWED_EXTENSIONS)}")

    # 流式保存文件（不一次性加载 200MB 到内存）
    file_id = str(uuid.uuid4())
    safe_name = f"{file_id}{ext}"
    file_path = UPLOAD_DIR / safe_name

    import hashlib
    h = hashlib.md5()
    t1 = time.time()
    bytes_total = 0
    with open(file_path, "wb") as f:
        while chunk := await file.read(4 * 1024 * 1024):  # 4MB chunks
            f.write(chunk)
            h.update(chunk)
            bytes_total += len(chunk)
    t2 = time.time()
    file_hash = h.hexdigest()
    logger.info(f"upload_file write_disk: {bytes_total/1024/1024:.1f} MB in {(t2-t1)*1000:.0f}ms ({bytes_total/(t2-t1)/1024/1024:.1f} MB/s)")

    # 校验 country_mask 格式
    try:
        countries_parsed = json.loads(countries)
    except json.JSONDecodeError:
        raise HTTPException(400, "countries 格式错误，应为 JSON 数组，如 [\"US\",\"DE\"]")

    # 创建任务，状态为 analyzing
    job = create_job(user.id, file.filename, json.dumps(countries_parsed), file_hash)

    # 后台线程分析文件（不阻塞上传响应）
    import threading
    threading.Thread(target=_analyze_upload, args=(job.id, str(file_path)), daemon=True).start()

    return {
        "job_id": job.id,
        "filename": file.filename,
        "countries": countries_parsed,
        "quota_remaining": user.quota_remaining,
        "quota_total": user.quota_total,
        "status": "analyzing",
    }


def _analyze_upload(job_id: str, file_path: str):
    """后台分析上传文件：统计行数 + 抓取预览（不阻塞上传响应）"""
    try:
        t0 = time.time()
        logger.info(f"_analyze_upload start: job={job_id[:8]}")
        total_rows, preview_rows = _fast_preview(file_path)
        update_job(job_id, status="uploaded", total_rows=total_rows,
                   preview_json=json.dumps(preview_rows[:10], ensure_ascii=False))
        logger.info(f"_analyze_upload done: {total_rows} rows in {(time.time()-t0)*1000:.0f}ms")
    except Exception as e:
        update_job(job_id, status="failed", error_msg=f"文件分析失败: {e}")


def _fast_preview(file_path: str) -> tuple[int, list[dict]]:
    """轻量预览：用 openpyxl read_only 只读前 10 行 + 统计总行数。
    201MB Excel 也能秒级完成。"""
    t0 = time.time()
    ext = Path(file_path).suffix.lower()
    try:
        if ext in (".xlsx",):
            import openpyxl
            logger.info(f"_fast_preview opening xlsx: {file_path}")
            t1 = time.time()
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            t2 = time.time()
            logger.info(f"_fast_preview xlsx open: {(t2-t1)*1000:.0f}ms")
            ws = wb.active
            header = None
            preview = []
            total = 0
            for row in ws.iter_rows(values_only=True):
                vals = [str(c) if c is not None else "" for c in row]
                if header is None:
                    header = [chr(65 + i) for i in range(len(vals))]
                    preview.append({header[i]: vals[i] for i in range(len(vals))})
                else:
                    if total < 10:
                        preview.append({header[i]: vals[i] for i in range(min(len(vals), len(header)))})
                total += 1
            wb.close()
            logger.info(f"_fast_preview xlsx done: {total-1} rows in {(time.time()-t0)*1000:.0f}ms total")
            return total - 1, preview[1:] if len(preview) > 1 else []
        elif ext in (".xls",):
            return _fast_preview_xls_or_csv(file_path, engine="xls")
        else:
            return _fast_preview_xls_or_csv(file_path, engine="csv")
    except Exception:
        return 0, []


def _fast_preview_xls_or_csv(file_path: str, engine: str = "csv") -> tuple[int, list[dict]]:
    if engine == "xls":
        import xlrd
        wb = xlrd.open_workbook(file_path)
        ws = wb.sheet_by_index(0)
        header = {chr(65 + ci): str(ws.cell_value(0, ci)).strip() for ci in range(ws.ncols)}
        preview = []
        for ri in range(1, min(ws.nrows, 11)):
            preview.append({chr(65 + ci): str(ws.cell_value(ri, ci)).strip() for ci in range(ws.ncols)})
        return ws.nrows - 1, preview
    else:
        import csv
        # 先数行数（只扫描不解析）
        with open(file_path, encoding="utf-8", errors="replace") as f:
            total = sum(1 for _ in f) - 1  # minus header
        # 再读前 10 行
        with open(file_path, encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header_row = next(reader, [])
            header = {chr(65 + i): header_row[i] for i in range(len(header_row))}
            preview = []
            for i, row in enumerate(reader):
                if i >= 10:
                    break
                preview.append({chr(65 + j): row[j] for j in range(min(len(row), len(header)))})
        return total, preview


# ═══════════════ Processing ═══════════════

async def _process_job(job_id: str, user_id: str, file_path: str, countries: list[str]):
    """后台处理任务"""
    t0 = time.time()
    logger.info(f"_process_job start: job={job_id[:8]}, file={os.path.basename(file_path)}")
    try:
        update_job(job_id, status="processing")
        user = get_user(user_id)
        job = get_job(job_id)
        file_size_mb = os.path.getsize(file_path) / 1024 / 1024 if os.path.exists(file_path) else 0
        logger.info(f"_process_job file_size={file_size_mb:.1f}MB job.total_rows={job.total_rows}")

        # 配额为 0 时直接拒绝
        if user.quota_remaining <= 0:
            update_job(job_id, status="failed", error_msg="Monthly quota exhausted. Please upgrade to continue.")
            return

        # 调用 pipeline（配额不足时自动截断）
        from .pipeline import run as pipeline_run
        processable = min(user.quota_remaining, job.total_rows)

        def progress_callback(done: int, total: int):
            update_job(job_id, done_rows=done, total_rows=total)

        t_pipeline = time.time()
        result = pipeline_run(excel_path=file_path, countries=countries,
                              max_rows=processable, progress_callback=progress_callback)
        logger.info(f"_process_job pipeline done in {(time.time()-t_pipeline)*1000:.0f}ms")

        ok_count = result.get("ai_full_clean", 0) + result.get("partial_reclean", 0)
        total_skus = result.get("total_sku", 0)
        done = ok_count + result.get("skipped_old", 0) + result.get("price_updated", 0)
        fail_count = total_skus - done

        # 复制 comparison report 到 job 专属文件，供结果页展示
        from shutil import copyfile
        from .config import COMPARISON_REPORT
        job_report = OUTPUT_DIR / f"job_{job_id[:8]}_report.xlsx"
        if COMPARISON_REPORT.exists():
            copyfile(str(COMPARISON_REPORT), str(job_report))

        increment_quota(user_id, ok_count)
        update_job(
            job_id,
            status="completed",
            done_rows=done,
            ok_rows=ok_count,
            fail_rows=max(0, fail_count),
            result_csv=str(job_report),
            truncated=job.total_rows > processable,
        )
    except Exception as e:
        update_job(job_id, status="failed", error_msg=str(e))


@app.post("/api/jobs/{job_id}/process")
async def start_process(
    job_id: str,
    user: User = Depends(current_user),
):
    job = get_job(job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(404, "任务不存在")
    if job.status != "uploaded":
        raise HTTPException(400, f"任务状态不可处理: {job.status}")

    countries = json.loads(job.country_mask)
    file_id = Path(job.filename).stem
    file_path = None
    for f in UPLOAD_DIR.iterdir():
        if f.name.startswith(job_id[:8]) or f.stem == file_id:
            file_path = str(f)
            break
    if not file_path:
        for f in UPLOAD_DIR.iterdir():
            file_path = str(f)
            break

    if not file_path:
        raise HTTPException(404, "上传文件未找到")

    import threading
    threading.Thread(target=_process_job, args=(job_id, user.id, file_path, countries), daemon=True).start()
    return {"job_id": job_id, "status": "processing"}


# ═══════════════ Jobs ═══════════════

@app.get("/api/jobs")
async def get_jobs(user: User = Depends(current_user), limit: int = 20):
    jobs = list_jobs(user.id, limit=limit)
    return [
        {
            "id": j.id, "filename": j.filename, "status": j.status,
            "total_rows": j.total_rows, "done_rows": j.done_rows,
            "ok_rows": j.ok_rows, "fail_rows": j.fail_rows,
            "progress_pct": j.progress_pct,
            "created_at": j.created_at,
        }
        for j in jobs
    ]


@app.get("/api/jobs/{job_id}")
async def get_job_detail(job_id: str, user: User = Depends(current_user)):
    job = get_job(job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(404, "任务不存在")

    preview_rows = []
    if job.preview_json:
        try:
            preview_rows = json.loads(job.preview_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": job.id, "filename": job.filename, "status": job.status,
        "total_rows": job.total_rows, "preview_rows": preview_rows,
        "done_rows": job.done_rows,
        "ok_rows": job.ok_rows, "fail_rows": job.fail_rows,
        "progress_pct": job.progress_pct,
        "truncated": job.truncated,
        "result_csv": job.result_csv,
        "error_msg": job.error_msg,
        "created_at": job.created_at, "updated_at": job.updated_at,
    }


@app.get("/api/jobs/{job_id}/results")
async def get_job_results(job_id: str, user: User = Depends(current_user)):
    """返回 job 的处理结果预览（前 20 条）"""
    import openpyxl
    job = get_job(job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(404, "任务不存在")
    if job.status != "completed":
        return {"rows": [], "message": "任务尚未完成"}

    report_path = Path(job.result_csv) if job.result_csv else None
    if not report_path or not report_path.exists():
        # 回退：尝试从 product_memory 获取最新结果
        from .product_memory import get_recent as get_recent_products
        rows = get_recent_products(limit=20)
        return {"rows": rows, "source": "product_memory"}

    try:
        wb = openpyxl.load_workbook(str(report_path), read_only=True, data_only=True)
        ws = wb.active
        rows = []
        headers = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            vals = [str(c) if c is not None else "" for c in row]
            if i == 0:
                headers = vals
            else:
                rows.append({headers[j]: vals[j] for j in range(min(len(vals), len(headers)))})
                if len(rows) >= 20:
                    break
        wb.close()
        return {"rows": rows, "source": "report", "total": len(rows)}
    except Exception:
        return {"rows": [], "error": "无法读取结果文件"}


# ═══════════════ Feed Export ═══════════════

@app.get("/api/feeds/{country}")
async def download_feed(country: str, user: User = Depends(current_user)):
    """从 product_memory 动态生成 GMC Feed XML 并返回"""
    from .feed_generator import generate_from_memory

    allowed = {"US", "DE", "FR", "ES", "IT"}
    country = country.upper()
    if country not in allowed:
        raise HTTPException(400, f"不支持的国家: {country}。支持: {', '.join(sorted(allowed))}")

    xml = generate_from_memory(country, user_id=user.id)
    return HTMLResponse(content=xml, media_type="application/xml",
                        headers={"Content-Disposition": f"attachment; filename=feed_{country.lower()}.xml"})


@app.get("/api/feeds")
async def list_feeds(user: User = Depends(current_user)):
    """列出可用的 Feed 文件"""
    feeds = []
    for country in ["US", "DE", "FR", "ES", "IT"]:
        feed_path = OUTPUT_DIR / f"feed_{country.lower()}.xml"
        if feed_path.exists():
            stat = feed_path.stat()
            feeds.append({
                "country": country,
                "size_bytes": stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "download_url": f"/api/feeds/{country}",
            })
    return {"feeds": feeds}


# ═══════════════ PayPal Subscription ═══════════════

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_PLAN_IDS = {
    "starter": os.getenv("PAYPAL_PLAN_ID_STARTER", ""),
    "growth":  os.getenv("PAYPAL_PLAN_ID_GROWTH", ""),
}

PLAN_QUOTAS = {"starter": 120, "growth": 400}


@app.get("/api/billing/plans")
async def get_paypal_config(user: User = Depends(current_user)):
    """返回 PayPal 配置 + 可选档位"""
    return {
        "client_id": PAYPAL_CLIENT_ID,
        "current_plan": user.plan,
        "plans": {
            plan: {"id": pid, "name": plan.capitalize(), "skus": PLAN_QUOTAS.get(plan, 100)}
            for plan, pid in PAYPAL_PLAN_IDS.items() if pid
        },
    }


@app.post("/api/billing/activate")
async def activate_subscription(
    body: dict,
    user: User = Depends(current_user),
):
    """PayPal 付款成功后激活订阅。
    
    body: {"paypal_subscription_id": "I-XXXX", "paypal_plan_id": "P-XXXX"}
    """
    sub_id = body.get("paypal_subscription_id", "")
    plan_id = body.get("paypal_plan_id", "")

    if not sub_id:
        raise HTTPException(400, "缺少 paypal_subscription_id")

    # 根据 plan_id 找到对应档位
    plan_name = None
    for plan, pid in PAYPAL_PLAN_IDS.items():
        if pid == plan_id:
            plan_name = plan
            break

    if not plan_name:
        raise HTTPException(400, f"未知的 plan_id: {plan_id}")

    from .db import update_user
    quota = PLAN_QUOTAS.get(plan_name, 100)
    update_user(user.id, plan=plan_name, quota_total=quota, stripe_subscription_id=sub_id)

    return {
        "ok": True,
        "plan": plan_name,
        "quota_total": quota,
    }


# ═══════════════ Shopify Integration ═══════════════

from .shopify_client import (
    get_shopify_auth_url, fetch_shopify_products, connect_shopify_store,
)


class ShopifyConnectBody(BaseModel):
    shop_domain: str
    code: str


class ShopifyProcessBody(BaseModel):
    product_ids: list[str]
    countries: list[str] = ["US"]


@app.get("/api/shopify/status")
async def shopify_status(user: User = Depends(current_user)):
    """查询用户是否已连接 Shopify"""
    conn = get_shopify_connection(user.id)
    if conn:
        return {
            "connected": True,
            "shop_domain": conn.shop_domain,
            "shop_name": conn.shop_name,
            "connected_at": conn.created_at,
        }
    return {"connected": False}


@app.get("/api/shopify/auth-url")
async def shopify_auth_url(shop: str = ""):
    """获取 Shopify OAuth 授权 URL"""
    if not shop:
        raise HTTPException(400, "请提供 Shopify 店铺域名，如 mystore")
    url = get_shopify_auth_url(shop)
    return {"url": url}


@app.get("/api/shopify/callback")
async def shopify_callback(shop: str = "", code: str = ""):
    """Shopify OAuth 回调 — 换 token 并存储"""
    if not shop or not code:
        raise HTTPException(400, "缺少 shop 或 code 参数")

    # 这里需要从 cookie 或 session 获取用户
    # 简化处理：要求前端在 callback 页面手动调用 /api/shopify/connect
    return {"shop": shop, "code": code, "message": "请使用前端完成连接"}


@app.post("/api/shopify/connect")
async def shopify_connect(body: ShopifyConnectBody, user: User = Depends(current_user)):
    """连接 Shopify 店铺（前端拿到 code 后调用）"""
    result = await connect_shopify_store(user.id, body.shop_domain, body.code)
    if not result:
        raise HTTPException(400, "Shopify 授权失败，请检查店铺域名和授权码")
    return result


@app.post("/api/shopify/disconnect")
async def shopify_disconnect(user: User = Depends(current_user)):
    """断开 Shopify 连接"""
    deleted = delete_shopify_connection(user.id)
    return {"ok": deleted}


@app.get("/api/shopify/products")
async def shopify_products(
    page_info: str = "",
    limit: int = 50,
    user: User = Depends(current_user),
):
    """拉取 Shopify 产品列表"""
    conn = get_shopify_connection(user.id)
    if not conn:
        raise HTTPException(400, "请先连接 Shopify 店铺")

    result = await fetch_shopify_products(
        shop_domain=conn.shop_domain,
        access_token=conn.access_token,
        limit=limit,
        page_info=page_info or None,
    )
    return result


@app.post("/api/shopify/process")
async def shopify_process(body: ShopifyProcessBody, user: User = Depends(current_user)):
    """选择 Shopify 产品 + 国家 → 启动 AI pipeline"""
    conn = get_shopify_connection(user.id)
    if not conn:
        raise HTTPException(400, "请先连接 Shopify 店铺")

    if not body.product_ids:
        raise HTTPException(400, "请至少选择一个产品")

    # 拉取选中产品的完整数据
    all_products = await fetch_shopify_products(
        shop_domain=conn.shop_domain,
        access_token=conn.access_token,
        limit=250,
    )

    # 过滤出用户选中的产品
    selected = [p for p in all_products["products"] if p["shopify_id"] in body.product_ids]
    if not selected:
        raise HTTPException(404, "未找到选中的产品")

    # 创建 job
    job = create_job(
        user.id,
        f"shopify_{conn.shop_name}_{len(selected)}_products",
        json.dumps(body.countries),
        f"shopify_{conn.shop_domain}",
    )

    # 后台线程处理
    import threading
    threading.Thread(
        target=_process_shopify_job,
        args=(job.id, user.id, selected, body.countries),
        daemon=True,
    ).start()

    return {"job_id": job.id, "status": "processing", "product_count": len(selected)}


def _process_shopify_job(job_id: str, user_id: str, products: list, countries: list):
    """后台处理 Shopify 产品 job"""
    from .pipeline import run as pipeline_run
    try:
        logger.info(f"Shopify job start: {job_id[:8]} ({len(products)} products, {countries})")
        update_job(job_id, status="processing")

        def progress_cb(done, total):
            update_job(job_id, done_rows=done, total_rows=total)

        result = pipeline_run(
            products_data=products,
            countries=countries,
            progress_callback=progress_cb,
        )

        update_job(job_id, status="completed", total_rows=result.get("total_sku", 0),
                   ok_rows=result.get("ai_full_clean", 0) + result.get("partial_reclean", 0))
        logger.info(f"Shopify job done: {job_id[:8]} — {result.get('total_sku', 0)} SKU")
    except Exception as e:
        logger.error(f"Shopify job failed: {job_id[:8]} — {e}")
        update_job(job_id, status="failed", error_msg=str(e))


# ═══════════════ Shopify Feed API (Plugin) ═══════════════

class ShopifyFeedRequest(BaseModel):
    product_ids: list[str]
    countries: list[str] = ["US"]
    shop_domain: str


@app.post("/api/shopify/feed")
async def shopify_generate_feed(body: ShopifyFeedRequest):
    """LEGACY — unauthenticated generate disabled. Use /api/app/generate with session."""
    raise HTTPException(
        410,
        "This endpoint is retired. Use authenticated /api/app/generate with a Shopify session token.",
    )


def _xml_to_csv(xml_path: Path, csv_path: Path):
    """将 Feed XML 转为 TSV（Google 标准 Tab-delimited 格式）"""
    import re
    content = xml_path.read_text(encoding="utf-8")
    items = re.findall(r'<item>(.*?)</item>', content, re.DOTALL)
    if not items:
        return

    # 提取所有 g: 命名空间字段
    fields = set()
    rows = []
    for item in items:
        row = {}
        # 普通字段
        for tag in ["id", "title", "description", "link", "image_link",
                    "price", "availability", "condition", "brand",
                    "gtin", "mpn", "identifier_exists"]:
            m = re.search(f'<g:{tag}>(.*?)</g:{tag}>', item)
            if m:
                row[tag] = m.group(1)
                fields.add(tag)
        # 可能重复的字段
        for tag in ["additional_image_link", "product_highlight"]:
            vals = re.findall(f'<g:{tag}>(.*?)</g:{tag}>', item)
            if vals:
                row[tag] = ",".join(vals)
                fields.add(tag)
        # 变体字段
        for tag in ["item_group_id", "color", "size", "size_system",
                    "gender", "age_group", "product_type"]:
            m = re.search(f'<g:{tag}>(.*?)</g:{tag}>', item)
            if m:
                row[tag] = m.group(1)
                fields.add(tag)
        # custom labels
        for i in range(5):
            tag = f"custom_label_{i}"
            m = re.search(f'<g:{tag}>(.*?)</g:{tag}>', item)
            if m:
                row[tag] = m.group(1)
                fields.add(tag)
        rows.append(row)

    # 写 TSV
    import csv
    ordered_fields = sorted(fields)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ordered_fields, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    logger.info(f"CSV generated: {csv_path} ({len(rows)} rows)")


@app.get("/api/shopify/feed/status")
async def shopify_feed_status(shop_domain: str = ""):
    """查询店铺 Feed 状态（URL、商品数、更新时间）"""
    from . import store_db

    if not shop_domain:
        raise HTTPException(400, "请提供 shop_domain")

    shop_domain = shop_domain.replace(".myshopify.com", "").strip() + ".myshopify.com"
    store = store_db.get_store_by_domain(shop_domain)
    if not store:
        return {"feeds": []}

    feed_files = store_db.list_store_feeds(store.id)
    feeds = []
    for ff in feed_files:
        feeds.append({
            "country": ff.country,
            "url": ff.feed_url,
            "csv_url": ff.feed_url.replace(".xml", ".csv"),
            "item_count": ff.item_count,
            "updated_at": ff.generated_at,
        })

    return {"feeds": feeds, "store_id": store.id}


# 静态文件服务：Feed XML/CSV 下载（带 Cache-Control 和 CORS 头）
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .config import FEEDS_DIR

FEEDS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/feeds/{store_id}/{filename}")
async def serve_feed_file(store_id: str, filename: str):
    """提供 Feed 文件下载，带正确的缓存和 CORS 头

    GMC 定期抓取此 URL，缓存 1 小时确保价格/库存及时更新。
    """
    file_path = FEEDS_DIR / store_id / filename
    if not file_path.exists():
        raise HTTPException(404, f"Feed 文件不存在: {filename}")

    # 确定内容类型
    if filename.endswith(".xml"):
        media_type = "application/xml"
    elif filename.endswith(".csv"):
        media_type = "text/csv"
    else:
        media_type = "application/octet-stream"

    response = FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )
    # GMC 建议短缓存（1小时），确保价格/库存及时更新
    response.headers["Cache-Control"] = "public, max-age=3600, must-revalidate"
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# 保留 StaticFiles 作为回退（处理其他路径）
app.mount("/feeds-static", StaticFiles(directory=str(FEEDS_DIR)), name="feeds")


# ═══════════════ Health ═══════════════

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.3.0"}
