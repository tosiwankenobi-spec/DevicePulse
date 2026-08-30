"""DevicePulse backend — Daily Pulse Check tests.

Covers:
  * GET /pulse/daily requires auth (401 without a Bearer token)
  * Returns a card with a score/status/headline and caches it per user per day
  * Score computation: no cleanup history vs. a cleanup within the last 24h
  * delta is 0 with no prior-day data, and reflects the difference once a
    prior day's cached pulse exists
  * security_ok / storage_used_pct are derived consistently from the same
    baseline the rest of the app uses (_seed_health)
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


def _seed_user_and_session(prefix="PULSE_", sid=None):
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
class TestPulseRequiresAuth:
    def test_no_token_returns_401(self, client):
        r = client.get(f"{API}/pulse/daily")
        assert r.status_code == 401


# ---------------- Basic shape + caching ----------------
class TestPulseDailyCard:
    def test_returns_card_and_caches_per_day(self, client, seeded_user):
        r1 = client.get(f"{API}/pulse/daily", headers=_auth(seeded_user["token"]))
        assert r1.status_code == 200, r1.text
        card1 = r1.json()
        for key in ("date", "score", "status", "headline", "delta", "storage_used_pct", "battery_pct", "security_ok"):
            assert key in card1

        # Second call same day should return the identical cached card, not
        # recompute (score would otherwise drift based on "now").
        r2 = client.get(f"{API}/pulse/daily", headers=_auth(seeded_user["token"]))
        assert r2.status_code == 200
        assert r2.json() == card1

    def test_score_and_status_bounds(self, client, seeded_user):
        card = client.get(f"{API}/pulse/daily", headers=_auth(seeded_user["token"])).json()
        assert 40 <= card["score"] <= 97
        assert card["status"] in {"Excellent", "Good", "Needs Attention", "Poor"}

    def test_no_cleanup_history_is_needs_attention_with_no_delta(self, client, seeded_user):
        # Fresh user, never cleaned up: base(68) - 5 (never cleaned) = 63.
        card = client.get(f"{API}/pulse/daily", headers=_auth(seeded_user["token"])).json()
        assert card["score"] == 63
        assert card["status"] == "Needs Attention"
        assert card["delta"] == 0  # no prior-day pulse cached yet
        assert card["security_ok"] is False  # seed security_status contains "1 minor issue"
        assert card["storage_used_pct"] == 74  # round(94.2 / 128 * 100)


# ---------------- Score reacts to recent activity ----------------
class TestPulseRewardsRecentCleanup:
    def test_cleanup_within_24h_boosts_score_and_headline(self, client, seeded_user):
        _db.cleanups.insert_one({
            "id": str(uuid.uuid4()),
            "device_id": seeded_user["user_id"],
            "categories": ["junk"],
            "reclaimed_mb": 250.0,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        card = client.get(f"{API}/pulse/daily", headers=_auth(seeded_user["token"])).json()
        # base(68) + 6 (1 cleanup in last 7d) + 5 (cleaned in last 24h) = 79
        assert card["score"] == 79
        assert card["status"] == "Good"
        assert "cleaned up recently" in card["headline"].lower()


# ---------------- delta vs. yesterday ----------------
class TestPulseDelta:
    def test_delta_reflects_prior_day_score(self, client, seeded_user):
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        _db.pulse_daily.insert_one({
            "user_id": seeded_user["user_id"],
            "date": yesterday,
            "score": 50,
            "status": "Needs Attention",
            "headline": "seed",
            "delta": 0,
            "storage_used_pct": 74,
            "battery_pct": 54,
            "security_ok": False,
        })
        card = client.get(f"{API}/pulse/daily", headers=_auth(seeded_user["token"])).json()
        # No cleanups today -> score 63; yesterday seeded at 50 -> delta +13.
        assert card["score"] == 63
        assert card["delta"] == 13


# ---------------- Per-user isolation ----------------
class TestPulseScoping:
    def test_users_get_independent_cards(self, client):
        uid_a, _, tok_a, _ = _seed_user_and_session(prefix="PULSEA_")
        uid_b, _, tok_b, _ = _seed_user_and_session(prefix="PULSEB_")
        try:
            _db.cleanups.insert_one({
                "id": str(uuid.uuid4()),
                "device_id": uid_a,
                "categories": ["junk"],
                "reclaimed_mb": 100.0,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
            card_a = client.get(f"{API}/pulse/daily", headers=_auth(tok_a)).json()
            card_b = client.get(f"{API}/pulse/daily", headers=_auth(tok_b)).json()
            assert card_a["score"] != card_b["score"]
            assert card_b["score"] == 63  # user B has no cleanup history of their own
        finally:
            _cleanup_user(uid_a, tok_a)
            _cleanup_user(uid_b, tok_b)
