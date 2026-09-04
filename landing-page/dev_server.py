#!/usr/bin/env python3
"""Local landing preview: static files + /api/* proxy to FastAPI (like nginx)."""
from __future__ import annotations

import http.server
import os
import socketserver
import urllib.error
import urllib.request
from pathlib import Path

PORT = int(os.environ.get("LANDING_PORT", "8765"))
API_BASE = os.environ.get("ADFEED_API_URL", "http://127.0.0.1:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Serve video/static and API proxy concurrently (plain TCPServer blocks)."""

    daemon_threads = True
    allow_reuse_address = True


class LandingHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def translate_path(self, path: str) -> str:
        if path.startswith("/lp-assets/"):
            path = "/assets/" + path[len("/lp-assets/") :]
        return super().translate_path(path)

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self._proxy_api()
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path.startswith("/api/"):
            self._proxy_api()
            return
        self.send_error(501, "Unsupported method ('POST')")

    def _proxy_api(self) -> None:
        url = f"{API_BASE}{self.path}"
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        headers: dict[str, str] = {}
        content_type = self.headers.get("Content-Type")
        if content_type:
            headers["Content-Type"] = content_type

        req = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=self.command,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read()
                self.send_response(resp.status)
                for key, value in resp.headers.items():
                    if key.lower() not in ("transfer-encoding", "connection", "content-encoding"):
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as err:
            payload = err.read()
            self.send_response(err.code)
            self.send_header("Content-Type", err.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except urllib.error.URLError as err:
            msg = f"API unreachable at {API_BASE}: {err.reason}"
            self.send_error(502, msg)


def main() -> None:
    with ThreadingHTTPServer(("", PORT), LandingHandler) as httpd:
        print(f"Landing: http://127.0.0.1:{PORT}/", flush=True)
        print(f"Proxy:   /api/* → {API_BASE}", flush=True)
        print("Start FastAPI first: cd phase0 && .venv/bin/uvicorn adfeed.api:app --port 8000", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
