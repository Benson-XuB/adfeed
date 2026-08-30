import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adfeed.google_oauth import SCOPE_CONTENT, build_authorize_url, scopes_for_phase


def test_scopes_phase1_content_only():
    assert SCOPE_CONTENT in scopes_for_phase(ads=False)
    assert "adwords" not in scopes_for_phase(ads=False)


def test_scopes_phase2_includes_ads():
    s = scopes_for_phase(ads=True)
    assert "content" in s and "adwords" in s


def test_build_authorize_url_requires_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_REDIRECT_URI", raising=False)
    try:
        build_authorize_url(state="x")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


def test_build_authorize_url_ok(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://example.com/cb")
    url = build_authorize_url(state="store|mc", include_ads=False)
    assert "accounts.google.com" in url
    assert "cid" in url
