"""Google OAuth helpers for Merchant (content) + incremental Ads (adwords)."""

from __future__ import annotations

import os
from urllib.parse import urlencode

SCOPE_CONTENT = "https://www.googleapis.com/auth/content"
SCOPE_ADWORDS = "https://www.googleapis.com/auth/adwords"


def google_oauth_configured() -> bool:
    return bool(
        os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
        and os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
        and os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    )


def build_authorize_url(*, state: str, include_ads: bool = False) -> str:
    if not google_oauth_configured():
        raise RuntimeError("GOOGLE_OAUTH_* env not configured")
    scopes = [SCOPE_CONTENT]
    if include_ads:
        scopes.append(SCOPE_ADWORDS)
    params = {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"].strip(),
        "redirect_uri": os.environ["GOOGLE_OAUTH_REDIRECT_URI"].strip(),
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def scopes_for_phase(*, ads: bool) -> str:
    parts = [SCOPE_CONTENT]
    if ads:
        parts.append(SCOPE_ADWORDS)
    return " ".join(parts)
