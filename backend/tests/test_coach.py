"""DevicePulse backend — AI Health Coach endpoint tests.

Covers:
  * All /coach/* endpoints require auth (401 without a Bearer token)
  * GET /coach/daily returns a card and caches it per user per day
  * GET /coach/daily falls back gracefully when the LLM call fails
  * POST /coach/chat happy path persists both user + assistant messages
  * POST /coach/chat rejects empty messages (422) and enforces the 1000-char cap
  * POST /coach/chat is rate-limited per user (429 after N requests/minute)
  * GET /coach/history / DELETE /coach/history are scoped per user (no IDOR leak)
"""
import os
import uuid
import time
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


def _seed_user_and_session(prefix="COACH_", sid=None):
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
    _db.coach_messages.delete_many({"user_id": user_id})
    _db.coach_daily.delete_many({"user_id": user_id})


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
COACH_PROTECTED = [
    ("GET", "/coach/daily", None),
    ("GET", "/coach/history", None),
    ("DELETE", "/coach/history", None),
    ("POST", "/coach/chat", {"message": "hi"}),
]


class TestCoachRequiresAuth:
    @pytest.mark.parametrize("method,path,body", COACH_PROTECTED)
    def test_no_token_returns_401(self, client, method, path, body):
        r = client.request(method, f"{API}{path}", json=body)
        assert r.status_code == 401, f"{method} {path} should require auth, got {r.status_code}"


# ---------------- Daily coaching card ----------------
class TestCoachDaily:
    def test_returns_card_and_caches_per_day(self, client, seeded_user):
        r1 = client.get(f"{API}/coach/daily", headers=_auth(seeded_user["token"]))
        assert r1.status_code == 200, r1.text
        card1 = r1.json()
        for key in ("date", "greeting", "tip_title", "tip_body", "focus", "action_label", "action_route"):
            assert key in card1

        # Second call same day should return the cached card (identical content),
        # not generate a fresh one.
        r2 = client.get(f"{API}/coach/daily", headers=_auth(seeded_user["token"]))
        assert r2.status_code == 200
        assert r2.json() == card1

    def test_focus_and_route_are_allowlisted(self, client, seeded_user):
        r = client.get(f"{API}/coach/daily", headers=_auth(seeded_user["token"]))
        card = r.json()
        assert card["focus"] in {"storage", "battery", "security", "photos", "general"}
        assert card["action_route"] in {"/smart-scan", "/duplicates", "/large-files", "/junk", "/insights"}


# ---------------- Chat ----------------
class TestCoachChat:
    def test_happy_path_persists_messages(self, client, seeded_user):
        r = client.post(
            f"{API}/coach/chat",
            headers=_auth(seeded_user["token"]),
            json={"message": "Why is my phone slow?", "health_score": 80},
        )
        assert r.status_code == 200, r.text
        reply = r.json()
        assert reply["role"] == "assistant"
        assert isinstance(reply["content"], str) and len(reply["content"]) > 0

        hist = client.get(f"{API}/coach/history", headers=_auth(seeded_user["token"])).json()
        roles = [m["role"] for m in hist]
        assert roles[-2:] == ["user", "assistant"], hist

    def test_empty_message_rejected(self, client, seeded_user):
        r = client.post(
            f"{API}/coach/chat",
            headers=_auth(seeded_user["token"]),
            json={"message": "   "},
        )
        assert r.status_code == 422

    def test_message_is_capped_at_1000_chars(self, client, seeded_user):
        long_msg = "x" * 5000
        r = client.post(
            f"{API}/coach/chat",
            headers=_auth(seeded_user["token"]),
            json={"message": long_msg},
        )
        assert r.status_code == 200, r.text
        stored = _db.coach_messages.find_one(
            {"user_id": seeded_user["user_id"], "role": "user"}, sort=[("created_at", -1)]
        )
        assert len(stored["content"]) <= 1000

    def test_rate_limited_after_ten_per_minute(self, client, seeded_user):
        last = None
        for _ in range(11):
            last = client.post(
                f"{API}/coach/chat",
                headers=_auth(seeded_user["token"]),
                json={"message": "ping"},
            )
        assert last.status_code == 429, "11th chat message within a minute should be rate-limited"


# ---------------- History scoping (IDOR) ----------------
class TestCoachHistoryScoping:
    def test_users_cannot_see_each_others_history(self, client):
        uid_a, _, tok_a, _ = _seed_user_and_session(prefix="COACHA_")
        uid_b, _, tok_b, _ = _seed_user_and_session(prefix="COACHB_")
        try:
            client.post(f"{API}/coach/chat", headers=_auth(tok_a), json={"message": "user A secret question"})
            hist_b = client.get(f"{API}/coach/history", headers=_auth(tok_b)).json()
            assert all("secret" not in m["content"] for m in hist_b)
        finally:
            _cleanup_user(uid_a, tok_a)
            _cleanup_user(uid_b, tok_b)

    def test_clear_only_clears_own_history(self, client):
        uid_a, _, tok_a, _ = _seed_user_and_session(prefix="COACHC_")
        uid_b, _, tok_b, _ = _seed_user_and_session(prefix="COACHD_")
        try:
            client.post(f"{API}/coach/chat", headers=_auth(tok_a), json={"message": "hello from A"})
            client.post(f"{API}/coach/chat", headers=_auth(tok_b), json={"message": "hello from B"})
            client.delete(f"{API}/coach/history", headers=_auth(tok_a))

            hist_a = client.get(f"{API}/coach/history", headers=_auth(tok_a)).json()
            hist_b = client.get(f"{API}/coach/history", headers=_auth(tok_b)).json()
            assert hist_a == []
            assert len(hist_b) == 2  # user + assistant message still intact
        finally:
            _cleanup_user(uid_a, tok_a)
            _cleanup_user(uid_b, tok_b)


# ---------------- Fallback behavior when the LLM call fails ----------------
class TestCoachFallback:
    _FLAG_FILE = os.environ.get("EI_STUB_RAISE_FLAG_FILE", "/tmp/ei_stub_raise.flag")

    def test_daily_falls_back_gracefully_on_llm_error(self, client):
        uid, _, tok, _ = _seed_user_and_session(prefix="COACHFB_")
        open(self._FLAG_FILE, "w").close()
        try:
            r = client.get(f"{API}/coach/daily", headers=_auth(tok))
            assert r.status_code == 200, r.text
            card = r.json()
            assert card["action_route"] == "/smart-scan"  # the hardcoded fallback card
        finally:
            if os.path.exists(self._FLAG_FILE):
                os.remove(self._FLAG_FILE)
            _cleanup_user(uid, tok)

    def test_chat_returns_friendly_message_on_llm_error(self, client):
        uid, _, tok, _ = _seed_user_and_session(prefix="COACHFB2_")
        open(self._FLAG_FILE, "w").close()
        try:
            r = client.post(f"{API}/coach/chat", headers=_auth(tok), json={"message": "hi"})
            assert r.status_code == 200, r.text
            assert "trouble" in r.json()["content"].lower()
        finally:
            if os.path.exists(self._FLAG_FILE):
                os.remove(self._FLAG_FILE)
            _cleanup_user(uid, tok)
