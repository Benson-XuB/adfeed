"""Landing page launch waitlist API."""
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def waitlist_client(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]

    from adfeed.db import init_db, list_waitlist_emails
    init_db()
    from adfeed.api import app

    return TestClient(app), list_waitlist_emails


def test_waitlist_signup_new_email(waitlist_client):
    client, list_emails = waitlist_client
    email = f"wait-{uuid.uuid4().hex[:8]}@example.com"

    res = client.post("/api/waitlist", json={"email": email, "source": "test"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["created"] is True
    assert data["status"] == "created"
    assert email in list_emails()


def test_waitlist_signup_duplicate_is_flagged(waitlist_client):
    client, list_emails = waitlist_client
    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"

    first = client.post("/api/waitlist", json={"email": email})
    second = client.post("/api/waitlist", json={"email": email.upper()})

    assert first.status_code == 200
    assert first.json()["status"] == "created"
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["status"] == "already_registered"
    assert "already" in second.json()["message"].lower()
    assert list_emails().count(email) == 1


def test_waitlist_rejects_invalid_email(waitlist_client):
    client, _ = waitlist_client
    res = client.post("/api/waitlist", json={"email": "not-an-email"})
    assert res.status_code == 422


def test_waitlist_rejects_email_with_spaces(waitlist_client):
    client, _ = waitlist_client
    res = client.post("/api/waitlist", json={"email": "bad address@example.com"})
    assert res.status_code == 422
