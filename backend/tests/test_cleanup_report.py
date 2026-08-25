"""DevicePulse backend — Shareable Cleanup Report tests.

Covers the roadmap ask: "Shareable Cleanup Report." Before this feature, the
only "share" surface in the app was the post-cleanup results screen's local
"Share result" button — a client-side screenshot + share-sheet call with
nothing persisted and nothing a recipient without the app could open. This
feature is scoped (per explicit user choice, "Real persisted,
publicly-viewable report") as a real backend-generated, DB-persisted report
with a unique share code and a genuinely public, unauthenticated view route:

  * POST /reports/generate and GET /reports/mine require auth (401 without
    a token); GET /reports/{share_code} is intentionally PUBLIC — no auth
    required, since the whole point is that someone without an account can
    open the link.
  * GET /reports/mine is nullable-by-design (mirrors the Family Dashboard's
    GET /family/group): it does NOT auto-create a report on a plain read.
    Only POST /reports/generate creates one.
  * A generated report reflects the user's REAL aggregate history — total
    cleanups, total GB reclaimed, current streak, top category, current
    pulse score/status, days-until-full — via the same helpers used
    elsewhere (_compute_streak_data, _compute_forecast,
    _compute_daily_pulse_score, _detect_top_category), not fabricated
    numbers. Proven by giving two users different histories and checking
    their reports differ accordingly.
  * Each POST /reports/generate call mints a NEW share code and freezes a
    new snapshot; it does not mutate a previously-generated/shared report,
    and GET /reports/mine returns the most recently generated one.
  * GET /reports/{share_code} never exposes user_id or email — only the
    frozen public-safe fields (first name, stats). An unknown share code is
    a 404.
  * Deleting the account removes the user's cleanup_reports too (regression
    guard alongside the other owned collections DELETE /auth/account wipes).
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


def _seed_user_and_session(prefix="CRPT_", name="Reporty Tester"):
    user_id = f"{prefix}user_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}{uuid.uuid4().hex[:6]}@example.com"
    token = f"{prefix}tok_{uuid.uuid4().hex}"
    sid = uuid.uuid4().hex[:12]
    _db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": name,
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
    _db.cleanup_reports.delete_many({"user_id": user_id})


def _insert_cleanup(user_id, hours_ago, reclaimed_mb=100.0, categories=None):
    completed_at = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    _db.cleanups.insert_one({
        "id": str(uuid.uuid4()),
        "device_id": user_id,
        "categories": categories or ["Junk files"],
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


class TestReportsRequireAuth:
    def test_mine_requires_auth(self, client):
        assert client.get(f"{API}/reports/mine").status_code == 401

    def test_generate_requires_auth(self, client):
        assert client.post(f"{API}/reports/generate").status_code == 401

    def test_public_view_does_not_require_auth(self, client):
        # A bogus code with no token should 404 (not found), never 401 —
        # proving the route itself is genuinely public.
        r = client.get(f"{API}/reports/CR-NOTREAL")
        assert r.status_code == 404


class TestNullableUntilGenerated:
    def test_no_report_until_explicitly_generated(self, client, seeded_user):
        r = client.get(f"{API}/reports/mine", headers=_auth(seeded_user["token"]))
        assert r.status_code == 200
        assert r.json() is None

    def test_generate_creates_a_report_with_share_code(self, client, seeded_user):
        r = client.post(f"{API}/reports/generate", headers=_auth(seeded_user["token"]))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["share_code"].startswith("CR-")
        assert body["total_cleanups"] == 0
        assert body["total_reclaimed_mb"] == 0
        assert body["display_name"] == "Reporty"  # first name only, from "Reporty Tester"

        # GET /reports/mine now reflects it.
        r2 = client.get(f"{API}/reports/mine", headers=_auth(seeded_user["token"]))
        assert r2.json()["share_code"] == body["share_code"]

    def test_regenerate_mints_a_new_code_and_mine_returns_the_latest(self, client, seeded_user):
        h = _auth(seeded_user["token"])
        first = client.post(f"{API}/reports/generate", headers=h).json()
        second = client.post(f"{API}/reports/generate", headers=h).json()
        assert first["share_code"] != second["share_code"]

        latest = client.get(f"{API}/reports/mine", headers=h).json()
        assert latest["share_code"] == second["share_code"]

        # The OLD code still resolves publicly — regenerating didn't delete it.
        r = client.get(f"{API}/reports/{first['share_code']}")
        assert r.status_code == 200
        assert r.json()["share_code"] == first["share_code"]


class TestRealAggregateData:
    def test_report_reflects_real_history_not_fabricated(self, client, seeded_user):
        h = _auth(seeded_user["token"])
        for _ in range(4):
            _insert_cleanup(seeded_user["user_id"], hours_ago=2, reclaimed_mb=250.0, categories=["Junk files"])
        report = client.post(f"{API}/reports/generate", headers=h).json()
        assert report["total_cleanups"] == 4
        assert report["total_reclaimed_mb"] == 1000.0
        assert report["total_reclaimed_gb"] == round(1000.0 / 1024, 2)
        assert report["top_category"] == "Junk files"

        # Cross-check against the same source-of-truth endpoints used elsewhere.
        streak = client.get(f"{API}/streak", headers=h).json()
        forecast = client.get(f"{API}/forecast", headers=h).json()
        assert report["current_streak_weeks"] == streak["current_streak_weeks"]
        assert report["days_until_full"] == forecast["days_until_full"]

    def test_two_users_with_different_histories_get_different_reports(self, client):
        a_id, a_tok = _seed_user_and_session(prefix="CRPT_A_", name="Alice Aardvark")
        b_id, b_tok = _seed_user_and_session(prefix="CRPT_B_", name="Bob Builder")
        try:
            for _ in range(6):
                _insert_cleanup(a_id, hours_ago=1, reclaimed_mb=400.0, categories=["Duplicates"])
            # B has no history at all.
            ra = client.post(f"{API}/reports/generate", headers=_auth(a_tok)).json()
            rb = client.post(f"{API}/reports/generate", headers=_auth(b_tok)).json()
            assert ra["total_cleanups"] != rb["total_cleanups"]
            assert ra["total_reclaimed_mb"] != rb["total_reclaimed_mb"]
            assert ra["display_name"] == "Alice"
            assert rb["display_name"] == "Bob"
            assert ra["top_category"] == "Duplicates"
            assert rb["top_category"] is None  # not enough history for a pattern yet
        finally:
            _cleanup_user(a_id, a_tok)
            _cleanup_user(b_id, b_tok)


class TestPublicView:
    def test_public_view_matches_generated_report(self, client, seeded_user):
        h = _auth(seeded_user["token"])
        _insert_cleanup(seeded_user["user_id"], hours_ago=3, reclaimed_mb=150.0)
        generated = client.post(f"{API}/reports/generate", headers=h).json()

        r = client.get(f"{API}/reports/{generated['share_code']}")
        assert r.status_code == 200
        public = r.json()
        assert public == generated

    def test_public_view_never_exposes_user_id_or_email(self, client, seeded_user):
        h = _auth(seeded_user["token"])
        generated = client.post(f"{API}/reports/generate", headers=h).json()
        r = client.get(f"{API}/reports/{generated['share_code']}")
        body = r.json()
        assert "user_id" not in body
        assert "email" not in body
        assert seeded_user["user_id"] not in str(body)

    def test_unknown_share_code_is_404(self, client):
        r = client.get(f"{API}/reports/CR-ZZZZZZ")
        assert r.status_code == 404

    def test_share_code_lookup_is_case_insensitive(self, client, seeded_user):
        h = _auth(seeded_user["token"])
        generated = client.post(f"{API}/reports/generate", headers=h).json()
        r = client.get(f"{API}/reports/{generated['share_code'].lower()}")
        assert r.status_code == 200
        assert r.json()["share_code"] == generated["share_code"]


class TestPublicHtmlPage:
    """GET /r/{share_code} (outside the /api prefix) is the human-facing
    counterpart to the JSON route — a real page, not raw JSON, so a link
    opened in a plain browser actually shows something."""

    def test_html_page_renders_real_stats(self, client, seeded_user):
        h = _auth(seeded_user["token"])
        # _detect_top_category needs 3+ cleanups before it'll name a pattern.
        for _ in range(3):
            _insert_cleanup(seeded_user["user_id"], hours_ago=1, reclaimed_mb=800.0, categories=["Large files"])
        generated = client.post(f"{API}/reports/generate", headers=h).json()
        assert generated["top_category"] == "Large files"

        r = client.get(f"{BASE_URL}/r/{generated['share_code']}")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        assert "Reporty" in r.text
        assert f"{generated['total_reclaimed_gb']} GB" in r.text
        assert "Large files" in r.text

    def test_html_page_unknown_code_is_404_page_not_json(self, client):
        r = client.get(f"{BASE_URL}/r/CR-NOPE00")
        assert r.status_code == 404
        assert "text/html" in r.headers.get("content-type", "")
        assert "not found" in r.text.lower()


class TestAccountDeletionCleansUpReports:
    def test_deleting_account_removes_cleanup_reports(self, client):
        uid, tok = _seed_user_and_session(prefix="CRPT_DEL_")
        h = _auth(tok)
        try:
            generated = client.post(f"{API}/reports/generate", headers=h).json()
            assert _db.cleanup_reports.count_documents({"user_id": uid}) == 1

            r = client.delete(f"{API}/auth/account", headers=h)
            assert r.status_code == 200

            assert _db.cleanup_reports.count_documents({"user_id": uid}) == 0
            # The share code itself no longer resolves — data really is gone.
            assert client.get(f"{API}/reports/{generated['share_code']}").status_code == 404
        finally:
            _db.user_sessions.delete_many({"session_token": tok})
            _db.users.delete_many({"user_id": uid})
            _db.cleanups.delete_many({"device_id": uid})
            _db.cleanup_reports.delete_many({"user_id": uid})
