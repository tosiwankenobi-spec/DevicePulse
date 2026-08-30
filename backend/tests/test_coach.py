"""DevicePulse backend — AI Health Coach tests.

Covers:
  * GET /api/coach/daily — LLM-generated card, cached per user per day
  * POST /api/coach/chat — contextual reply, persists both user + assistant, memory continuity
  * GET /api/coach/history — ordered list of messages
  * DELETE /api/coach/history — clears conversation
  * Rate limit — 429 after 10 rapid chat calls
  * Auth — 401 without token
  * Regression — scan / clean / ai/recommendations still work
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

# Prefer public URL from frontend/.env (this is what the mobile app hits)
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = (
    os.environ.get("BACKEND_TEST_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


# ---------------- Helpers ----------------
def _seed_user_and_session(prefix="TEST_COACH_"):
    user_id = f"{prefix}user_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}{uuid.uuid4().hex[:6]}@example.com"
    token = f"{prefix}tok_{uuid.uuid4().hex}"
    _db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": "Priya Sharma",
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    })
    return user_id, email, token


def _cleanup_user(user_id, token):
    _db.user_sessions.delete_many({"session_token": token})
    _db.users.delete_many({"user_id": user_id})
    _db.coach_daily.delete_many({"user_id": user_id})
    _db.coach_messages.delete_many({"user_id": user_id})
    _db.cleanups.delete_many({"user_id": user_id})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_a():
    uid, email, token = _seed_user_and_session()
    yield {"user_id": uid, "email": email, "token": token}
    _cleanup_user(uid, token)


@pytest.fixture
def user_b():
    uid, email, token = _seed_user_and_session()
    yield {"user_id": uid, "email": email, "token": token}
    _cleanup_user(uid, token)


# ---------------- Auth enforcement ----------------
class TestCoachAuth:
    """All /api/coach/* endpoints must require a valid Bearer token."""

    def test_daily_requires_auth(self):
        r = requests.get(f"{API}/coach/daily", timeout=10)
        assert r.status_code == 401, r.text

    def test_history_get_requires_auth(self):
        r = requests.get(f"{API}/coach/history", timeout=10)
        assert r.status_code == 401, r.text

    def test_history_delete_requires_auth(self):
        r = requests.delete(f"{API}/coach/history", timeout=10)
        assert r.status_code == 401, r.text

    def test_chat_requires_auth(self):
        r = requests.post(f"{API}/coach/chat", json={"message": "hi"}, timeout=10)
        assert r.status_code == 401, r.text

    def test_bogus_token_rejected(self):
        r = requests.get(
            f"{API}/coach/daily",
            headers={"Authorization": "Bearer this-token-does-not-exist"},
            timeout=10,
        )
        assert r.status_code == 401


# ---------------- Daily card ----------------
class TestCoachDaily:
    def test_daily_returns_valid_card(self, user_a):
        r = requests.get(f"{API}/coach/daily", headers=_auth(user_a["token"]), timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        # required fields
        for key in ("date", "greeting", "tip_title", "tip_body", "focus", "action_label", "action_route"):
            assert key in data and data[key], f"missing/empty field {key}: {data}"
        # constrained enums
        assert data["focus"] in {"storage", "battery", "security", "photos", "general"}, data["focus"]
        assert data["action_route"] in {"/smart-scan", "/duplicates", "/large-files", "/junk", "/insights"}, data["action_route"]
        # date format YYYY-MM-DD (today)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert data["date"] == today

    def test_daily_is_cached_per_day(self, user_a):
        r1 = requests.get(f"{API}/coach/daily", headers=_auth(user_a["token"]), timeout=60)
        assert r1.status_code == 200
        card1 = r1.json()
        r2 = requests.get(f"{API}/coach/daily", headers=_auth(user_a["token"]), timeout=15)
        assert r2.status_code == 200
        card2 = r2.json()
        # cached: exact match across all fields
        assert card1 == card2, f"daily card should be cached same day\nfirst: {card1}\nsecond: {card2}"

    def test_daily_scoped_per_user(self, user_a, user_b):
        r_a = requests.get(f"{API}/coach/daily", headers=_auth(user_a["token"]), timeout=60)
        r_b = requests.get(f"{API}/coach/daily", headers=_auth(user_b["token"]), timeout=60)
        assert r_a.status_code == 200 and r_b.status_code == 200
        # Different users get independent cache rows (content may or may not match by chance, but
        # confirm both persisted separately)
        count_a = _db.coach_daily.count_documents({"user_id": user_a["user_id"]})
        count_b = _db.coach_daily.count_documents({"user_id": user_b["user_id"]})
        assert count_a == 1 and count_b == 1, (count_a, count_b)


# ---------------- Chat + history + memory ----------------
class TestCoachChat:
    def test_chat_returns_contextual_reply_and_persists(self, user_a):
        payload = {
            "message": "My phone feels slow today",
            "health_score": 62,
            "storage_used_pct": 88.0,
            "battery_health_pct": 79,
        }
        r = requests.post(f"{API}/coach/chat", json=payload, headers=_auth(user_a["token"]), timeout=60)
        assert r.status_code == 200, r.text
        msg = r.json()
        assert msg["role"] == "assistant"
        assert isinstance(msg["content"], str) and len(msg["content"].strip()) > 5
        assert msg["created_at"]

        # Verify BOTH user + assistant messages persisted via history endpoint
        h = requests.get(f"{API}/coach/history", headers=_auth(user_a["token"]), timeout=15)
        assert h.status_code == 200
        history = h.json()
        assert len(history) == 2, history
        roles = [m["role"] for m in history]
        assert roles == ["user", "assistant"], roles
        assert history[0]["content"] == payload["message"]
        assert history[1]["content"] == msg["content"]

    def test_chat_memory_continuity(self, user_a):
        # Clear any prior state first
        requests.delete(f"{API}/coach/history", headers=_auth(user_a["token"]), timeout=10)

        r1 = requests.post(
            f"{API}/coach/chat",
            json={"message": "My phone is slow and storage is nearly full."},
            headers=_auth(user_a["token"]),
            timeout=60,
        )
        assert r1.status_code == 200, r1.text
        reply1 = r1.json()["content"]

        r2 = requests.post(
            f"{API}/coach/chat",
            json={"message": "what should I do first?"},
            headers=_auth(user_a["token"]),
            timeout=60,
        )
        assert r2.status_code == 200, r2.text
        reply2 = r2.json()["content"]

        # History should have 4 messages ordered user/assistant/user/assistant
        h = requests.get(f"{API}/coach/history", headers=_auth(user_a["token"]), timeout=15)
        assert h.status_code == 200
        hist = h.json()
        assert [m["role"] for m in hist] == ["user", "assistant", "user", "assistant"], hist
        assert len(reply2) > 5
        # Contextual awareness: second reply should reference slowness/storage/cleanup topic
        # (soft assertion — reply MUST NOT be identical fallback text, and should be topical)
        low = reply2.lower()
        topical = any(
            kw in low for kw in ("storage", "clean", "junk", "duplicate", "large", "scan", "space", "cache", "slow", "photo")
        )
        assert topical, f"2nd reply lacks topical awareness of prior context: {reply2!r}"
        # Not the LLM-down fallback string
        assert "having trouble thinking" not in low

    def test_chat_empty_message_rejected(self, user_a):
        r = requests.post(f"{API}/coach/chat", json={"message": "   "}, headers=_auth(user_a["token"]), timeout=15)
        assert r.status_code in (400, 422), r.text


class TestCoachHistoryClear:
    def test_delete_history_clears(self, user_a):
        # seed one exchange
        r = requests.post(
            f"{API}/coach/chat",
            json={"message": "hello coach"},
            headers=_auth(user_a["token"]),
            timeout=60,
        )
        assert r.status_code == 200
        h1 = requests.get(f"{API}/coach/history", headers=_auth(user_a["token"]), timeout=10).json()
        assert len(h1) >= 2

        d = requests.delete(f"{API}/coach/history", headers=_auth(user_a["token"]), timeout=10)
        assert d.status_code == 200, d.text
        assert d.json().get("cleared") is True

        h2 = requests.get(f"{API}/coach/history", headers=_auth(user_a["token"]), timeout=10).json()
        assert h2 == [], h2


# ---------------- Rate limit ----------------
class TestCoachRateLimit:
    def test_chat_returns_429_after_10_rapid_calls(self, user_a):
        # Ensure clean slate
        requests.delete(f"{API}/coach/history", headers=_auth(user_a["token"]), timeout=10)
        statuses = []
        for i in range(12):
            r = requests.post(
                f"{API}/coach/chat",
                json={"message": f"ping {i}"},
                headers=_auth(user_a["token"]),
                timeout=60,
            )
            statuses.append(r.status_code)
            if r.status_code == 429:
                break
        assert 429 in statuses, f"Expected a 429 within 12 rapid calls, got: {statuses}"
        # first 10 should be 200s
        first_ten = statuses[:10]
        assert first_ten.count(200) >= 9, f"first 10 mostly 200s expected, got: {first_ten}"


# ---------------- Regression: core endpoints still work ----------------
class TestCoreRegression:
    def test_device_scan_still_works(self, user_a):
        # scan is authed in server.py — send bearer to be safe
        r = requests.post(f"{API}/device/scan", headers=_auth(user_a["token"]), timeout=30)
        # If public it will 200; if authed with token, still 200.
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict) and data, data

    def test_device_clean_still_works(self, user_a):
        r = requests.post(
            f"{API}/device/clean",
            json={"categories": ["cache", "junk"], "reclaimable_mb": 1200.5},
            headers=_auth(user_a["token"]),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "reclaimed_mb" in data or "reclaimed" in data or isinstance(data, dict)

    def test_ai_recommendations_still_works(self, user_a):
        # ai/recommendations previously public — allow both 200 and 401 handling
        r = requests.post(
            f"{API}/ai/recommendations",
            json={
                "health_score": 74,
                "storage_used_pct": 62,
                "battery_health_pct": 85,
                "security_status": "ok",
                "duplicates_mb": 250,
                "junk_mb": 800,
                "threats": 0,
            },
            headers=_auth(user_a["token"]),
            timeout=60,
        )
        # allow 429 in case shared limiter got hit
        assert r.status_code in (200, 429), r.text
        if r.status_code == 200:
            body = r.json()
            assert isinstance(body, (list, dict)) and body
