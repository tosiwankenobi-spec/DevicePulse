"""DevicePulse backend — Smart Nudges tests.

Covers:
  * GET /nudges/active and POST /nudges/{type}/dismiss require auth (401)
  * At most one nudge is ever returned, picked by priority
  * storage_reclaim fires when the deterministic reclaimable-junk estimate
    crosses the threshold (a fresh/inactive user, or one who cleaned up long
    enough ago); a recent cleanup suppresses it
  * security is an always-available fallback under the app's fixed simulated
    baseline (security_status always contains "issue"), so it surfaces once
    storage_reclaim doesn't qualify
  * Dismissing a nudge type suppresses it (falls through to the next
    candidate, or to null if nothing else qualifies) without touching other
    still-valid candidates — this is the "not spam" mechanism
  * Dismissing an unknown nudge type is rejected (400)
  * Per-user isolation: one user's dismissal doesn't affect another user's
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


def _seed_user_and_session(prefix="NUDGE_", sid=None):
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
    _db.nudge_dismissals.delete_many({"user_id": user_id})


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


def _insert_cleanup(user_id, hours_ago):
    completed_at = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    _db.cleanups.insert_one({
        "id": str(uuid.uuid4()),
        "device_id": user_id,
        "categories": ["junk"],
        "reclaimed_mb": 300.0,
        "completed_at": completed_at,
    })


# ---------------- Auth gating ----------------
class TestNudgesRequireAuth:
    def test_get_active_requires_auth(self, client):
        r = client.get(f"{API}/nudges/active")
        assert r.status_code == 401

    def test_dismiss_requires_auth(self, client):
        r = client.post(f"{API}/nudges/storage_reclaim/dismiss")
        assert r.status_code == 401


# ---------------- Candidate selection ----------------
class TestActiveNudgeSelection:
    def test_fresh_user_gets_storage_reclaim(self, client, seeded_user):
        # Never cleaned up -> reclaimable estimate defaults to 1850MB (>=1500
        # threshold), and storage_reclaim outranks the always-true security
        # fallback.
        r = client.get(f"{API}/nudges/active", headers=_auth(seeded_user["token"]))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body is not None
        assert body["type"] == "storage_reclaim"
        assert "1.8 GB" in body["message"]
        assert body["cta_route"] == "/smart-scan"

    def test_recent_cleanup_falls_through_to_security(self, client, seeded_user):
        _insert_cleanup(seeded_user["user_id"], hours_ago=1)
        r = client.get(f"{API}/nudges/active", headers=_auth(seeded_user["token"]))
        body = r.json()
        assert body is not None
        assert body["type"] == "security"
        assert body["cta_route"] == "/insights"

    def test_old_enough_cleanup_still_triggers_reclaim(self, client, seeded_user):
        # 50h since last cleanup -> 50*35 = 1750MB, still over threshold.
        _insert_cleanup(seeded_user["user_id"], hours_ago=50)
        r = client.get(f"{API}/nudges/active", headers=_auth(seeded_user["token"]))
        body = r.json()
        assert body["type"] == "storage_reclaim"


# ---------------- Dismiss suppresses without spamming other candidates ----------------
class TestDismiss:
    def test_dismiss_unknown_type_rejected(self, client, seeded_user):
        r = client.post(f"{API}/nudges/not_a_real_type/dismiss", headers=_auth(seeded_user["token"]))
        assert r.status_code == 400

    def test_dismiss_falls_through_to_next_candidate(self, client, seeded_user):
        # Fresh user -> storage_reclaim would normally win.
        r = client.post(f"{API}/nudges/storage_reclaim/dismiss", headers=_auth(seeded_user["token"]))
        assert r.status_code == 200
        assert r.json() == {"dismissed": True, "type": "storage_reclaim"}

        r2 = client.get(f"{API}/nudges/active", headers=_auth(seeded_user["token"]))
        body = r2.json()
        assert body is not None
        assert body["type"] == "security"  # still qualifies, and wasn't dismissed

    def test_dismissing_all_candidates_returns_null(self, client, seeded_user):
        h = _auth(seeded_user["token"])
        client.post(f"{API}/nudges/storage_reclaim/dismiss", headers=h)
        client.post(f"{API}/nudges/security/dismiss", headers=h)
        r = client.get(f"{API}/nudges/active", headers=h)
        assert r.status_code == 200
        assert r.json() is None


# ---------------- Per-user isolation ----------------
class TestNudgeScoping:
    def test_dismissal_is_per_user(self, client):
        uid_a, _, tok_a, _ = _seed_user_and_session(prefix="NUDGEA_")
        uid_b, _, tok_b, _ = _seed_user_and_session(prefix="NUDGEB_")
        try:
            client.post(f"{API}/nudges/storage_reclaim/dismiss", headers=_auth(tok_a))
            body_a = client.get(f"{API}/nudges/active", headers=_auth(tok_a)).json()
            body_b = client.get(f"{API}/nudges/active", headers=_auth(tok_b)).json()
            assert body_a["type"] == "security"       # dismissed storage_reclaim for A
            assert body_b["type"] == "storage_reclaim"  # untouched for B
        finally:
            _cleanup_user(uid_a, tok_a)
            _cleanup_user(uid_b, tok_b)
