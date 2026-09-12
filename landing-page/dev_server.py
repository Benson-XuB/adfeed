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


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Pass 3xx through to the browser (needed for Google OAuth start)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class LandingHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def translate_path(self, path: str) -> str:
        # Strip query/fragment like the parent handler expects a clean path segment.
        bare = path.split("?", 1)[0].split("#", 1)[0]
        if bare in ("/waitlist", "/waitlist/"):
            path = "/waitlist.html"
        elif bare in ("/tools", "/tools/"):
            path = "/tools/index.html"
        elif bare == "/tools/feed-checker":
            path = "/tools/feed-checker.html"
        elif bare == "/tools/google-issues":
            path = "/tools/google-issues.html"
        elif bare == "/tools/google-ads-monitor":
            path = "/tools/google-ads-monitor.html"
        elif bare in ("/guides", "/guides/"):
            path = "/guides/index.html"
        elif bare == "/guides/google-shopping-disapproved":
            path = "/guides/google-shopping-disapproved.html"
        elif bare == "/guides/google-shopping-feed-errors":
            path = "/guides/google-shopping-feed-errors.html"
        elif bare == "/guides/1688-google-shopping":
            path = "/guides/1688-google-shopping.html"
        elif bare == "/guides/1688-products-need-gtin":
            path = "/guides/1688-products-need-gtin.html"
        elif bare == "/guides/1688-supplier-brand-vs-google-shopping-brand":
            path = "/guides/1688-supplier-brand-vs-google-shopping-brand.html"
        elif bare.startswith("/lp-assets/"):
            path = "/assets/" + bare[len("/lp-assets/") :]
        return super().translate_path(path)

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self._proxy_api()
            return
        # Pretty URL without relying solely on translate_path query quirks
        bare = self.path.split("?", 1)[0].split("#", 1)[0]
        q = "?" + self.path.split("?", 1)[1] if "?" in self.path else ""
        if bare in ("/waitlist", "/waitlist/"):
            self.path = "/waitlist.html" + q
        elif bare in ("/tools", "/tools/"):
            self.path = "/tools/index.html" + q
        elif bare == "/tools/feed-checker":
            self.path = "/tools/feed-checker.html" + q
        elif bare == "/tools/google-issues":
            self.path = "/tools/google-issues.html" + q
        elif bare == "/tools/google-ads-monitor":
            self.path = "/tools/google-ads-monitor.html" + q
        elif bare in ("/guides", "/guides/"):
            self.path = "/guides/index.html" + q
        elif bare == "/guides/google-shopping-disapproved":
            self.path = "/guides/google-shopping-disapproved.html" + q
        elif bare == "/guides/google-shopping-feed-errors":
            self.path = "/guides/google-shopping-feed-errors.html" + q
        elif bare == "/guides/1688-google-shopping":
            self.path = "/guides/1688-google-shopping.html" + q
        elif bare == "/guides/1688-products-need-gtin":
            self.path = "/guides/1688-products-need-gtin.html" + q
        elif bare == "/guides/1688-supplier-brand-vs-google-shopping-brand":
            self.path = "/guides/1688-supplier-brand-vs-google-shopping-brand.html" + q
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
        cookie = self.headers.get("Cookie")
        if cookie:
            headers["Cookie"] = cookie

        req = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=self.command,
        )
        opener = urllib.request.build_opener(NoRedirectHandler)
        try:
            with opener.open(req, timeout=30) as resp:
                self._write_proxied(resp.status, resp.headers, resp.read())
        except urllib.error.HTTPError as err:
            # Includes 3xx when redirects are disabled — forward Location to browser.
            self._write_proxied(err.code, err.headers, err.read())
        except urllib.error.URLError as err:
            msg = f"API unreachable at {API_BASE}: {err.reason}"
            self.send_error(502, msg)

    def _write_proxied(self, status: int, headers, payload: bytes) -> None:  # noqa: ANN001
        self.send_response(status)
        skip = {"transfer-encoding", "connection", "content-encoding", "content-length"}
        for key, value in headers.items():
            if key.lower() in skip:
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)


def main() -> None:
    with ThreadingHTTPServer(("", PORT), LandingHandler) as httpd:
        print(f"Landing:  http://127.0.0.1:{PORT}/", flush=True)
        print(f"Waitlist: http://127.0.0.1:{PORT}/waitlist → /#waitlist", flush=True)
        print(f"Proxy:    /api/* → {API_BASE}", flush=True)
        print("Start FastAPI first: cd phase0 && .venv/bin/uvicorn adfeed.api:app --port 8000", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
