#!/usr/bin/env python3
"""AdFeed AI — Web 服务入口

用法:
    python server.py                  # 默认端口 8000
    python server.py --port 8001      # 指定端口
    python server.py --reload         # 开发模式自动重载
"""
import sys, os
from pathlib import Path

# 确保 adfeed 包可导入
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--port" else 8000
    reload = "--reload" in sys.argv

    print(f"\n  AdFeed AI API Server")
    print(f"  ────────────────────")
    print(f"  http://localhost:{port}")
    print(f"  Docs: http://localhost:{port}/docs\n")

    uvicorn.run(
        "adfeed.api:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        log_level="info",
    )
