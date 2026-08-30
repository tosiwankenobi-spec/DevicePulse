"""DevicePulse backend — Auto-Clean Scheduling (Pro-only) tests.

Covers the roadmap ask: "Auto-Clean Scheduling (Pro-only)" — the app running
a cleanup on the user's behalf on a recurring schedule, not just nudging them
to do it themselves (that's Smart Nudges, already shipped).

Two design decisions, both made explicitly via AskUserQuestion / discovery
before writing code:

  1. Pro gating: the backend has no RevenueCat secret key or webhook
     configured in this sandbox, so it can't independently verify a
     purchase. Per explicit user choice, this stores a real, persisted
     `is_pro` flag on the user record (POST /entitlements/sync, called by
     the client once RevenueCat confirms an active entitlement) and every
     mutating auto-clean endpoint checks that STORED flag server-side —
     never a value passed on the individual request. Deleting/disabling a
     schedule is NOT Pro-gated (a lapsed subscriber can still turn it off).

  2. There's no real background scheduler in this sandbox (same constraint
     Predictive Storage and Coach Insights already worked within) — so
     POST /autoclean/run-if-due is the same "lazy cron" pattern used
     everywhere else in this app: the client calls it (e.g. once on app
     open) and it decides for itself whether a run is due, based on
     frequency + last_run_at (+ day_of_week for weekly).

Covers:
  * GET/POST /entitlements/*, GET/PUT/DELETE /autoclean/schedule, and
    POST /autoclean/run-if-due all require auth (401)
  * is_pro defaults false; POST /entitlements/sync persists it, GET
    /entitlements/me reflects it
  * GET /autoclean/schedule is nullable until explicitly created (same
    design as GET /family/group and GET /reports/mine)
  * PUT /autoclean/schedule is 403 without is_pro, 200 once synced Pro
  * Validation: bad frequency, weekly missing day_of_week, empty
    categories, and "Large files" (deliberately excluded from what
    auto-clean may touch) all 400
  * DELETE works regardless of Pro status
  * run-if-due: no schedule / disabled / not-pro / not-due are all
    reason-coded no-ops that never touch db.cleanups; a due daily or
    weekly schedule actually records a real cleanup with the schedule's
    own categories and moves last_run_at forward; weekly only fires on the
    configured weekday
  * Downgrading from Pro leaves the schedule itself untouched (it just
    goes inert) rather than deleting it
  * Deleting the account removes autoclean_schedules too
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


def _seed_user_and_session(prefix="ACLEAN_"):
    user_id = f"{prefix}user_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}{uuid.uuid4().hex[:6]}@example.com"
    token = f"{prefix}tok_{uuid.uuid4().hex}"
    sid = uuid.uuid4().hex[:12]
    _db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": "Auto Cleaner",
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
    _db.autoclean_schedules.delete_many({"user_id": user_id})


def _make_pro(user_id):
    _db.users.update_one({"user_id": user_id}, {"$set": {"is_pro": True}})


@pytest.fixture()
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture()
def pro_user():
    uid, tok = _seed_user_and_session()
    _make_pro(uid)
    yield {"user_id": uid, "token": tok}
    _cleanup_user(uid, tok)


@pytest.fixture()
def free_user():
    uid, tok = _seed_user_and_session(prefix="ACLEAN_FREE_")
    yield {"user_id": uid, "token": tok}
    _cleanup_user(uid, tok)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


DAILY_BODY = {"enabled": True, "frequency": "daily", "categories": ["Junk files"]}


class TestRequiresAuth:
    def test_entitlements_me_requires_auth(self, client):
        assert client.get(f"{API}/entitlements/me").status_code == 401

    def test_entitlements_sync_requires_auth(self, client):
        assert client.post(f"{API}/entitlements/sync", json={"is_pro": True}).status_code == 401

    def test_get_schedule_requires_auth(self, client):
        assert client.get(f"{API}/autoclean/schedule").status_code == 401

    def test_put_schedule_requires_auth(self, client):
        assert client.put(f"{API}/autoclean/schedule", json=DAILY_BODY).status_code == 401

    def test_delete_schedule_requires_auth(self, client):
        assert client.delete(f"{API}/autoclean/schedule").status_code == 401

    def test_run_if_due_requires_auth(self, client):
        assert client.post(f"{API}/autoclean/run-if-due").status_code == 401


class TestEntitlementSync:
    def test_defaults_to_not_pro(self, client, free_user):
        r = client.get(f"{API}/entitlements/me", headers=_auth(free_user["token"]))
        assert r.status_code == 200
        assert r.json() == {"is_pro": False}

    def test_sync_persists_and_me_reflects_it(self, client, free_user):
        h = _auth(free_user["token"])
        r = client.post(f"{API}/entitlements/sync", headers=h, json={"is_pro": True})
        assert r.status_code == 200
        assert r.json() == {"is_pro": True}
        assert client.get(f"{API}/entitlements/me", headers=h).json() == {"is_pro": True}

        # And it can go back down (a lapsed subscription).
        client.post(f"{API}/entitlements/sync", headers=h, json={"is_pro": False})
        assert client.get(f"{API}/entitlements/me", headers=h).json() == {"is_pro": False}


class TestProGating:
    def test_put_schedule_requires_pro(self, client, free_user):
        r = client.put(f"{API}/autoclean/schedule", headers=_auth(free_user["token"]), json=DAILY_BODY)
        assert r.status_code == 403

    def test_put_schedule_succeeds_once_pro(self, client, pro_user):
        r = client.put(f"{API}/autoclean/schedule", headers=_auth(pro_user["token"]), json=DAILY_BODY)
        assert r.status_code == 200, r.text
        assert r.json()["frequency"] == "daily"

    def test_delete_allowed_without_pro(self, client, free_user):
        # Nothing to delete, but the route itself must not be Pro-gated.
        r = client.delete(f"{API}/autoclean/schedule", headers=_auth(free_user["token"]))
        assert r.status_code == 200
        assert r.json() == {"deleted": False}


class TestScheduleValidation:
    def test_bad_frequency_rejected(self, client, pro_user):
        body = {**DAILY_BODY, "frequency": "hourly"}
        r = client.put(f"{API}/autoclean/schedule", headers=_auth(pro_user["token"]), json=body)
        assert r.status_code == 400

    def test_weekly_requires_day_of_week(self, client, pro_user):
        body = {"enabled": True, "frequency": "weekly", "categories": ["Junk files"]}
        r = client.put(f"{API}/autoclean/schedule", headers=_auth(pro_user["token"]), json=body)
        assert r.status_code == 400

    def test_empty_categories_rejected(self, client, pro_user):
        body = {**DAILY_BODY, "categories": []}
        r = client.put(f"{API}/autoclean/schedule", headers=_auth(pro_user["token"]), json=body)
        assert r.status_code == 400

    def test_large_files_not_allowed(self, client, pro_user):
        """Deliberately excluded — the one category likely to contain
        something worth reviewing before an unattended deletion."""
        body = {**DAILY_BODY, "categories": ["Large files"]}
        r = client.put(f"{API}/autoclean/schedule", headers=_auth(pro_user["token"]), json=body)
        assert r.status_code == 400

    def test_valid_weekly_schedule_accepted(self, client, pro_user):
        body = {"enabled": True, "frequency": "weekly", "day_of_week": 6, "categories": ["Duplicates", "App cache"]}
        r = client.put(f"{API}/autoclean/schedule", headers=_auth(pro_user["token"]), json=body)
        assert r.status_code == 200, r.text
        assert r.json()["day_of_week"] == 6


class TestScheduleLifecycle:
    def test_no_schedule_until_explicitly_created(self, client, pro_user):
        r = client.get(f"{API}/autoclean/schedule", headers=_auth(pro_user["token"]))
        assert r.status_code == 200
        assert r.json() is None

    def test_create_then_get_reflects_it(self, client, pro_user):
        h = _auth(pro_user["token"])
        created = client.put(f"{API}/autoclean/schedule", headers=h, json=DAILY_BODY).json()
        fetched = client.get(f"{API}/autoclean/schedule", headers=h).json()
        assert fetched == created

    def test_update_preserves_last_run_at(self, client, pro_user):
        h = _auth(pro_user["token"])
        client.put(f"{API}/autoclean/schedule", headers=h, json=DAILY_BODY)
        stamp = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        _db.autoclean_schedules.update_one({"user_id": pro_user["user_id"]}, {"$set": {"last_run_at": stamp}})

        updated = client.put(
            f"{API}/autoclean/schedule", headers=h,
            json={"enabled": False, "frequency": "daily", "categories": ["Junk files", "App cache"]},
        ).json()
        assert updated["enabled"] is False
        assert updated["last_run_at"] == stamp  # not clobbered by the update

    def test_delete_removes_it(self, client, pro_user):
        h = _auth(pro_user["token"])
        client.put(f"{API}/autoclean/schedule", headers=h, json=DAILY_BODY)
        r = client.delete(f"{API}/autoclean/schedule", headers=h)
        assert r.status_code == 200 and r.json() == {"deleted": True}
        assert client.get(f"{API}/autoclean/schedule", headers=h).json() is None


class TestRunIfDue:
    def test_no_schedule_is_a_noop(self, client, pro_user):
        r = client.post(f"{API}/autoclean/run-if-due", headers=_auth(pro_user["token"]))
        assert r.status_code == 200
        assert r.json() == {"ran": False, "reason": "no_schedule", "reclaimed_mb": None, "categories": None}

    def test_disabled_schedule_is_a_noop(self, client, pro_user):
        h = _auth(pro_user["token"])
        client.put(f"{API}/autoclean/schedule", headers=h, json={**DAILY_BODY, "enabled": False})
        r = client.post(f"{API}/autoclean/run-if-due", headers=h)
        assert r.json()["reason"] == "disabled"

    def test_not_pro_is_a_noop_but_schedule_survives(self, client, free_user):
        h = _auth(free_user["token"])
        # Sync pro just long enough to create the schedule, then lapse.
        client.post(f"{API}/entitlements/sync", headers=h, json={"is_pro": True})
        client.put(f"{API}/autoclean/schedule", headers=h, json=DAILY_BODY)
        client.post(f"{API}/entitlements/sync", headers=h, json={"is_pro": False})

        r = client.post(f"{API}/autoclean/run-if-due", headers=h)
        assert r.json()["reason"] == "not_pro"
        assert client.get(f"{API}/autoclean/schedule", headers=h).json() is not None, \
            "downgrading should leave the schedule config intact, not delete it"

    def test_daily_fresh_schedule_runs_immediately_and_then_cools_down(self, client, pro_user):
        h = _auth(pro_user["token"])
        client.put(f"{API}/autoclean/schedule", headers=h, json={**DAILY_BODY, "categories": ["Junk files", "App cache"]})

        before_count = _db.cleanups.count_documents({"device_id": pro_user["user_id"]})
        r = client.post(f"{API}/autoclean/run-if-due", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert body["ran"] is True
        assert body["categories"] == ["Junk files", "App cache"]
        assert body["reclaimed_mb"] > 0

        after_count = _db.cleanups.count_documents({"device_id": pro_user["user_id"]})
        assert after_count == before_count + 1
        doc = _db.cleanups.find_one({"device_id": pro_user["user_id"]}, sort=[("completed_at", -1)])
        assert doc["categories"] == ["Junk files", "App cache"]

        # Immediately again: cooldown means it should NOT run twice in a row.
        r2 = client.post(f"{API}/autoclean/run-if-due", headers=h)
        assert r2.json() == {"ran": False, "reason": "not_due", "reclaimed_mb": None, "categories": None}

    def test_daily_due_again_after_cooldown_window(self, client, pro_user):
        h = _auth(pro_user["token"])
        client.put(f"{API}/autoclean/schedule", headers=h, json=DAILY_BODY)
        stale = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        _db.autoclean_schedules.update_one({"user_id": pro_user["user_id"]}, {"$set": {"last_run_at": stale}})

        r = client.post(f"{API}/autoclean/run-if-due", headers=h)
        assert r.json()["ran"] is True

    def test_weekly_only_fires_on_the_configured_weekday(self, client, pro_user):
        h = _auth(pro_user["token"])
        today = datetime.now(timezone.utc).weekday()
        other_day = (today + 3) % 7
        client.put(
            f"{API}/autoclean/schedule", headers=h,
            json={"enabled": True, "frequency": "weekly", "day_of_week": other_day, "categories": ["Duplicates"]},
        )
        r = client.post(f"{API}/autoclean/run-if-due", headers=h)
        assert r.json()["reason"] == "not_due"

    def test_weekly_runs_on_the_configured_weekday(self, client, pro_user):
        h = _auth(pro_user["token"])
        today = datetime.now(timezone.utc).weekday()
        client.put(
            f"{API}/autoclean/schedule", headers=h,
            json={"enabled": True, "frequency": "weekly", "day_of_week": today, "categories": ["Duplicates"]},
        )
        r = client.post(f"{API}/autoclean/run-if-due", headers=h)
        assert r.json()["ran"] is True
        assert r.json()["categories"] == ["Duplicates"]

        # Same day, already ran -> cools down for the rest of the week.
        r2 = client.post(f"{API}/autoclean/run-if-due", headers=h)
        assert r2.json()["reason"] == "not_due"


class TestAccountDeletionCleansUp:
    def test_deleting_account_removes_autoclean_schedule(self, client):
        uid, tok = _seed_user_and_session(prefix="ACLEAN_DEL_")
        h = _auth(tok)
        try:
            _make_pro(uid)
            client.put(f"{API}/autoclean/schedule", headers=h, json=DAILY_BODY)
            assert _db.autoclean_schedules.count_documents({"user_id": uid}) == 1

            r = client.delete(f"{API}/auth/account", headers=h)
            assert r.status_code == 200

            assert _db.autoclean_schedules.count_documents({"user_id": uid}) == 0
        finally:
            _db.user_sessions.delete_many({"session_token": tok})
            _db.users.delete_many({"user_id": uid})
            _db.cleanups.delete_many({"device_id": uid})
            _db.autoclean_schedules.delete_many({"user_id": uid})
