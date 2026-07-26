"""FastAPI 路由 — 上传、处理、导出、账户"""
import os, json, uuid, tempfile, asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from .db import (
    User, Job, get_user, list_jobs, get_job, create_job, update_job,
    get_user_by_email, increment_quota,
)
from .auth import (
    create_jwt, decode_jwt, google_login, send_magic_link_email,
    verify_magic_link_and_login, get_google_auth_url,
)
from .config import DATA_DIR, OUTPUT_DIR


# ── App ──

app = FastAPI(title="AdFeed AI", version="0.3.0", request_max_size=50 * 1024 * 1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        os.getenv("FRONTEND_URL", "http://localhost:3000"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


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

    # 保存文件
    file_id = str(uuid.uuid4())
    safe_name = f"{file_id}{ext}"
    file_path = UPLOAD_DIR / safe_name

    content = await file.read()
    file_path.write_bytes(content)

    # 校验 country_mask 格式
    try:
        countries_parsed = json.loads(countries)
    except json.JSONDecodeError:
        raise HTTPException(400, "countries 格式错误，应为 JSON 数组，如 [\"US\",\"DE\"]")

    # 计算 file hash
    import hashlib
    file_hash = hashlib.md5(content).hexdigest()

    # 创建任务
    job = create_job(user.id, file.filename, json.dumps(countries_parsed), file_hash)

    # 尝试用 _ingest_universal 解析文件，返回预览
    import importlib.util, importlib
    # 动态导入 _ingest_universal.py（不在 adfeed 包内）
    ingest_path = Path(__file__).resolve().parent.parent / "_ingest_universal.py"
    mod_name = f"_ingest_universal_{file_id[:8]}"
    spec = importlib.util.spec_from_file_location(mod_name, ingest_path)
    ingest_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ingest_mod)
    raw_rows = ingest_mod.read_any(str(file_path))
    total_rows = len(raw_rows) - 1 if raw_rows else 0
    preview_rows = []
    for r in raw_rows[1:11]:
        preview_rows.append({
            col: r.get(col, "") for col in (raw_rows[0] if raw_rows else {})
        })

    update_job(job.id, total_rows=total_rows)

    return {
        "job_id": job.id,
        "filename": file.filename,
        "total_rows": total_rows,
        "preview_rows": preview_rows[:10],
        "countries": countries_parsed,
    }


# ═══════════════ Processing ═══════════════

async def _process_job(job_id: str, user_id: str, file_path: str, countries: list[str]):
    """后台处理任务"""
    try:
        update_job(job_id, status="processing")
        user = get_user(user_id)

        # 检查配额
        job = get_job(job_id)
        if user.quota_remaining < job.total_rows:
            update_job(job_id, status="failed", error_msg=f"配额不足 (剩余 {user.quota_remaining}, 需要 {job.total_rows})")
            return

        # 调用 pipeline
        from .pipeline import run as pipeline_run
        result = pipeline_run(excel_path=file_path, countries=countries)

        ok_count = result.get("optimized", 0)
        fail_count = result.get("total_skus", 0) - ok_count

        increment_quota(user_id, ok_count)
        update_job(
            job_id,
            status="completed",
            done_rows=result.get("total_skus", 0),
            ok_rows=ok_count,
            fail_rows=max(0, fail_count),
            result_csv=str(OUTPUT_DIR / "summary.json"),
        )
    except Exception as e:
        update_job(job_id, status="failed", error_msg=str(e))


@app.post("/api/jobs/{job_id}/process")
async def start_process(
    job_id: str,
    background_tasks: BackgroundTasks,
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

    background_tasks.add_task(_process_job, job_id, user.id, file_path, countries)
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
    return {
        "id": job.id, "filename": job.filename, "status": job.status,
        "total_rows": job.total_rows, "done_rows": job.done_rows,
        "ok_rows": job.ok_rows, "fail_rows": job.fail_rows,
        "progress_pct": job.progress_pct,
        "error_msg": job.error_msg,
        "created_at": job.created_at, "updated_at": job.updated_at,
    }


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


# ═══════════════ Health ═══════════════

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.3.0"}
