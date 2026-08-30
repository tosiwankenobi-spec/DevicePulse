"""DevicePulse backend — Memory/RAM Boost tests.

Covers a post-roadmap gap found by inspection: the scan hub
(app/(tabs)/scan.tsx) advertises a distinct "Memory Cleanup" tool ("Free up
RAM instantly"), but its tile has never had any real backend behind it — it
just rerouted to /smart-scan. The only "RAM" concept anywhere in the
backend was a single hardcoded ram_used_pct=72 constant baked into the
shared _seed_health() device-health snapshot (deliberately left alone here,
since that baseline is reused by Daily Pulse Check / the widget / the
Coach, and making it stateful risks breaking their consistency). This gives
Memory Boost its own real per-user state and action, mirroring how Battery
Health & Optimizer got its own independent state.

Design note: like Large File Cleanup, there is no Pro-perk promise anywhere
in paywall.tsx tied to memory/RAM, so this feature has no Pro gate.

Covers:
  * GET /device/memory and POST /device/memory/boost both require auth
  * GET lazily generates a per-user RAM state once, persists it (stable
    across repeated GETs), independently per user
  * POST /device/memory/boost closes the top RAM-consuming app(s), reduces
    ram_used_pct accordingly (never below the 15% floor), sets
    last_boosted_at, and increments boosts_run
  * Repeated boosts keep working safely once apps_running is exhausted
  * Deleting the account removes memory_state too
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


def _seed_user_and_session(prefix="MEM_"):
    user_id = f"{prefix}user_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}{uuid.uuid4().hex[:6]}@example.com"
    token = f"{prefix}tok_{uuid.uuid4().hex}"
    sid = uuid.uuid4().hex[:12]
    _db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": "Memory Tester",
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
    _db.memory_state.delete_many({"user_id": user_id})


@pytest.fixture()
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture()
def user():
    uid, tok = _seed_user_and_session()
    yield {"user_id": uid, "token": tok}
    _cleanup_user(uid, tok)


@pytest.fixture()
def other_user():
    uid, tok = _seed_user_and_session(prefix="MEM_OTHER_")
    yield {"user_id": uid, "token": tok}
    _cleanup_user(uid, tok)


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


class TestRequiresAuth:
    def test_get_requires_auth(self, client):
        assert client.get(f"{API}/device/memory").status_code == 401

    def test_boost_requires_auth(self, client):
        assert client.post(f"{API}/device/memory/boost").status_code == 401


class TestPersistedGeneration:
    def test_first_get_generates_and_persists(self, client, user):
        r = client.get(f"{API}/device/memory", headers=_auth(user["token"]))
        assert r.status_code == 200
        body = r.json()
        assert 0 <= body["ram_used_pct"] <= 100
        assert body["ram_total_gb"] > 0
        assert isinstance(body["apps_running"], list) and len(body["apps_running"]) >= 1
        assert body["last_boosted_at"] is None
        assert body["boosts_run"] == 0
        assert _db.memory_state.find_one({"user_id": user["user_id"]}) is not None

    def test_repeated_get_is_stable(self, client, user):
        h = _auth(user["token"])
        first = client.get(f"{API}/device/memory", headers=h).json()
        second = client.get(f"{API}/device/memory", headers=h).json()
        assert first == second

    def test_two_users_get_independent_state(self, client, user, other_user):
        client.get(f"{API}/device/memory", headers=_auth(user["token"]))
        client.get(f"{API}/device/memory", headers=_auth(other_user["token"]))
        doc_a = _db.memory_state.find_one({"user_id": user["user_id"]})
        doc_b = _db.memory_state.find_one({"user_id": other_user["user_id"]})
        assert doc_a["user_id"] != doc_b["user_id"]


class TestBoostBehavior:
    def test_boost_closes_top_apps_and_frees_ram(self, client, user):
        h = _auth(user["token"])
        before = client.get(f"{API}/device/memory", headers=h).json()
        before_apps = before["apps_running"]

        r = client.post(f"{API}/device/memory/boost", headers=h)
        assert r.status_code == 200
        result = r.json()
        assert result["apps_closed"] == min(3, len(before_apps))
        assert result["ram_freed_pct"] >= 0

        state = result["state"]
        assert state["ram_used_pct"] == before["ram_used_pct"] - result["ram_freed_pct"]
        assert state["ram_used_pct"] <= before["ram_used_pct"]
        assert len(state["apps_running"]) == len(before_apps) - result["apps_closed"]

    def test_boost_sets_timestamp_and_increments_counter(self, client, user):
        h = _auth(user["token"])
        client.get(f"{API}/device/memory", headers=h)
        r1 = client.post(f"{API}/device/memory/boost", headers=h)
        s1 = r1.json()["state"]
        assert s1["last_boosted_at"] is not None
        assert s1["boosts_run"] == 1

        r2 = client.post(f"{API}/device/memory/boost", headers=h)
        s2 = r2.json()["state"]
        assert s2["boosts_run"] == 2

    def test_ram_never_drops_below_floor(self, client, user):
        h = _auth(user["token"])
        client.get(f"{API}/device/memory", headers=h)
        last = None
        for _ in range(10):
            r = client.post(f"{API}/device/memory/boost", headers=h)
            assert r.status_code == 200
            last = r.json()
            assert last["state"]["ram_used_pct"] >= 15

    def test_boost_keeps_working_after_apps_exhausted(self, client, user):
        h = _auth(user["token"])
        client.get(f"{API}/device/memory", headers=h)
        last = None
        for _ in range(10):
            r = client.post(f"{API}/device/memory/boost", headers=h)
            assert r.status_code == 200
            last = r.json()
            if len(last["state"]["apps_running"]) == 0:
                break
        assert last["state"]["apps_running"] == []
        r = client.post(f"{API}/device/memory/boost", headers=h)
        assert r.status_code == 200
        final = r.json()
        assert final["apps_closed"] == 0
        assert final["ram_freed_pct"] == 0


class TestAccountDeletionCleansUp:
    def test_delete_account_removes_memory_state(self, client, user):
        h = _auth(user["token"])
        client.get(f"{API}/device/memory", headers=h)
        assert _db.memory_state.find_one({"user_id": user["user_id"]}) is not None

        r = client.delete(f"{API}/auth/account", headers=h)
        assert r.status_code == 200
        assert _db.memory_state.find_one({"user_id": user["user_id"]}) is None
