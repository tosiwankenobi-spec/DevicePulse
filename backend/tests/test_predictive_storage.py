"""DevicePulse backend — Predictive Storage tests.

Covers the roadmap ask: "At this rate you'll run out of space in 9 days"
with a one-tap fix, built as an upgrade to the existing (pre-session)
/forecast endpoint rather than a parallel feature:

  * GET /forecast and POST /forecast/quick-fix require auth (401)
  * daily_growth_gb is no longer a fixed constant — it's derived from how
    long it's been since the user's last cleanup (has_trend=False, default
    0.3 GB/day, when there's no cleanup history at all to project from;
    otherwise a value that climbs the longer junk has piled up, capped)
  * Smart Nudges gains a third, highest-priority "storage_forecast" nudge
    that only fires once there's real history (has_trend) AND the
    projection crosses FORECAST_ALERT_DAYS — never for a fresh user, so the
    existing "fresh user gets storage_reclaim" contract from Smart Nudges
    is untouched
  * The nudge outranks storage_reclaim when both qualify, and still
    respects the shared dismiss/cooldown + fallthrough mechanism
  * POST /forecast/quick-fix performs an immediate simulated cleanup sized
    to the same reclaimable estimate Smart Nudges uses, and returns a
    freshly-recomputed forecast that is meaningfully better (resets the
    idle clock, so daily_growth_gb drops back toward the baseline)
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


def _seed_user_and_session(prefix="PREDICT_"):
    user_id = f"{prefix}user_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}{uuid.uuid4().hex[:6]}@example.com"
    token = f"{prefix}tok_{uuid.uuid4().hex}"
    sid = uuid.uuid4().hex[:12]
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
    return user_id, token


def _cleanup_user(user_id, token):
    _db.user_sessions.delete_many({"session_token": token})
    _db.users.delete_many({"user_id": user_id})
    _db.cleanups.delete_many({"device_id": user_id})
    _db.nudge_dismissals.delete_many({"user_id": user_id})


def _insert_cleanup(user_id, hours_ago, reclaimed_mb=0.0):
    completed_at = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    _db.cleanups.insert_one({
        "id": str(uuid.uuid4()),
        "device_id": user_id,
        "categories": ["Junk files"],
        "reclaimed_mb": reclaimed_mb,
        "completed_at": completed_at,
    })


@pytest.fixture()
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture()
def seeded_user():
    uid, tok = _seed_user_and_session()
    yield {"user_id": uid, "token": tok}
    _cleanup_user(uid, tok)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- Auth gating ----------------
class TestPredictiveStorageRequiresAuth:
    def test_forecast_requires_auth(self, client):
        r = client.get(f"{API}/forecast")
        assert r.status_code == 401

    def test_quick_fix_requires_auth(self, client):
        r = client.post(f"{API}/forecast/quick-fix")
        assert r.status_code == 401


# ---------------- Dynamic growth rate ----------------
class TestForecastTrend:
    def test_fresh_user_has_no_trend_yet(self, client, seeded_user):
        r = client.get(f"{API}/forecast", headers=_auth(seeded_user["token"]))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["has_trend"] is False
        assert body["daily_growth_gb"] == 0.3
        assert body["days_until_full"] == 112  # 33.8 GB free / 0.3 GB/day

    def test_short_idle_gives_slow_growth(self, client, seeded_user):
        uid = seeded_user["user_id"]
        _insert_cleanup(uid, hours_ago=120)  # 5 days idle, 0 MB reclaimed
        r = client.get(f"{API}/forecast", headers=_auth(seeded_user["token"]))
        body = r.json()
        assert body["has_trend"] is True
        assert body["daily_growth_gb"] == 0.6
        assert body["days_until_full"] == 56

    def test_long_idle_gives_fast_growth_capped(self, client, seeded_user):
        uid = seeded_user["user_id"]
        _insert_cleanup(uid, hours_ago=2160)  # 90 days idle -> capped rate
        r = client.get(f"{API}/forecast", headers=_auth(seeded_user["token"]))
        body = r.json()
        assert body["has_trend"] is True
        assert body["daily_growth_gb"] == 3.0
        assert body["days_until_full"] == 11


# ---------------- Proactive nudge integration ----------------
class TestPredictiveStorageNudge:
    def test_fresh_user_still_gets_storage_reclaim_not_forecast(self, client, seeded_user):
        # No cleanup history at all -> has_trend is False, so the forecast
        # nudge can never fire for a brand-new user, no matter the (default)
        # days_until_full — preserves the existing Smart Nudges contract.
        r = client.get(f"{API}/nudges/active", headers=_auth(seeded_user["token"]))
        body = r.json()
        assert body is not None
        assert body["type"] == "storage_reclaim"

    def test_long_neglected_user_gets_forecast_nudge_as_top_priority(self, client, seeded_user):
        uid = seeded_user["user_id"]
        # Old enough to also trigger storage_reclaim (>=1500MB estimate) AND
        # cross FORECAST_ALERT_DAYS -- forecast must win (priority 0).
        _insert_cleanup(uid, hours_ago=900, reclaimed_mb=300.0)
        r = client.get(f"{API}/nudges/active", headers=_auth(seeded_user["token"]))
        body = r.json()
        assert body is not None
        assert body["type"] == "storage_forecast"
        assert "day" in body["message"]
        assert body["cta_route"] == "/forecast"

    def test_dismissing_forecast_nudge_falls_through_to_reclaim(self, client, seeded_user):
        uid = seeded_user["user_id"]
        _insert_cleanup(uid, hours_ago=900, reclaimed_mb=300.0)
        h = _auth(seeded_user["token"])
        client.post(f"{API}/nudges/storage_forecast/dismiss", headers=h)
        r = client.get(f"{API}/nudges/active", headers=h)
        body = r.json()
        assert body is not None
        assert body["type"] == "storage_reclaim"  # still qualifies, wasn't dismissed

    def test_moderate_idle_does_not_trigger_forecast(self, client, seeded_user):
        uid = seeded_user["user_id"]
        _insert_cleanup(uid, hours_ago=1)  # barely idle -> slow growth, plenty of days left
        r = client.get(f"{API}/nudges/active", headers=_auth(seeded_user["token"]))
        body = r.json()
        # Only the always-available security fallback should qualify here.
        assert body is not None
        assert body["type"] == "security"


# ---------------- One-tap fix ----------------
class TestQuickFix:
    def test_quick_fix_improves_the_forecast(self, client, seeded_user):
        uid = seeded_user["user_id"]
        _insert_cleanup(uid, hours_ago=900, reclaimed_mb=300.0)
        h = _auth(seeded_user["token"])

        before = client.get(f"{API}/forecast", headers=h).json()
        assert before["days_until_full"] == 13

        fix = client.post(f"{API}/forecast/quick-fix", headers=h)
        assert fix.status_code == 200, fix.text
        fix_body = fix.json()
        assert fix_body["reclaimed_mb"] == 3600.0  # capped estimate at 900h idle
        after = fix_body["forecast"]
        assert after["has_trend"] is True
        assert after["daily_growth_gb"] == 0.3  # idle clock reset by the new cleanup
        assert after["days_until_full"] > before["days_until_full"]
        assert after["days_until_full"] == 125

    def test_quick_fix_records_a_cleanup(self, client, seeded_user):
        uid = seeded_user["user_id"]
        h = _auth(seeded_user["token"])
        before_count = _db.cleanups.count_documents({"device_id": uid})
        client.post(f"{API}/forecast/quick-fix", headers=h)
        after_count = _db.cleanups.count_documents({"device_id": uid})
        assert after_count == before_count + 1
        doc = _db.cleanups.find_one({"device_id": uid}, sort=[("completed_at", -1)])
        assert doc["categories"] == ["Predictive quick fix"]
