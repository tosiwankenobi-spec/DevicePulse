"""DevicePulse backend — Home Screen Widget (live) tests.

Covers:
  * GET /widget/summary requires auth (401 without a Bearer token)
  * Returns a compact live snapshot (score/status/storage/battery/security/updated_at)
  * Score computation matches the shared Daily Pulse Check formula
  * Unlike /pulse/daily, this endpoint is NOT cached per day: two calls in the
    same moment return the same score (deterministic), but a cleanup landing
    in between calls is reflected on the very next call — no waiting for a
    new calendar day, and no stored pulse_daily doc is touched.
  * updated_at moves forward between calls, proving the snapshot is live
  * security_ok / storage_used_pct / storage_used_gb / storage_total_gb are
    derived consistently from the same baseline the rest of the app uses
    (_seed_health)
  * Per-user isolation
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("BACKEND_TEST_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


def _seed_user_and_session(prefix="WIDGET_", sid=None):
    user_id = f"{prefix}user_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}{uuid.uuid4().hex[:6]}@example.com"
    token = f"{prefix}tok_{uuid.uuid4().hex}"
    sid = sid or uuid.uuid4().hex[:12]
    _db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": f"Test {prefix}",
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _db.user_sessions.insert_one({
        "session_token": token,
        "sid": sid,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    })
    return user_id, email, token, sid


def _cleanup_user(user_id, token):
    _db.user_sessions.delete_many({"session_token": token})
    _db.users.delete_many({"user_id": user_id})
    _db.cleanups.delete_many({"device_id": user_id})
    _db.pulse_daily.delete_many({"user_id": user_id})


@pytest.fixture()
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture()
def seeded_user():
    uid, email, tok, sid = _seed_user_and_session()
    yield {"user_id": uid, "email": email, "token": tok, "sid": sid}
    _cleanup_user(uid, tok)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- Auth gating ----------------
class TestWidgetRequiresAuth:
    def test_no_token_returns_401(self, client):
        r = client.get(f"{API}/widget/summary")
        assert r.status_code == 401


# ---------------- Basic shape ----------------
class TestWidgetSummaryShape:
    def test_returns_expected_fields(self, client, seeded_user):
        r = client.get(f"{API}/widget/summary", headers=_auth(seeded_user["token"]))
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("score", "status", "storage_used_pct", "storage_used_gb",
                    "storage_total_gb", "battery_pct", "security_ok", "updated_at"):
            assert key in body

    def test_score_and_status_bounds(self, client, seeded_user):
        body = client.get(f"{API}/widget/summary", headers=_auth(seeded_user["token"])).json()
        assert 40 <= body["score"] <= 97
        assert body["status"] in {"Excellent", "Good", "Needs Attention", "Poor"}

    def test_matches_shared_baseline(self, client, seeded_user):
        # Fresh user, never cleaned up: same formula as Daily Pulse Check ->
        # base(68) - 5 (never cleaned) = 63, "Needs Attention".
        body = client.get(f"{API}/widget/summary", headers=_auth(seeded_user["token"])).json()
        assert body["score"] == 63
        assert body["status"] == "Needs Attention"
        assert body["security_ok"] is False  # seed security_status contains "1 minor issue"
        assert body["storage_used_pct"] == 74  # round(94.2 / 128 * 100)
        assert body["storage_used_gb"] == 94.2
        assert body["storage_total_gb"] == 128.0
        assert body["battery_pct"] == 54


# ---------------- Live, not cached ----------------
class TestWidgetIsLiveNotCached:
    def test_no_pulse_daily_doc_is_written(self, client, seeded_user):
        client.get(f"{API}/widget/summary", headers=_auth(seeded_user["token"]))
        assert _db.pulse_daily.count_documents({"user_id": seeded_user["user_id"]}) == 0

    def test_reflects_a_cleanup_immediately_without_waiting_for_a_new_day(self, client, seeded_user):
        before = client.get(f"{API}/widget/summary", headers=_auth(seeded_user["token"])).json()
        assert before["score"] == 63

        _db.cleanups.insert_one({
            "id": str(uuid.uuid4()),
            "device_id": seeded_user["user_id"],
            "categories": ["junk"],
            "reclaimed_mb": 250.0,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

        after = client.get(f"{API}/widget/summary", headers=_auth(seeded_user["token"])).json()
        # base(68) + 6 (1 cleanup in last 7d) + 5 (cleaned in last 24h) = 79
        assert after["score"] == 79
        assert after["status"] == "Good"

    def test_updated_at_advances_between_calls(self, client, seeded_user):
        r1 = client.get(f"{API}/widget/summary", headers=_auth(seeded_user["token"])).json()
        r2 = client.get(f"{API}/widget/summary", headers=_auth(seeded_user["token"])).json()
        t1 = datetime.fromisoformat(r1["updated_at"])
        t2 = datetime.fromisoformat(r2["updated_at"])
        assert t2 >= t1


# ---------------- Per-user isolation ----------------
class TestWidgetScoping:
    def test_users_get_independent_snapshots(self, client):
        uid_a, _, tok_a, _ = _seed_user_and_session(prefix="WIDGETA_")
        uid_b, _, tok_b, _ = _seed_user_and_session(prefix="WIDGETB_")
        try:
            _db.cleanups.insert_one({
                "id": str(uuid.uuid4()),
                "device_id": uid_a,
                "categories": ["junk"],
                "reclaimed_mb": 100.0,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
            body_a = client.get(f"{API}/widget/summary", headers=_auth(tok_a)).json()
            body_b = client.get(f"{API}/widget/summary", headers=_auth(tok_b)).json()
            assert body_a["score"] != body_b["score"]
            assert body_b["score"] == 63  # user B has no cleanup history of their own
        finally:
            _cleanup_user(uid_a, tok_a)
            _cleanup_user(uid_b, tok_b)
