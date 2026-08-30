"""DevicePulse backend — Battery Health & Optimizer tests.

Covers a post-roadmap gap found by inspection: the old GET /device/battery
was unauthenticated and returned the exact same hardcoded fixture (level=54,
health=87%, the same five drain apps at the same percentages) on every call
— nothing was per-user or persisted, and paywall.tsx has long advertised
"Battery optimizer" as a Pro perk with no backend action behind it at all
(the same shape of gap Auto-Clean Scheduling closed for "Scheduled
cleanups" and Duplicate Photo AI closed for "Unlimited duplicate cleanup").

Design decision, made explicitly via AskUserQuestion before writing code:
the new POST /device/battery/optimize action is Pro-gated using the same
stored `is_pro` flag as Auto-Clean Scheduling (403 for free users), matching
what paywall.tsx already promises. GET /device/battery itself stays free
for everyone — it's just now real and per-user instead of a static fixture.

Covers:
  * GET /device/battery and POST /device/battery/optimize both require auth
  * GET lazily generates a per-user battery state once, persists it (stable
    across repeated GETs), independently per user
  * POST /device/battery/optimize is 403 for a non-Pro user, 200 once Pro
  * A successful optimize call removes the top drain app(s), increases
    `level` (capped at 100), leaves health_pct/cycle_count untouched (no
    fake hardware-health claim), sets last_optimized_at, and increments
    optimizations_run
  * time_to_empty_hours scales consistently with level via the persisted
    per-user baseline (not just a static constant)
  * Repeated optimize calls keep working even once drain_apps is exhausted
    (apps_optimized=0, level_gained=0, still 200 — no crash, no fake gain)
  * Deleting the account removes battery_state too
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


def _seed_user_and_session(prefix="BATT_"):
    user_id = f"{prefix}user_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}{uuid.uuid4().hex[:6]}@example.com"
    token = f"{prefix}tok_{uuid.uuid4().hex}"
    sid = uuid.uuid4().hex[:12]
    _db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": "Battery Tester",
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
    _db.battery_state.delete_many({"user_id": user_id})


def _make_pro(user_id):
    _db.users.update_one({"user_id": user_id}, {"$set": {"is_pro": True}})


@pytest.fixture()
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture()
def free_user():
    uid, tok = _seed_user_and_session()
    yield {"user_id": uid, "token": tok}
    _cleanup_user(uid, tok)


@pytest.fixture()
def pro_user():
    uid, tok = _seed_user_and_session()
    _make_pro(uid)
    yield {"user_id": uid, "token": tok}
    _cleanup_user(uid, tok)


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


class TestRequiresAuth:
    def test_get_battery_requires_auth(self, client):
        r = client.get(f"{API}/device/battery")
        assert r.status_code == 401

    def test_optimize_requires_auth(self, client):
        r = client.post(f"{API}/device/battery/optimize")
        assert r.status_code == 401


class TestPersistedGeneration:
    def test_first_get_generates_and_persists(self, client, free_user):
        r = client.get(f"{API}/device/battery", headers=_auth(free_user["token"]))
        assert r.status_code == 200
        body = r.json()
        assert 0 <= body["level"] <= 100
        assert 0 <= body["health_pct"] <= 100
        assert body["cycle_count"] > 0
        assert body["temperature_c"] > 0
        assert body["charging"] is False
        assert body["time_to_empty_hours"] > 0
        assert isinstance(body["drain_apps"], list) and len(body["drain_apps"]) >= 1
        assert body["last_optimized_at"] is None
        assert body["optimizations_run"] == 0

        doc = _db.battery_state.find_one({"user_id": free_user["user_id"]})
        assert doc is not None

    def test_repeated_get_is_stable(self, client, free_user):
        h = _auth(free_user["token"])
        first = client.get(f"{API}/device/battery", headers=h).json()
        second = client.get(f"{API}/device/battery", headers=h).json()
        assert first == second

    def test_two_users_get_independent_state(self, client, free_user, pro_user):
        a = client.get(f"{API}/device/battery", headers=_auth(free_user["token"])).json()
        b = client.get(f"{API}/device/battery", headers=_auth(pro_user["token"])).json()
        # Independently generated per-user docs exist (not shared/global state).
        doc_a = _db.battery_state.find_one({"user_id": free_user["user_id"]})
        doc_b = _db.battery_state.find_one({"user_id": pro_user["user_id"]})
        assert doc_a["user_id"] != doc_b["user_id"]
        assert (a["level"], a["drain_apps"]) != (None, None)
        assert (b["level"], b["drain_apps"]) != (None, None)


class TestProGating:
    def test_optimize_403_without_pro(self, client, free_user):
        client.get(f"{API}/device/battery", headers=_auth(free_user["token"]))
        r = client.post(f"{API}/device/battery/optimize", headers=_auth(free_user["token"]))
        assert r.status_code == 403

    def test_optimize_200_with_pro(self, client, pro_user):
        client.get(f"{API}/device/battery", headers=_auth(pro_user["token"]))
        r = client.post(f"{API}/device/battery/optimize", headers=_auth(pro_user["token"]))
        assert r.status_code == 200


class TestOptimizeBehavior:
    def test_optimize_removes_top_drain_apps_and_gains_level(self, client, pro_user):
        h = _auth(pro_user["token"])
        before = client.get(f"{API}/device/battery", headers=h).json()
        before_apps = before["drain_apps"]
        before_level = before["level"]

        r = client.post(f"{API}/device/battery/optimize", headers=h)
        assert r.status_code == 200
        result = r.json()

        assert result["apps_optimized"] == min(2, len(before_apps))
        assert result["level_gained"] >= 0

        state = result["state"]
        assert state["level"] == min(100, before_level + result["level_gained"])
        assert len(state["drain_apps"]) == len(before_apps) - result["apps_optimized"]
        # The apps removed should be the highest-drain ones.
        remaining_names = {a["name"] for a in state["drain_apps"]}
        top_names = {a["name"] for a in sorted(before_apps, key=lambda a: a["pct"], reverse=True)[:result["apps_optimized"]]}
        assert remaining_names.isdisjoint(top_names)

    def test_optimize_never_touches_hardware_health_fields(self, client, pro_user):
        h = _auth(pro_user["token"])
        before = client.get(f"{API}/device/battery", headers=h).json()
        r = client.post(f"{API}/device/battery/optimize", headers=h)
        state = r.json()["state"]
        assert state["health_pct"] == before["health_pct"]
        assert state["cycle_count"] == before["cycle_count"]

    def test_optimize_sets_timestamp_and_increments_counter(self, client, pro_user):
        h = _auth(pro_user["token"])
        client.get(f"{API}/device/battery", headers=h)
        r1 = client.post(f"{API}/device/battery/optimize", headers=h)
        s1 = r1.json()["state"]
        assert s1["last_optimized_at"] is not None
        assert s1["optimizations_run"] == 1

        r2 = client.post(f"{API}/device/battery/optimize", headers=h)
        s2 = r2.json()["state"]
        assert s2["optimizations_run"] == 2

    def test_time_to_empty_scales_with_level(self, client, pro_user):
        h = _auth(pro_user["token"])
        before = client.get(f"{API}/device/battery", headers=h).json()
        r = client.post(f"{API}/device/battery/optimize", headers=h)
        state = r.json()["state"]
        if state["level"] != before["level"]:
            # Same baseline_full_hours underneath -> ratio should hold.
            ratio_before = before["time_to_empty_hours"] / before["level"] if before["level"] else 0
            ratio_after = state["time_to_empty_hours"] / state["level"] if state["level"] else 0
            assert abs(ratio_before - ratio_after) < 0.01

    def test_optimize_keeps_working_after_apps_exhausted(self, client, pro_user):
        h = _auth(pro_user["token"])
        client.get(f"{API}/device/battery", headers=h)
        # Optimize repeatedly until drain_apps is exhausted.
        last = None
        for _ in range(10):
            r = client.post(f"{API}/device/battery/optimize", headers=h)
            assert r.status_code == 200
            last = r.json()
            if len(last["state"]["drain_apps"]) == 0:
                break
        assert last["state"]["drain_apps"] == []
        # One more call on an already-exhausted list should be a safe no-op.
        r = client.post(f"{API}/device/battery/optimize", headers=h)
        assert r.status_code == 200
        final = r.json()
        assert final["apps_optimized"] == 0
        assert final["level_gained"] == 0
        assert final["state"]["drain_apps"] == []


class TestAccountDeletionCleansUp:
    def test_delete_account_removes_battery_state(self, client, pro_user):
        h = _auth(pro_user["token"])
        client.get(f"{API}/device/battery", headers=h)
        assert _db.battery_state.find_one({"user_id": pro_user["user_id"]}) is not None

        r = client.delete(f"{API}/auth/account", headers=h)
        assert r.status_code == 200
        assert _db.battery_state.find_one({"user_id": pro_user["user_id"]}) is None
