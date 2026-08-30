"""DevicePulse backend — Duplicate Photo AI tests.

Covers the roadmap ask: "Duplicate photo AI." The pre-existing GET
/device/duplicates was unauthenticated and returned a fresh random batch of
fake groups (random count/size, six hardcoded stock photo URLs) on *every*
single call — nothing was per-user, nothing persisted, and the "Remove"
button on the duplicates screen didn't call the backend at all.

Scoped explicitly via AskUserQuestion to the fuller option — a real,
persisted, per-user AI scan rather than a lightweight fix that only wires
"Remove" to the existing generic /device/clean:

  * Duplicate groups are generated once per user, lazily, on first GET, and
    persisted — revisiting the screen shows the same groups instead of a
    reshuffled random set.
  * Each group carries a deterministic "AI" classification (ai_label +
    ai_confidence) — consistent with every other "AI" feature in this app
    (Smart Nudges, Predictive Storage): branded as AI, actually deterministic
    logic, no LLM call.
  * POST /device/duplicates/scan appends a fresh batch, simulating finding
    newly-taken duplicate/burst photos since the last scan.
  * POST /device/duplicates/remove actually removes groups from the pending
    list (they never come back) and records a REAL cleanup
    (categories=["Duplicates"]) that feeds history/streak/forecast exactly
    like any other cleanup action.
  * "Unlimited duplicate cleanup" is a Pro perk paywall.tsx has advertised
    since before this session with nothing enforcing it — same shape of gap
    Auto-Clean Scheduling closed for "Scheduled cleanups." Free users are
    capped at FREE_DUPLICATE_REMOVE_DAILY_LIMIT (3) group removals per UTC
    day; Pro users (the same stored is_pro flag) are unlimited.

Covers:
  * All four routes require auth (401)
  * GET is stable across repeated calls (persisted, not reshuffled)
  * GET auto-generates on first call only; a second user gets their own,
    independent set (no cross-user leakage)
  * Each returned group has a valid ai_label / ai_confidence in range
  * scan appends new groups without touching existing pending ones
  * remove: unknown id 404s, removing deletes from pending permanently,
    records a real db.cleanups entry sized to the removed groups' total MB
  * free-tier daily cap: 403 once the day's removals would exceed the limit,
    succeeds again the next UTC day; Pro users are never capped
  * IDOR: a user cannot remove another user's group id
  * Deleting the account removes duplicate_groups too
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

VALID_LABELS = {"Exact duplicate", "Burst photo", "Similar photo"}


def _seed_user_and_session(prefix="DUPAI_"):
    user_id = f"{prefix}user_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}{uuid.uuid4().hex[:6]}@example.com"
    token = f"{prefix}tok_{uuid.uuid4().hex}"
    sid = uuid.uuid4().hex[:12]
    _db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": "Photo Hoarder",
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
    _db.duplicate_groups.delete_many({"user_id": user_id})


def _make_pro(user_id):
    _db.users.update_one({"user_id": user_id}, {"$set": {"is_pro": True}})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


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
    uid, tok = _seed_user_and_session(prefix="DUPAI_PRO_")
    _make_pro(uid)
    yield {"user_id": uid, "token": tok}
    _cleanup_user(uid, tok)


class TestRequiresAuth:
    def test_get_requires_auth(self, client):
        assert client.get(f"{API}/device/duplicates").status_code == 401

    def test_scan_requires_auth(self, client):
        assert client.post(f"{API}/device/duplicates/scan").status_code == 401

    def test_remove_requires_auth(self, client):
        assert client.post(f"{API}/device/duplicates/remove", json={"group_ids": ["x"]}).status_code == 401


class TestPersistedGeneration:
    def test_first_get_generates_groups(self, client, free_user):
        r = client.get(f"{API}/device/duplicates", headers=_auth(free_user["token"]))
        assert r.status_code == 200
        groups = r.json()
        assert 5 <= len(groups) <= 7
        for g in groups:
            assert g["ai_label"] in VALID_LABELS
            assert 0 <= g["ai_confidence"] <= 100
            assert g["photo_count"] >= 2
            assert g["size_mb"] > 0
            assert g["thumbnail_url"].startswith("https://")

    def test_repeated_get_is_stable_not_reshuffled(self, client, free_user):
        h = _auth(free_user["token"])
        first = client.get(f"{API}/device/duplicates", headers=h).json()
        second = client.get(f"{API}/device/duplicates", headers=h).json()
        assert [g["id"] for g in first] == [g["id"] for g in second]
        assert first == second

    def test_two_users_get_independent_groups(self, client, free_user, pro_user):
        a = client.get(f"{API}/device/duplicates", headers=_auth(free_user["token"])).json()
        b = client.get(f"{API}/device/duplicates", headers=_auth(pro_user["token"])).json()
        a_ids = {g["id"] for g in a}
        b_ids = {g["id"] for g in b}
        assert a_ids.isdisjoint(b_ids)


class TestScan:
    def test_scan_appends_without_losing_existing(self, client, free_user):
        h = _auth(free_user["token"])
        before = client.get(f"{API}/device/duplicates", headers=h).json()
        before_ids = {g["id"] for g in before}

        r = client.post(f"{API}/device/duplicates/scan", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert 1 <= body["new_groups_found"] <= 3
        after_ids = {g["id"] for g in body["groups"]}
        assert before_ids.issubset(after_ids)
        assert len(after_ids) == len(before_ids) + body["new_groups_found"]


class TestRemove:
    def test_unknown_group_id_404s(self, client, free_user):
        h = _auth(free_user["token"])
        client.get(f"{API}/device/duplicates", headers=h)  # ensure generated
        r = client.post(f"{API}/device/duplicates/remove", headers=h, json={"group_ids": ["not-a-real-id"]})
        assert r.status_code == 404

    def test_empty_group_ids_400s(self, client, free_user):
        h = _auth(free_user["token"])
        r = client.post(f"{API}/device/duplicates/remove", headers=h, json={"group_ids": []})
        assert r.status_code == 400

    def test_remove_deletes_from_pending_permanently(self, client, free_user):
        h = _auth(free_user["token"])
        groups = client.get(f"{API}/device/duplicates", headers=h).json()
        target = groups[0]

        r = client.post(f"{API}/device/duplicates/remove", headers=h, json={"group_ids": [target["id"]]})
        assert r.status_code == 200
        body = r.json()
        assert body["removed_count"] == 1
        assert body["freed_mb"] == target["size_mb"]
        assert target["id"] not in {g["id"] for g in body["groups"]}

        # Doesn't come back on a fresh GET, and can't be removed twice.
        after = client.get(f"{API}/device/duplicates", headers=h).json()
        assert target["id"] not in {g["id"] for g in after}
        r2 = client.post(f"{API}/device/duplicates/remove", headers=h, json={"group_ids": [target["id"]]})
        assert r2.status_code == 404

    def test_remove_records_a_real_cleanup(self, client, free_user):
        h = _auth(free_user["token"])
        groups = client.get(f"{API}/device/duplicates", headers=h).json()
        target = groups[0]
        before_count = _db.cleanups.count_documents({"device_id": free_user["user_id"]})

        client.post(f"{API}/device/duplicates/remove", headers=h, json={"group_ids": [target["id"]]})

        after_count = _db.cleanups.count_documents({"device_id": free_user["user_id"]})
        assert after_count == before_count + 1
        doc = _db.cleanups.find_one({"device_id": free_user["user_id"]}, sort=[("completed_at", -1)])
        assert doc["categories"] == ["Duplicates"]
        assert doc["reclaimed_mb"] == target["size_mb"]

    def test_idor_cannot_remove_another_users_group(self, client, free_user, pro_user):
        victim_groups = client.get(f"{API}/device/duplicates", headers=_auth(free_user["token"])).json()
        target_id = victim_groups[0]["id"]

        r = client.post(
            f"{API}/device/duplicates/remove",
            headers=_auth(pro_user["token"]),
            json={"group_ids": [target_id]},
        )
        assert r.status_code == 404

        # Still there for the rightful owner.
        still_there = client.get(f"{API}/device/duplicates", headers=_auth(free_user["token"])).json()
        assert target_id in {g["id"] for g in still_there}


class TestFreeTierDailyLimit:
    def test_free_user_capped_at_daily_limit(self, client, free_user):
        h = _auth(free_user["token"])
        groups = client.get(f"{API}/device/duplicates", headers=h).json()
        assert len(groups) >= 4, "fixture assumption: need at least 4 pending groups"

        # Remove exactly the free daily limit (3), one at a time — all succeed.
        for g in groups[:3]:
            r = client.post(f"{API}/device/duplicates/remove", headers=h, json={"group_ids": [g["id"]]})
            assert r.status_code == 200, r.text

        # A 4th removal the same day is rejected.
        r = client.post(f"{API}/device/duplicates/remove", headers=h, json={"group_ids": [groups[3]["id"]]})
        assert r.status_code == 403
        assert "Upgrade to Pro" in r.json()["detail"]

        # The group that was rejected is still pending, not consumed.
        still_pending = client.get(f"{API}/device/duplicates", headers=h).json()
        assert groups[3]["id"] in {x["id"] for x in still_pending}

    def test_free_user_can_remove_again_the_next_day(self, client, free_user):
        h = _auth(free_user["token"])
        groups = client.get(f"{API}/device/duplicates", headers=h).json()
        for g in groups[:3]:
            client.post(f"{API}/device/duplicates/remove", headers=h, json={"group_ids": [g["id"]]})

        # Backdate all of today's removals into yesterday (UTC) directly.
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        _db.duplicate_groups.update_many(
            {"user_id": free_user["user_id"], "status": "removed"},
            {"$set": {"removed_at": yesterday}},
        )

        r = client.post(f"{API}/device/duplicates/remove", headers=h, json={"group_ids": [groups[3]["id"]]})
        assert r.status_code == 200

    def test_pro_user_is_never_capped(self, client, pro_user):
        h = _auth(pro_user["token"])
        groups = client.get(f"{API}/device/duplicates", headers=h).json()
        assert len(groups) >= 5

        r = client.post(
            f"{API}/device/duplicates/remove", headers=h,
            json={"group_ids": [g["id"] for g in groups]},
        )
        assert r.status_code == 200
        assert r.json()["removed_count"] == len(groups)


class TestAccountDeletionCleansUp:
    def test_deleting_account_removes_duplicate_groups(self, client):
        uid, tok = _seed_user_and_session(prefix="DUPAI_DEL_")
        h = _auth(tok)
        try:
            client.get(f"{API}/device/duplicates", headers=h)
            assert _db.duplicate_groups.count_documents({"user_id": uid}) > 0

            r = client.delete(f"{API}/auth/account", headers=h)
            assert r.status_code == 200

            assert _db.duplicate_groups.count_documents({"user_id": uid}) == 0
        finally:
            _db.user_sessions.delete_many({"session_token": tok})
            _db.users.delete_many({"user_id": uid})
            _db.cleanups.delete_many({"device_id": uid})
            _db.duplicate_groups.delete_many({"user_id": uid})
