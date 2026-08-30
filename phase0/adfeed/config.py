"""AdFeed AI — Phase 0: 跨境广告数据洗白验证脚本"""

from dotenv import load_dotenv
load_dotenv()

from pathlib import Path

# ============================================
# 路径配置
# ============================================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
PROMPTS_DIR = BASE_DIR / "adfeed" / "prompts"

TAXONOMY_FILE = DATA_DIR / "taxonomy-with-ids.en-US.txt"
COMPLIANCE_RULES_FILE = DATA_DIR / "compliance_rules.json"

# ============================================
# API 配置 — 通义千问 (DashScope)
# ============================================
import os

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-plus")
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 600
LLM_MAX_RETRIES = 2
LLM_RETRY_DELAY_SECONDS = [1, 3]

# ============================================
# GPC 匹配配置
# ============================================
GPC_TOPK = 5
GPC_CONFIDENCE_THRESHOLD = 0.65

# ============================================
# 标题优化配置
# ============================================
TITLE_MAX_LENGTH = 150  # Google Shopping title hard limit
DESCRIPTION_MAX_LENGTH = 5000  # Google Shopping description hard limit
# Empty by default — field contract: no silent eprolo; App sets default_brand.
DEFAULT_STORE_BRAND = os.getenv("ADFEED_DEFAULT_BRAND", "")
DEFAULT_COUNTRY = "US"

# ============================================
# 图片 AI 处理配置
# ============================================
IMAGE_AI_ENABLED = os.getenv("IMAGE_AI_ENABLED", "false").lower() in ("true", "1", "yes")
IMAGE_AI_REMOVE_WATERMARK = True    # 去水印（中英文）
IMAGE_AI_WHITE_BACKGROUND = False   # 换白底（耗时较长，可选）
IMAGE_AI_CDN_BASE_URL = os.getenv("IMAGE_AI_CDN_BASE_URL", "")  # Cloudflare R2 URL
# Cap DashScope cleans per generate_feed_for_store job (cost control)
IMAGE_CLEAN_MAX_PER_JOB = int(os.getenv("IMAGE_CLEAN_MAX_PER_JOB", "20"))

# Cloudflare R2 配置
R2_ENABLED = os.getenv("R2_ENABLED", "false").lower() in ("true", "1", "yes")
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "adfeed-images")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")  # 自定义域名或 R2 公开 URL

# ============================================
# Shopify 配置
# ============================================
SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET", "")
SHOPIFY_REDIRECT_URI = os.getenv("SHOPIFY_REDIRECT_URI", "https://deltfu.com/api/shopify/callback")
SHOPIFY_SCOPES = "read_products,write_products,read_legal_policies"
# contextualPricing works with read_products on modern Admin API; merchants with
# Markets-only catalogs may need re-auth if GraphQL returns access errors.
SHOPIFY_API_VERSION = "2024-07"

# Google Merchant / Ads (read-only loop) — optional until post-review deploy
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = os.getenv(
    "GOOGLE_OAUTH_REDIRECT_URI",
    "https://deltfu.com/api/app/google/oauth/callback",
)
# Ads API developer token (required for product metrics sync; separate from OAuth)
GOOGLE_ADS_DEVELOPER_TOKEN = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
GOOGLE_ADS_LOGIN_CUSTOMER_ID = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
GOOGLE_ADS_API_VERSION = os.getenv("GOOGLE_ADS_API_VERSION", "v19")

# Meta Catalog (optional until post-review deploy)
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_OAUTH_REDIRECT_URI = os.getenv(
    "META_OAUTH_REDIRECT_URI",
    "https://deltfu.com/api/app/meta/oauth/callback",
)
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v21.0")

# TikTok Shop Partner (optional until post-review deploy)
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_OAUTH_REDIRECT_URI = os.getenv(
    "TIKTOK_OAUTH_REDIRECT_URI",
    "https://deltfu.com/api/app/tiktok/oauth/callback",
)
TIKTOK_API_BASE = os.getenv(
    "TIKTOK_API_BASE", "https://open-api.tiktokglobalshop.com"
)

# ============================================
# Mock 数据配置
# ============================================
MOCK_SKU_COUNT = 20
MOCK_OUTPUT_FILE = OUTPUT_DIR / "mock_products.xlsx"

# ============================================
# 输出配置
# ============================================
FEED_OUTPUT_XML = OUTPUT_DIR / "feed_us.xml"
COMPARISON_REPORT = OUTPUT_DIR / "comparison_report.xlsx"
SUMMARY_JSON = OUTPUT_DIR / "summary.json"
FEEDS_DIR = BASE_DIR / "feeds"  # 多店铺 Feed 持久化目录
PUBLIC_BASE_URL = os.getenv("ADFEED_PUBLIC_URL", "https://deltfu.com").rstrip("/")
WEB_SAAS_ENABLED = os.getenv("ADFEED_WEB_SAAS_ENABLED", "false").lower() in ("true", "1", "yes")


def ensure_dirs():
    """创建必要的输出目录"""
    for d in [DATA_DIR, OUTPUT_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def validate():
    """启动前校验配置完整性"""
    errors = []
    if not DASHSCOPE_API_KEY or DASHSCOPE_API_KEY == "sk-your-api-key-here":
        errors.append("请先在 .env 文件中设置有效的 DASHSCOPE_API_KEY")
    if not TAXONOMY_FILE.exists():
        errors.append(f"GPC taxonomy 文件未找到: {TAXONOMY_FILE}，请先运行下载脚本")
    if errors:
        raise RuntimeError("\n".join(errors))
