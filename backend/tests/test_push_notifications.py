"""DevicePulse backend — Push Notification (Emergent SuprSend relay) tests.

Context:
  * EMERGENT_PUSH_KEY is intentionally "placeholder" in this preview env,
    so upstream calls to https://integrations.emergentagent.com will fail
    with 401. Backend maps this to a controlled response — verify:

  1) POST /api/register-push (public) — returns 500 "EMERGENT_PUSH_KEY missing
     or invalid" and does NOT crash the server.
  2) POST /api/push/test (Bearer required):
        - 401 without token
        - 200 {"sent": false, "reason": ...} with token (graceful)
  3) POST /api/push/cleanup-reminder (Bearer required):
        - 401 without token
        - 200 {"sent": false} with token (graceful)
  4) POST /api/family/join (Bearer) still returns 200 and persists the
     membership even though the owner-notification push fails upstream
     (wrapped in try/except).
  5) send_push validation:
        - >100 recipients raises ValueError
        - missing title/message raises ValueError
     (unit-level via imported symbol)
  6) REGRESSION — /ai/recommendations still returns 4 recs (one call only,
     respect the 10/min rate limit).
"""
import os
import sys
import uuid
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

BASE_URL = os.environ.get("BACKEND_TEST_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

load_dotenv("/app/backend/.env")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


def _seed_user_and_session(prefix="TEST_PUSH_"):
    user_id = f"{prefix}user_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}{uuid.uuid4().hex[:6]}@example.com"
    token = f"{prefix}tok_{uuid.uuid4().hex}"
    sid = uuid.uuid4().hex[:12]
    _db.users.insert_one({
        "user_id": user_id, "email": email, "name": "Push Tester",
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _db.user_sessions.insert_one({
        "session_token": token, "sid": sid, "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    })
    return user_id, token, sid


def _cleanup_user(user_id, token):
    _db.user_sessions.delete_many({"session_token": token})
    _db.users.delete_many({"user_id": user_id})
    _db.family_memberships.delete_many({"user_id": user_id})
    _db.family_groups.delete_many({"owner_id": user_id})
    _db.cleanups.delete_many({"device_id": user_id})


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture()
def seeded_user():
    uid, tok, sid = _seed_user_and_session()
    yield {"user_id": uid, "token": tok, "sid": sid}
    _cleanup_user(uid, tok)


# ==================== /api/register-push ====================
class TestRegisterPush:
    def test_register_push_requires_bearer(self, client):
        """Now auth-protected: no token → 401 (identity derived from token, not body)."""
        body = {
            "user_id": f"TEST_dev_{uuid.uuid4().hex[:8]}",
            "platform": "android",
            "device_token": f"ExponentPushToken[{uuid.uuid4().hex}]",
        }
        r = client.post(f"{API}/register-push", json=body)
        assert r.status_code == 401, f"expected 401 without token, got {r.status_code}: {r.text[:300]}"

    def test_register_push_graceful_with_bearer(self, client, seeded_user):
        """With a valid token but placeholder push key, upstream 401 → controlled 500
        'EMERGENT_PUSH_KEY missing or invalid'. Must NOT crash the server."""
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        body = {
            "user_id": "ignored-server-uses-token",
            "platform": "android",
            "device_token": f"ExponentPushToken[{uuid.uuid4().hex}]",
        }
        r = client.post(f"{API}/register-push", headers=h, json=body)
        assert r.status_code == 500, f"expected 500 with placeholder key, got {r.status_code}: {r.text[:300]}"
        assert "EMERGENT_PUSH_KEY" in r.text, r.text[:300]

    def test_server_still_alive_after_bad_push(self, client):
        """Immediately after the failing push call, another endpoint works."""
        r = client.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("app") == "DevicePulse"

    def test_register_push_validates_body(self, client, seeded_user):
        """Missing required fields → 422 (pydantic), not 500 (with valid auth)."""
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        r = client.post(f"{API}/register-push", headers=h, json={"platform": "ios"})
        assert r.status_code == 422


# ==================== /api/push/test ====================
class TestPushTest:
    def test_requires_bearer(self, client):
        r = client.post(f"{API}/push/test")
        assert r.status_code == 401

    def test_returns_sent_false_gracefully(self, client, seeded_user):
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        r = client.post(f"{API}/push/test", headers=h)
        # Graceful: 200 with sent:false + reason (upstream is placeholder)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("sent") is False, data
        assert "reason" in data and isinstance(data["reason"], str)


# ==================== /api/push/cleanup-reminder ====================
class TestPushCleanupReminder:
    def test_requires_bearer(self, client):
        r = client.post(f"{API}/push/cleanup-reminder")
        assert r.status_code == 401

    def test_returns_sent_false_gracefully(self, client, seeded_user):
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        r = client.post(f"{API}/push/cleanup-reminder", headers=h)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("sent") is False, data


# ==================== Family join not broken by push failure ====================
class TestFamilyJoinNotBrokenByPush:
    def test_join_still_succeeds_even_though_owner_push_fails(self, client):
        owner_id, owner_tok, _ = _seed_user_and_session(prefix="TEST_PUSH_FAMOWN_")
        member_id, member_tok, _ = _seed_user_and_session(prefix="TEST_PUSH_FAMMEM_")
        try:
            ho = {"Authorization": f"Bearer {owner_tok}"}
            hm = {"Authorization": f"Bearer {member_tok}"}
            code = client.post(f"{API}/family/create", headers=ho).json()["invite_code"]

            # Joining notifies the owner via push, which fails upstream
            # (placeholder key) — the join itself must still succeed (200).
            r = client.post(f"{API}/family/join", headers=hm, json={"invite_code": code})
            assert r.status_code == 200, r.text
            assert any(m["user_id"] == member_id for m in r.json()["members"])

            # Verify persistence via the owner's view
            r2 = client.get(f"{API}/family/group", headers=ho)
            assert r2.status_code == 200
            assert any(m["user_id"] == member_id for m in r2.json()["members"]), \
                "membership not persisted after push failure"
        finally:
            _cleanup_user(owner_id, owner_tok)
            _cleanup_user(member_id, member_tok)


# ==================== send_push() unit validation ====================
class TestSendPushValidation:
    """Directly import send_push and assert the input validation rules
    (>100 recipients → ValueError; missing title/message → ValueError)."""

    @classmethod
    def setup_class(cls):
        # Ensure backend package importable
        sys.path.insert(0, "/app/backend")

    def test_more_than_100_recipients_raises(self):
        from server import send_push  # imported after path insert
        recipients = [f"u{i}" for i in range(101)]
        with pytest.raises(ValueError, match="max 100"):
            asyncio.get_event_loop().run_until_complete(
                send_push(recipients, {"title": "t", "message": "m"})
            )

    def test_missing_title_or_message_raises(self):
        from server import send_push
        with pytest.raises(ValueError, match="title and message"):
            asyncio.get_event_loop().run_until_complete(
                send_push(["u1"], {"title": "only"})
            )
        with pytest.raises(ValueError, match="title and message"):
            asyncio.get_event_loop().run_until_complete(
                send_push(["u1"], {"message": "only"})
            )


# ==================== REGRESSION — /ai/recommendations ====================
class TestAIRecommendationsRegression:
    def test_ai_returns_four_recs(self, client):
        """One call only — respect 10/min rate limit."""
        r = client.post(f"{API}/ai/recommendations", json={
            "health_score": 68, "storage_used_pct": 73.6,
            "battery_health_pct": 87, "duplicates_mb": 320.0,
            "junk_mb": 900.0, "threats": 1, "platform": "android",
        }, timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 4, f"expected 4 recs, got {len(data)}"
        for rec in data:
            assert "title" in rec and "description" in rec and "impact" in rec
            assert rec["impact"] in ("low", "medium", "high")


# ==================== REGRESSION — Auth gating for push endpoints ====================
class TestPushAuthRegression:
    def test_bogus_bearer_on_push_test(self, client):
        r = client.post(f"{API}/push/test", headers={"Authorization": "Bearer nope-abc-xyz"})
        assert r.status_code == 401

    def test_bogus_bearer_on_cleanup_reminder(self, client):
        r = client.post(f"{API}/push/cleanup-reminder",
                        headers={"Authorization": "Bearer nope-abc-xyz"})
        assert r.status_code == 401

    def test_bogus_session_id_returns_401(self, client):
        r = client.post(f"{API}/auth/session",
                        json={"session_id": "definitely-not-a-real-session-id-xyz"})
        assert r.status_code == 401
