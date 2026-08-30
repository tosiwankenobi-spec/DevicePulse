"""DevicePulse backend — AI Health Coach upgrade tests.

Covers the "running assistant" additions on top of the existing one-time
/coach/daily card:

  * GET /coach/insights and POST /coach/insights/{key}/ack require auth (401)
  * Pattern insight ("learns your usage"):
      - fewer than 3 cleanups -> no pattern card yet (not enough signal)
      - 3+ cleanups -> top (most-frequent) category surfaces a monthly plan
        card, tied to that category's fixed CATEGORY_PLAN text
      - a tie between categories breaks alphabetically (deterministic)
  * Win insights ("celebrates wins"):
      - milestones (cleanup count / GB reclaimed / streak weeks) surface as
        soon as they're crossed
      - acking a win removes it from the feed permanently (no re-celebrating)
      - acking an unknown key is rejected (400)
  * Per-user isolation: one user's acked win doesn't affect another user's feed
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


def _seed_user_and_session(prefix="COACHI_"):
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
    _db.coach_seen_wins.delete_many({"user_id": user_id})


def _insert_cleanup(user_id, categories, reclaimed_mb=100.0, hours_ago=1):
    completed_at = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    _db.cleanups.insert_one({
        "id": str(uuid.uuid4()),
        "device_id": user_id,
        "categories": categories,
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
class TestCoachInsightsRequireAuth:
    def test_get_insights_requires_auth(self, client):
        r = client.get(f"{API}/coach/insights")
        assert r.status_code == 401

    def test_ack_requires_auth(self, client):
        r = client.post(f"{API}/coach/insights/win_first_clean/ack")
        assert r.status_code == 401


# ---------------- Pattern insight (learns usage) ----------------
class TestPatternInsight:
    def test_no_pattern_below_three_cleanups(self, client, seeded_user):
        _insert_cleanup(seeded_user["user_id"], ["Junk files"])
        _insert_cleanup(seeded_user["user_id"], ["Junk files"])
        r = client.get(f"{API}/coach/insights", headers=_auth(seeded_user["token"]))
        assert r.status_code == 200, r.text
        kinds = [i["kind"] for i in r.json()]
        assert "pattern" not in kinds

    def test_top_category_surfaces_plan(self, client, seeded_user):
        uid = seeded_user["user_id"]
        _insert_cleanup(uid, ["Duplicates"])
        _insert_cleanup(uid, ["Duplicates"])
        _insert_cleanup(uid, ["Junk files"])
        r = client.get(f"{API}/coach/insights", headers=_auth(seeded_user["token"]))
        pattern = next((i for i in r.json() if i["kind"] == "pattern"), None)
        assert pattern is not None
        assert pattern["key"] == "pattern_duplicates"
        assert "Duplicates" in pattern["title"]
        assert pattern["action_route"] == "/smart-scan"

    def test_tie_breaks_alphabetically(self, client, seeded_user):
        uid = seeded_user["user_id"]
        # 1 Duplicates, 1 Junk files, 1 Large files -> 3-way tie -> "Duplicates" wins alphabetically
        _insert_cleanup(uid, ["Duplicates"])
        _insert_cleanup(uid, ["Junk files"])
        _insert_cleanup(uid, ["Large files"])
        r = client.get(f"{API}/coach/insights", headers=_auth(seeded_user["token"]))
        pattern = next((i for i in r.json() if i["kind"] == "pattern"), None)
        assert pattern["key"] == "pattern_duplicates"


# ---------------- Win insights (celebrates wins) ----------------
class TestWinInsights:
    def test_first_cleanup_win_appears(self, client, seeded_user):
        _insert_cleanup(seeded_user["user_id"], ["Junk files"])
        r = client.get(f"{API}/coach/insights", headers=_auth(seeded_user["token"]))
        wins = [i["key"] for i in r.json() if i["kind"] == "win"]
        assert "win_first_clean" in wins

    def test_gb_milestone_appears_from_reclaimed_total(self, client, seeded_user):
        uid = seeded_user["user_id"]
        _insert_cleanup(uid, ["Large files"], reclaimed_mb=1200.0)  # > 1 GB lifetime
        r = client.get(f"{API}/coach/insights", headers=_auth(seeded_user["token"]))
        wins = [i["key"] for i in r.json() if i["kind"] == "win"]
        assert "win_gb_1" in wins
        assert "win_gb_5" not in wins

    def test_no_wins_for_fresh_user(self, client, seeded_user):
        r = client.get(f"{API}/coach/insights", headers=_auth(seeded_user["token"]))
        wins = [i["key"] for i in r.json() if i["kind"] == "win"]
        assert wins == []

    def test_ack_unknown_key_rejected(self, client, seeded_user):
        r = client.post(f"{API}/coach/insights/not_a_real_win/ack", headers=_auth(seeded_user["token"]))
        assert r.status_code == 400

    def test_ack_removes_win_permanently(self, client, seeded_user):
        uid = seeded_user["user_id"]
        _insert_cleanup(uid, ["Junk files"])
        h = _auth(seeded_user["token"])

        r1 = client.get(f"{API}/coach/insights", headers=h)
        assert "win_first_clean" in [i["key"] for i in r1.json() if i["kind"] == "win"]

        ack = client.post(f"{API}/coach/insights/win_first_clean/ack", headers=h)
        assert ack.status_code == 200
        assert ack.json() == {"acknowledged": True, "key": "win_first_clean"}

        r2 = client.get(f"{API}/coach/insights", headers=h)
        assert "win_first_clean" not in [i["key"] for i in r2.json() if i["kind"] == "win"]

    def test_acking_one_win_does_not_hide_other_unseen_wins(self, client, seeded_user):
        uid = seeded_user["user_id"]
        for _ in range(5):
            _insert_cleanup(uid, ["Junk files"])
        h = _auth(seeded_user["token"])

        client.post(f"{API}/coach/insights/win_first_clean/ack", headers=h)
        r = client.get(f"{API}/coach/insights", headers=h)
        wins = [i["key"] for i in r.json() if i["kind"] == "win"]
        assert "win_first_clean" not in wins
        assert "win_clean_5" in wins  # still unseen, still shown


# ---------------- Per-user isolation ----------------
class TestCoachInsightsScoping:
    def test_ack_is_per_user(self, client):
        uid_a, tok_a = _seed_user_and_session(prefix="COACHIA_")
        uid_b, tok_b = _seed_user_and_session(prefix="COACHIB_")
        try:
            _insert_cleanup(uid_a, ["Junk files"])
            _insert_cleanup(uid_b, ["Junk files"])
            s = requests.Session()
            s.post(f"{API}/coach/insights/win_first_clean/ack", headers=_auth(tok_a))
            wins_a = [i["key"] for i in s.get(f"{API}/coach/insights", headers=_auth(tok_a)).json() if i["kind"] == "win"]
            wins_b = [i["key"] for i in s.get(f"{API}/coach/insights", headers=_auth(tok_b)).json() if i["kind"] == "win"]
            assert "win_first_clean" not in wins_a
            assert "win_first_clean" in wins_b
        finally:
            _cleanup_user(uid_a, tok_a)
            _cleanup_user(uid_b, tok_b)
