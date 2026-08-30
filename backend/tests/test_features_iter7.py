"""
Iteration 7 feature tests:
- Daily Pulse Check (GET /api/pulse/today, POST /api/pulse/check)
- Smart Nudges (GET /api/nudges)
- Family remote-optimize (POST /api/family/member/{id}/optimize)
- Duplicates enrichment (photos[], best_index)
- Auth / IDOR checks
"""

import os
import time
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = os.environ['EXPO_PUBLIC_BACKEND_URL'].rstrip('/') if os.environ.get('EXPO_PUBLIC_BACKEND_URL') else None
if not BASE_URL:
    # frontend/.env holds the public URL
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('EXPO_PUBLIC_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                break

API = f"{BASE_URL}/api"
TOKEN = "feat-token-123"
USER_ID = "user_feat_test"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# ---- Mongo setup: clean pulse_checks for the test user so we have a fresh slate.
_mc = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
_db = _mc[os.environ.get('DB_NAME', 'test_database')]


@pytest.fixture(scope="module", autouse=True)
def clean_pulse():
    _db.pulse_checks.delete_many({"user_id": USER_ID})
    # keep at least one family member for optimize tests
    yield
    _db.pulse_checks.delete_many({"user_id": USER_ID})


# ==================== Auth guards ====================
class TestAuthGuards:
    def test_pulse_today_requires_auth(self):
        r = requests.get(f"{API}/pulse/today")
        assert r.status_code == 401

    def test_pulse_check_requires_auth(self):
        r = requests.post(f"{API}/pulse/check")
        assert r.status_code == 401

    def test_nudges_requires_auth(self):
        r = requests.get(f"{API}/nudges")
        assert r.status_code == 401

    def test_family_optimize_requires_auth(self):
        r = requests.post(f"{API}/family/member/anything/optimize")
        assert r.status_code == 401

    def test_bad_token_rejected(self):
        r = requests.get(f"{API}/pulse/today", headers={"Authorization": "Bearer garbage"})
        assert r.status_code == 401


# ==================== Daily Pulse ====================
class TestDailyPulse:
    def test_today_before_check(self):
        r = requests.get(f"{API}/pulse/today", headers=HEADERS)
        assert r.status_code == 200
        d = r.json()
        assert d["checked_today"] is False
        assert d["score"] is None
        assert d["daily_streak"] == 0
        assert d["best_streak"] == 0

    def test_check_first_time(self):
        r = requests.post(f"{API}/pulse/check", headers=HEADERS)
        assert r.status_code == 200
        d = r.json()
        assert 55 <= d["score"] <= 98
        assert d["daily_streak"] >= 1
        assert d["best_streak"] >= d["daily_streak"]
        assert d["already_checked"] is False
        assert "delta" in d

    def test_check_twice_same_day_no_double_count(self):
        r1 = requests.post(f"{API}/pulse/check", headers=HEADERS).json()
        r2 = requests.post(f"{API}/pulse/check", headers=HEADERS)
        assert r2.status_code == 200
        d = r2.json()
        assert d["already_checked"] is True
        assert d["score"] == r1["score"]
        assert d["daily_streak"] == r1["daily_streak"]  # streak did not bump

    def test_today_after_check(self):
        r = requests.get(f"{API}/pulse/today", headers=HEADERS)
        d = r.json()
        assert d["checked_today"] is True
        assert d["score"] is not None
        assert d["daily_streak"] >= 1


# ==================== Smart Nudges ====================
class TestNudges:
    def test_shape(self):
        r = requests.get(f"{API}/nudges", headers=HEADERS)
        assert r.status_code == 200
        d = r.json()
        assert "nudges" in d and isinstance(d["nudges"], list)
        assert "storage_pct" in d and isinstance(d["storage_pct"], int)
        assert "days_until_full" in d and isinstance(d["days_until_full"], int)
        assert len(d["nudges"]) <= 3
        for n in d["nudges"]:
            for k in ("id", "type", "priority", "tone", "icon", "title", "body", "action_label", "action_route"):
                assert k in n, f"nudge missing {k}"

    def test_sorted_by_priority_desc(self):
        d = requests.get(f"{API}/nudges", headers=HEADERS).json()
        prios = [n["priority"] for n in d["nudges"]]
        assert prios == sorted(prios, reverse=True)


# ==================== Family optimize ====================
class TestFamilyOptimize:
    @pytest.fixture(scope="class")
    def member_id(self):
        # ensure at least one member exists for this test user
        members = requests.get(f"{API}/family", headers=HEADERS).json()
        if not members:
            r = requests.post(
                f"{API}/family/member",
                headers=HEADERS,
                json={"name": "TEST_Optimize", "device_type": "phone"},
            )
            assert r.status_code == 200
            return r.json()["id"]
        return members[0]["id"]

    def test_family_list_includes_new_fields(self):
        r = requests.get(f"{API}/family", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        if data:
            m = data[0]
            assert "health_score" in m
            assert "last_optimized" in m  # may be None

    def test_optimize_success(self, member_id):
        r = requests.post(f"{API}/family/member/{member_id}/optimize", headers=HEADERS)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"] == member_id
        assert 90 <= d["health_score"] <= 98
        assert d["reclaimed_mb"] > 0
        assert d["last_optimized"]

    def test_optimize_persists_to_family_list(self, member_id):
        # GET after optimize should show updated health & last_optimized
        members = requests.get(f"{API}/family", headers=HEADERS).json()
        m = next((x for x in members if x["id"] == member_id), None)
        assert m is not None
        assert m["health_score"] >= 90
        assert m["last_optimized"] is not None

    def test_optimize_unknown_id_returns_404(self):
        r = requests.post(f"{API}/family/member/does-not-exist/optimize", headers=HEADERS)
        assert r.status_code == 404


# ==================== Duplicates enrichment ====================
class TestDuplicates:
    def test_groups_have_photos_and_best_index(self):
        # /device/duplicates is public per test_credentials notes
        r = requests.get(f"{API}/device/duplicates")
        assert r.status_code == 200
        groups = r.json()
        assert len(groups) > 0
        for g in groups:
            assert "photos" in g and isinstance(g["photos"], list)
            assert len(g["photos"]) == g["count"]
            for p in g["photos"]:
                assert "quality" in p
                assert "size_mb" in p
            bi = g["best_index"]
            assert 0 <= bi < len(g["photos"])
            best_q = g["photos"][bi]["quality"]
            for p in g["photos"]:
                assert p["quality"] <= best_q
