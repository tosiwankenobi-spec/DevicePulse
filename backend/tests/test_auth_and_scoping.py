"""DevicePulse backend — auth gating + per-user scoping (IDOR) tests.

Covers:
  * Protected endpoints reject unauthenticated requests with 401
  * POST /api/auth/session with bogus session_id returns 401
  * Public/simulated endpoints remain open (200)
  * Using a directly-seeded MongoDB session token, protected endpoints return 200
    and are scoped to that user
  * Two different seeded users cannot see each other's family members / history
  * Expired session returns 401
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

# Backend runs on localhost:8001 (per environment/config).
BASE_URL = os.environ.get("BACKEND_TEST_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

# Mongo config for seeding sessions
load_dotenv("/app/backend/.env")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


# ---------------- Helpers ----------------
def _seed_user_and_session(prefix="TEST_", sid=None):
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
    _db.referrals.delete_many({"device_id": user_id})
    _db.reminders.delete_many({"device_id": user_id})
    _db.freezes.delete_many({"device_id": user_id})
    _db.family.delete_many({"owner_id": user_id})


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture()
def seeded_user():
    uid, email, tok, sid = _seed_user_and_session()
    yield {"user_id": uid, "email": email, "token": tok, "sid": sid}
    _cleanup_user(uid, tok)


# The set of endpoints that MUST require auth (401 without a Bearer token).
PROTECTED = [
    ("GET", "/auth/me", None),
    ("GET", "/history", None),
    ("GET", "/streak", None),
    ("GET", "/forecast", None),
    ("GET", "/device/health-trend", None),
    ("GET", "/reminders", None),
    ("PUT", "/reminders", {"device_id": "x", "low_storage": True, "weekly_cleanup": True,
                           "after_downloads": True, "battery_alerts": False}),
    ("GET", "/referral", None),
    ("POST", "/referral/invite", {}),
    ("POST", "/streak/freeze", {}),
    ("GET", "/family", None),
    ("POST", "/family/member", {"name": "X", "device_type": "phone"}),
    ("DELETE", "/family/member/does-not-exist", None),
    ("POST", "/device/clean", {"categories": ["junk"], "reclaimable_mb": 100.0}),
    ("GET", "/device/cache-breakdown", None),
    # New in this iteration:
    ("GET", "/auth/sessions", None),
    ("POST", "/auth/sessions/does-not-exist/revoke", {}),
    ("DELETE", "/auth/account", None),
    # AI Health Coach:
    ("GET", "/coach/daily", None),
    ("GET", "/coach/history", None),
    ("DELETE", "/coach/history", None),
    ("POST", "/coach/chat", {"message": "hi"}),
    # Daily Pulse Check:
    ("GET", "/pulse/daily", None),
    # Home Screen Widget (live):
    ("GET", "/widget/summary", None),
]

PUBLIC = [
    ("GET", "/device/health"),
    ("GET", "/device/storage"),
    ("GET", "/device/duplicates"),
    ("GET", "/device/large-files"),
    ("GET", "/device/battery"),
    ("GET", "/device/security"),
    ("POST", "/device/scan"),
]


# ==================== Unauth: protected endpoints must return 401 ====================
class TestProtectedRequireAuth:
    @pytest.mark.parametrize("method,path,body", PROTECTED)
    def test_no_token_returns_401(self, client, method, path, body):
        url = f"{API}{path}"
        r = client.request(method, url, json=body)
        assert r.status_code == 401, f"{method} {path} expected 401, got {r.status_code}: {r.text[:200]}"


# ==================== Public endpoints remain open ====================
class TestPublicEndpointsOpen:
    @pytest.mark.parametrize("method,path", PUBLIC)
    def test_public_no_token_returns_200(self, client, method, path):
        r = client.request(method, f"{API}{path}")
        assert r.status_code == 200, f"{method} {path} expected 200, got {r.status_code}"


# ==================== POST /auth/session with bogus session_id ====================
class TestAuthSessionInvalid:
    def test_bogus_session_id_returns_401(self, client):
        r = client.post(f"{API}/auth/session", json={"session_id": "definitely-not-a-real-session-id-xyz"})
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"


# ==================== Seeded session: happy path across protected endpoints ====================
class TestSeededSessionFlow:
    def test_me_returns_seeded_user(self, client, seeded_user):
        r = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {seeded_user['token']}"})
        assert r.status_code == 200
        d = r.json()
        assert d["user_id"] == seeded_user["user_id"]
        assert d["email"] == seeded_user["email"]

    def test_clean_persists_and_history_reflects(self, client, seeded_user):
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        r = client.post(f"{API}/device/clean",
                        headers=h,
                        json={"categories": ["junk", "cache"], "reclaimable_mb": 777.0})
        assert r.status_code == 200
        assert r.json()["reclaimed_mb"] == 777.0

        r2 = client.get(f"{API}/history", headers=h)
        assert r2.status_code == 200
        items = r2.json()
        assert any(x["reclaimed_mb"] == 777.0 for x in items)

    def test_family_crud(self, client, seeded_user):
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        # add
        r = client.post(f"{API}/family/member", headers=h, json={"name": "Alice", "device_type": "phone"})
        assert r.status_code == 200
        mid = r.json()["id"]
        # list
        r2 = client.get(f"{API}/family", headers=h)
        assert r2.status_code == 200
        assert any(m["id"] == mid for m in r2.json())
        # delete
        r3 = client.delete(f"{API}/family/member/{mid}", headers=h)
        assert r3.status_code == 200
        r4 = client.get(f"{API}/family", headers=h)
        assert not any(m["id"] == mid for m in r4.json())

    def test_streak_and_freeze_once_per_month(self, client, seeded_user):
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        r = client.get(f"{API}/streak", headers=h)
        assert r.status_code == 200
        assert "current_streak_weeks" in r.json()

        r1 = client.post(f"{API}/streak/freeze", headers=h)
        assert r1.status_code == 200, r1.text
        r2 = client.post(f"{API}/streak/freeze", headers=h)
        assert r2.status_code == 400

    def test_forecast_health_trend(self, client, seeded_user):
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        r = client.get(f"{API}/forecast", headers=h)
        assert r.status_code == 200
        assert r.json()["total_gb"] > 0

        r2 = client.get(f"{API}/device/health-trend", headers=h)
        assert r2.status_code == 200
        assert len(r2.json()["points"]) == 8

    def test_reminders_get_put(self, client, seeded_user):
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        r = client.get(f"{API}/reminders", headers=h)
        assert r.status_code == 200
        prefs = r.json()
        prefs["battery_alerts"] = True
        r2 = client.put(f"{API}/reminders", headers=h, json=prefs)
        assert r2.status_code == 200
        assert r2.json()["battery_alerts"] is True

    def test_referral_and_invite(self, client, seeded_user):
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        r = client.get(f"{API}/referral", headers=h)
        assert r.status_code == 200
        assert r.json()["invited_count"] == 0
        r2 = client.post(f"{API}/referral/invite", headers=h)
        assert r2.status_code == 200
        assert r2.json()["invited_count"] == 1

    def test_cache_breakdown(self, client, seeded_user):
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        r = client.get(f"{API}/device/cache-breakdown", headers=h)
        assert r.status_code == 200
        assert r.json()["total_mb"] > 0


# ==================== IDOR fix: two users must be isolated ====================
class TestIDORScoping:
    def test_two_users_isolated_family_and_history(self, client):
        u1_id, _, u1_tok, _ = _seed_user_and_session(prefix="TEST_A_")
        u2_id, _, u2_tok, _ = _seed_user_and_session(prefix="TEST_B_")
        try:
            h1 = {"Authorization": f"Bearer {u1_tok}"}
            h2 = {"Authorization": f"Bearer {u2_tok}"}

            # user 1 adds family & does a cleanup
            r = client.post(f"{API}/family/member", headers=h1, json={"name": "OnlyForA", "device_type": "phone"})
            assert r.status_code == 200
            member_a = r.json()["id"]
            r = client.post(f"{API}/device/clean", headers=h1,
                            json={"categories": ["junk"], "reclaimable_mb": 111.0})
            assert r.status_code == 200

            # user 2 should NOT see user 1's family members or history
            r_fam = client.get(f"{API}/family", headers=h2)
            assert r_fam.status_code == 200
            assert not any(m["id"] == member_a for m in r_fam.json()), \
                "IDOR: user B sees user A's family member"
            assert not any(m["name"] == "OnlyForA" for m in r_fam.json())

            r_hist = client.get(f"{API}/history", headers=h2)
            assert r_hist.status_code == 200
            assert not any(x["reclaimed_mb"] == 111.0 for x in r_hist.json()), \
                "IDOR: user B sees user A's history entry"

            # user 2 also cannot delete user 1's family member (endpoint scoped by owner)
            r_del = client.delete(f"{API}/family/member/{member_a}", headers=h2)
            # endpoint returns 200 with {"removed": ...} but should not actually delete
            assert r_del.status_code == 200
            r_check = client.get(f"{API}/family", headers=h1)
            assert any(m["id"] == member_a for m in r_check.json()), \
                "IDOR: user B was able to delete user A's family member"
        finally:
            _cleanup_user(u1_id, u1_tok)
            _cleanup_user(u2_id, u2_tok)


# ==================== Expired session ====================
class TestExpiredSession:
    def test_expired_token_returns_401(self, client):
        user_id = f"TEST_exp_user_{uuid.uuid4().hex[:8]}"
        token = f"TEST_exp_tok_{uuid.uuid4().hex}"
        _db.users.insert_one({
            "user_id": user_id, "email": f"{user_id}@example.com",
            "name": "Expired Test", "picture": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        _db.user_sessions.insert_one({
            "session_token": token,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc) - timedelta(days=8),
            "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
        })
        try:
            r = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 401, f"Expected 401 for expired session, got {r.status_code}: {r.text}"
        finally:
            _db.user_sessions.delete_many({"session_token": token})
            _db.users.delete_many({"user_id": user_id})


# ==================== Malformed/invalid token ====================
class TestInvalidTokenShape:
    def test_missing_bearer_prefix_returns_401(self, client):
        r = client.get(f"{API}/auth/me", headers={"Authorization": "not-a-real-token"})
        assert r.status_code == 401

    def test_unknown_bearer_token_returns_401(self, client):
        r = client.get(f"{API}/auth/me", headers={"Authorization": "Bearer unknown-token-abc"})
        assert r.status_code == 401


# ==================== Sessions list, revoke, and account deletion (NEW) ====================
class TestSessionsListAndRevoke:
    def test_sessions_list_marks_current(self, client, seeded_user):
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        r = client.get(f"{API}/auth/sessions", headers=h)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1
        # Every entry has expected shape
        for s in data:
            assert set(["sid", "created_at", "expires_at", "current"]).issubset(s.keys())
        # exactly one is current (the calling token)
        currents = [s for s in data if s["current"]]
        assert len(currents) == 1
        assert currents[0]["sid"] == seeded_user["sid"]

    def test_sessions_list_only_own_user(self, client):
        u1_id, _, u1_tok, u1_sid = _seed_user_and_session(prefix="TEST_LA_")
        u2_id, _, u2_tok, u2_sid = _seed_user_and_session(prefix="TEST_LB_")
        try:
            r = client.get(f"{API}/auth/sessions", headers={"Authorization": f"Bearer {u1_tok}"})
            assert r.status_code == 200
            sids = [s["sid"] for s in r.json()]
            assert u1_sid in sids
            assert u2_sid not in sids, "IDOR: user A sees user B\u2019s session sid"
        finally:
            _cleanup_user(u1_id, u1_tok); _cleanup_user(u2_id, u2_tok)

    def test_revoke_own_extra_session(self, client, seeded_user):
        # Add a second session for the same user
        extra_sid = uuid.uuid4().hex[:12]
        extra_tok = f"TEST_extra_{uuid.uuid4().hex}"
        _db.user_sessions.insert_one({
            "session_token": extra_tok, "sid": extra_sid,
            "user_id": seeded_user["user_id"],
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        })
        try:
            h = {"Authorization": f"Bearer {seeded_user['token']}"}
            r = client.post(f"{API}/auth/sessions/{extra_sid}/revoke", headers=h)
            assert r.status_code == 200 and r.json() == {"revoked": True}
            # confirm the extra token no longer authenticates
            r2 = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {extra_tok}"})
            assert r2.status_code == 401
            # calling session still works
            r3 = client.get(f"{API}/auth/me", headers=h)
            assert r3.status_code == 200
        finally:
            _db.user_sessions.delete_many({"session_token": extra_tok})

    def test_revoke_nonexistent_sid_returns_revoked_false(self, client, seeded_user):
        h = {"Authorization": f"Bearer {seeded_user['token']}"}
        r = client.post(f"{API}/auth/sessions/nonexistent0/revoke", headers=h)
        assert r.status_code == 200 and r.json() == {"revoked": False}

    def test_cannot_revoke_other_users_sid(self, client):
        u1_id, _, u1_tok, u1_sid = _seed_user_and_session(prefix="TEST_R1_")
        u2_id, _, u2_tok, u2_sid = _seed_user_and_session(prefix="TEST_R2_")
        try:
            # user 2 tries to revoke user 1\u2019s sid
            r = client.post(f"{API}/auth/sessions/{u1_sid}/revoke",
                            headers={"Authorization": f"Bearer {u2_tok}"})
            assert r.status_code == 200 and r.json() == {"revoked": False}, \
                "IDOR: user B was able to revoke user A\u2019s session"
            # user 1\u2019s session is still valid
            r2 = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {u1_tok}"})
            assert r2.status_code == 200
        finally:
            _cleanup_user(u1_id, u1_tok); _cleanup_user(u2_id, u2_tok)


class TestAccountDeletion:
    def test_delete_removes_user_sessions_and_data(self, client):
        uid, _, tok, _ = _seed_user_and_session(prefix="TEST_DEL_")
        try:
            h = {"Authorization": f"Bearer {tok}"}
            # seed some data
            r = client.post(f"{API}/device/clean", headers=h,
                            json={"categories": ["junk"], "reclaimable_mb": 42.0})
            assert r.status_code == 200
            r = client.post(f"{API}/family/member", headers=h,
                            json={"name": "ToBeDeleted", "device_type": "phone"})
            assert r.status_code == 200
            r = client.get(f"{API}/referral", headers=h); assert r.status_code == 200
            r = client.get(f"{API}/reminders", headers=h); assert r.status_code == 200

            # delete the account
            r = client.delete(f"{API}/auth/account", headers=h)
            assert r.status_code == 200 and r.json() == {"deleted": True}

            # token no longer authenticates
            r2 = client.get(f"{API}/auth/me", headers=h)
            assert r2.status_code == 401

            # DB rows for this user are gone
            assert _db.users.find_one({"user_id": uid}) is None
            assert _db.user_sessions.count_documents({"user_id": uid}) == 0
            assert _db.cleanups.count_documents({"device_id": uid}) == 0
            assert _db.family.count_documents({"owner_id": uid}) == 0
            assert _db.referrals.count_documents({"device_id": uid}) == 0
            assert _db.reminders.count_documents({"device_id": uid}) == 0
        finally:
            _cleanup_user(uid, tok)

    def test_delete_leaves_other_user_data_untouched(self, client):
        a_id, _, a_tok, _ = _seed_user_and_session(prefix="TEST_KA_")
        b_id, _, b_tok, _ = _seed_user_and_session(prefix="TEST_KB_")
        try:
            ha = {"Authorization": f"Bearer {a_tok}"}
            hb = {"Authorization": f"Bearer {b_tok}"}
            client.post(f"{API}/device/clean", headers=ha,
                       json={"categories": ["junk"], "reclaimable_mb": 10.0})
            client.post(f"{API}/device/clean", headers=hb,
                       json={"categories": ["junk"], "reclaimable_mb": 20.0})
            client.post(f"{API}/family/member", headers=hb, json={"name": "KeepMe", "device_type": "phone"})

            # delete user A
            r = client.delete(f"{API}/auth/account", headers=ha)
            assert r.status_code == 200

            # user B still fine
            r2 = client.get(f"{API}/auth/me", headers=hb)
            assert r2.status_code == 200 and r2.json()["user_id"] == b_id
            r3 = client.get(f"{API}/history", headers=hb)
            assert r3.status_code == 200 and any(x["reclaimed_mb"] == 20.0 for x in r3.json())
            r4 = client.get(f"{API}/family", headers=hb)
            assert r4.status_code == 200 and any(m["name"] == "KeepMe" for m in r4.json())
        finally:
            _cleanup_user(a_id, a_tok); _cleanup_user(b_id, b_tok)
