"""DevicePulse backend — Security (real account signals) tests.

Covers the roadmap follow-up: "Deepen security into something real." The
pre-existing GET /device/security was unauthenticated, took no user at all,
and always returned the exact same single hardcoded finding with status
hardcoded to "safe" — nothing was per-user, nothing was actionable, and the
status text didn't even agree with the one threat being shown.

Scoped explicitly via AskUserQuestion to real account signals only — no
external breach-check service, to avoid sending user emails to a third party:

  * Every OTHER active session (db.user_sessions — real, already-existing
    data) is now a real, actionable finding, computed LIVE on every call
    (never persisted, so it's always exactly current) with a one-tap fix:
    revoking it via the pre-existing POST /auth/sessions/{sid}/revoke makes
    the finding disappear on the next read, since it's derived, not stored.
  * 2-3 concurrent sessions is "low" severity (informational); 4+ is
    "medium" (worth a closer look).
  * Device-level findings (permissions, backups, network, app hygiene) stay
    simulated — same honest framing as the rest of this app's device layer —
    but are now persisted per user (lazily generated once, like Duplicate
    Photo AI's groups) and individually dismissible via
    POST /device/security/findings/{id}/resolve, instead of one fact
    fabricated fresh on every call.
  * POST /device/security/scan can surface a new device-level finding,
    simulating discovering something new since the last scan.
  * status is "at_risk" if ANY finding (session or device) is medium/high
    severity, "safe" otherwise — computed for real, not hardcoded.

Covers:
  * All three routes require auth (401)
  * A lone active session produces zero findings and status "safe"
  * A second concurrent session produces exactly one real session finding,
    severity "low", with the correct session_sid — and it's gone the moment
    that session is revoked via the existing /auth/sessions/{sid}/revoke
  * 4+ concurrent sessions bumps severity to "medium" and status to
    "at_risk"
  * GET is stable/persisted for device findings (not reshuffled every call),
    scan_state (apps_scanned/permissions_reviewed) persists too
  * scan can add a new device finding without duplicating an already-open one
  * resolve: unknown/already-resolved id 404s, resolving actually removes it
    from the list, resolving a device finding can flip status back to "safe"
  * IDOR: a user cannot resolve another user's device finding
  * Deleting the account removes security_findings and security_scan_state
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


def _seed_user_and_session(prefix="SEC_"):
    user_id = f"{prefix}user_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}{uuid.uuid4().hex[:6]}@example.com"
    token = f"{prefix}tok_{uuid.uuid4().hex}"
    sid = uuid.uuid4().hex[:12]
    _db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": "Security Tester",
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


def _add_session(user_id, prefix="SEC_"):
    token = f"{prefix}tok_{uuid.uuid4().hex}"
    sid = uuid.uuid4().hex[:12]
    _db.user_sessions.insert_one({
        "session_token": token,
        "sid": sid,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    })
    return token, sid


def _cleanup_user(user_id, token):
    _db.user_sessions.delete_many({"user_id": user_id})
    _db.users.delete_many({"user_id": user_id})
    _db.security_findings.delete_many({"user_id": user_id})
    _db.security_scan_state.delete_many({"user_id": user_id})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture()
def solo_user():
    uid, tok = _seed_user_and_session()
    yield {"user_id": uid, "token": tok}
    _cleanup_user(uid, tok)


class TestRequiresAuth:
    def test_get_requires_auth(self, client):
        assert client.get(f"{API}/device/security").status_code == 401

    def test_scan_requires_auth(self, client):
        assert client.post(f"{API}/device/security/scan").status_code == 401

    def test_resolve_requires_auth(self, client):
        assert client.post(f"{API}/device/security/findings/x/resolve").status_code == 401


class TestRealSessionFindings:
    def test_lone_session_has_no_session_findings(self, client, solo_user):
        r = client.get(f"{API}/device/security", headers=_auth(solo_user["token"]))
        assert r.status_code == 200
        body = r.json()
        session_findings = [f for f in body["findings"] if f["source"] == "session"]
        assert session_findings == []

    def test_second_session_produces_one_low_severity_finding(self, client, solo_user):
        _, other_sid = _add_session(solo_user["user_id"])
        r = client.get(f"{API}/device/security", headers=_auth(solo_user["token"]))
        body = r.json()
        session_findings = [f for f in body["findings"] if f["source"] == "session"]
        assert len(session_findings) == 1
        assert session_findings[0]["severity"] == "low"
        assert session_findings[0]["session_sid"] == other_sid
        assert session_findings[0]["action"] == "revoke_session"

    def test_revoking_the_session_removes_its_finding(self, client, solo_user):
        h = _auth(solo_user["token"])
        _, other_sid = _add_session(solo_user["user_id"])
        assert any(f["source"] == "session" for f in client.get(f"{API}/device/security", headers=h).json()["findings"])

        rv = client.post(f"{API}/auth/sessions/{other_sid}/revoke", headers=h)
        assert rv.status_code == 200 and rv.json() == {"revoked": True}

        after = client.get(f"{API}/device/security", headers=h).json()
        assert not any(f["source"] == "session" for f in after["findings"])

    def test_four_or_more_concurrent_sessions_is_medium_and_at_risk(self, client, solo_user):
        for _ in range(3):
            _add_session(solo_user["user_id"])
        body = client.get(f"{API}/device/security", headers=_auth(solo_user["token"])).json()
        session_findings = [f for f in body["findings"] if f["source"] == "session"]
        assert len(session_findings) == 3
        assert all(f["severity"] == "medium" for f in session_findings)
        assert body["status"] == "at_risk"


class TestDeviceFindingsPersistence:
    def test_repeated_get_is_stable(self, client, solo_user):
        h = _auth(solo_user["token"])
        first = client.get(f"{API}/device/security", headers=h).json()
        second = client.get(f"{API}/device/security", headers=h).json()
        assert first["apps_scanned"] == second["apps_scanned"]
        assert first["permissions_reviewed"] == second["permissions_reviewed"]
        first_device_ids = {f["id"] for f in first["findings"] if f["source"] == "device"}
        second_device_ids = {f["id"] for f in second["findings"] if f["source"] == "device"}
        assert first_device_ids == second_device_ids

    def test_two_users_get_independent_scan_state(self, client, solo_user):
        other_uid, other_tok = _seed_user_and_session(prefix="SEC_OTHER_")
        try:
            client.get(f"{API}/device/security", headers=_auth(solo_user["token"]))
            client.get(f"{API}/device/security", headers=_auth(other_tok))
            a_state = _db.security_scan_state.find_one({"user_id": solo_user["user_id"]})
            b_state = _db.security_scan_state.find_one({"user_id": other_uid})
            assert a_state is not None and b_state is not None
        finally:
            _cleanup_user(other_uid, other_tok)


class TestScan:
    def test_scan_can_add_a_new_device_finding_without_duplicating(self, client, solo_user):
        h = _auth(solo_user["token"])
        client.get(f"{API}/device/security", headers=h)  # ensure scan_state exists

        seen_keys = set()
        for _ in range(15):
            r = client.post(f"{API}/device/security/scan", headers=h)
            assert r.status_code == 200
            body = r.json()
            device = [f for f in body["scan"]["findings"] if f["source"] == "device"]
            keys = [(f["title"], f["category"]) for f in device]
            assert len(keys) == len(set(keys)), "no duplicate open findings of the same kind"
            seen_keys.update(keys)
        # Over enough scans, the pool of possible findings should surface at least once.
        assert len(seen_keys) >= 1


class TestResolve:
    def test_unknown_id_404s(self, client, solo_user):
        r = client.post(f"{API}/device/security/findings/not-a-real-id/resolve", headers=_auth(solo_user["token"]))
        assert r.status_code == 404

    def test_resolve_removes_finding_and_double_resolve_404s(self, client, solo_user):
        h = _auth(solo_user["token"])
        # Force at least one device finding into existence directly, deterministically.
        _db.security_findings.insert_one({
            "id": "forced-1", "user_id": solo_user["user_id"], "key": "outdated_app",
            "category": "app", "severity": "low", "title": "Outdated app version detected",
            "description": "test", "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(), "resolved_at": None,
        })
        before = client.get(f"{API}/device/security", headers=h).json()
        assert any(f["id"] == "forced-1" for f in before["findings"])

        r = client.post(f"{API}/device/security/findings/forced-1/resolve", headers=h)
        assert r.status_code == 200 and r.json() == {"resolved": True}

        after = client.get(f"{API}/device/security", headers=h).json()
        assert not any(f["id"] == "forced-1" for f in after["findings"])

        r2 = client.post(f"{API}/device/security/findings/forced-1/resolve", headers=h)
        assert r2.status_code == 404

    def test_resolving_last_medium_finding_flips_status_to_safe(self, client, solo_user):
        h = _auth(solo_user["token"])
        client.get(f"{API}/device/security", headers=h)  # trigger lazy init first
        # Clear whatever the lazy init randomly generated, so only the finding
        # we insert below determines the status for this test.
        _db.security_findings.delete_many({"user_id": solo_user["user_id"]})
        _db.security_findings.insert_one({
            "id": "forced-medium", "user_id": solo_user["user_id"], "key": "camera_background",
            "category": "permission", "severity": "medium", "title": "Camera access outside app use",
            "description": "test", "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(), "resolved_at": None,
        })
        before = client.get(f"{API}/device/security", headers=h).json()
        assert before["status"] == "at_risk"

        client.post(f"{API}/device/security/findings/forced-medium/resolve", headers=h)
        after = client.get(f"{API}/device/security", headers=h).json()
        assert after["status"] == "safe"

    def test_idor_cannot_resolve_another_users_finding(self, client, solo_user):
        other_uid, other_tok = _seed_user_and_session(prefix="SEC_OTHER_")
        try:
            _db.security_findings.insert_one({
                "id": "victim-finding", "user_id": solo_user["user_id"], "key": "outdated_app",
                "category": "app", "severity": "low", "title": "Outdated app version detected",
                "description": "test", "status": "open",
                "created_at": datetime.now(timezone.utc).isoformat(), "resolved_at": None,
            })
            r = client.post(f"{API}/device/security/findings/victim-finding/resolve", headers=_auth(other_tok))
            assert r.status_code == 404

            still_there = client.get(f"{API}/device/security", headers=_auth(solo_user["token"])).json()
            assert any(f["id"] == "victim-finding" for f in still_there["findings"])
        finally:
            _cleanup_user(other_uid, other_tok)


class TestAccountDeletionCleansUp:
    def test_deleting_account_removes_security_state(self, client):
        uid, tok = _seed_user_and_session(prefix="SEC_DEL_")
        h = _auth(tok)
        try:
            client.get(f"{API}/device/security", headers=h)
            assert _db.security_scan_state.count_documents({"user_id": uid}) == 1

            r = client.delete(f"{API}/auth/account", headers=h)
            assert r.status_code == 200

            assert _db.security_scan_state.count_documents({"user_id": uid}) == 0
            assert _db.security_findings.count_documents({"user_id": uid}) == 0
        finally:
            _db.user_sessions.delete_many({"user_id": uid})
            _db.users.delete_many({"user_id": uid})
            _db.security_findings.delete_many({"user_id": uid})
            _db.security_scan_state.delete_many({"user_id": uid})
