"""OAuth code exchange, refresh, state seal, token at-rest encoding."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _oauth_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://example.com/cb")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-for-google-oauth")


def test_seal_and_open_refresh_token_roundtrip():
    from adfeed.google_oauth import open_refresh_token, seal_refresh_token

    sealed = seal_refresh_token("rt-abc")
    assert sealed != "rt-abc"
    assert open_refresh_token(sealed) == "rt-abc"


def test_oauth_state_roundtrip():
    from adfeed.google_oauth import make_oauth_state, parse_oauth_state

    state = make_oauth_state("store-1", phase="mc")
    parsed = parse_oauth_state(state)
    assert parsed["store_id"] == "store-1"
    assert parsed["phase"] == "mc"


def test_parse_oauth_state_rejects_tamper():
    from adfeed.google_oauth import make_oauth_state, parse_oauth_state

    state = make_oauth_state("store-1", phase="mc")
    with pytest.raises(ValueError):
        parse_oauth_state(state[:-4] + "xxxx")


def test_exchange_code_returns_refresh_and_scopes():
    from adfeed.google_oauth import exchange_authorization_code

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "refresh_token": "rt-1",
        "access_token": "at-1",
        "scope": "https://www.googleapis.com/auth/content",
        "expires_in": 3600,
    }
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value.post.return_value = mock_resp
    mock_cm.__exit__.return_value = None

    with patch("adfeed.platforms.google.oauth.httpx.Client", return_value=mock_cm):
        out = exchange_authorization_code("code-xyz")
    assert out["refresh_token"] == "rt-1"
    assert out["access_token"] == "at-1"
    assert "content" in out["scope"]


def test_refresh_access_token():
    from adfeed.google_oauth import refresh_access_token

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "at-new",
        "expires_in": 3600,
        "scope": "https://www.googleapis.com/auth/content",
    }
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value.post.return_value = mock_resp
    mock_cm.__exit__.return_value = None

    with patch("adfeed.platforms.google.oauth.httpx.Client", return_value=mock_cm):
        out = refresh_access_token("rt-1")
    assert out["access_token"] == "at-new"
