"""DevicePulse backend — Large File Cleanup tests.

Covers a post-roadmap gap found by inspection: the old GET /device/large-files
was unauthenticated and returned the exact same fixed eight-file hardcoded
array on every call — not per-user, not persisted. Worse, the "Delete X GB"
button on the large-files screen was 100% cosmetic
(onPress={() => router.back()}) — it never called the backend at all, so
nothing was ever actually deleted (the same shape of bug Duplicate Photo AI
fixed for duplicate groups).

Design note: unlike Duplicate Photo AI and the Battery Optimizer, there is no
Pro-perk promise anywhere in paywall.tsx tied to large files, so this feature
has no Pro gate and no free-tier cap — deletion is free and unlimited for
everyone, same as it always silently (uselessly) appeared to be.

Covers:
  * GET /device/large-files, POST /device/large-files/scan, and
    POST /device/large-files/delete all require auth
  * GET lazily generates a per-user file list once, persists it (stable
    across repeated GETs), independently per user
  * POST /device/large-files/scan appends new files without losing existing
    pending ones
  * POST /device/large-files/delete: unknown/already-deleted id 404s, empty
    file_ids 400s, a successful delete permanently removes the file(s) from
    the pending list and records a real cleanup (categories=["Large files"],
    reclaimed_mb matching the deleted files' sizes)
  * IDOR: cannot delete another user's file
  * Deleting the account removes large_files too
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


def _seed_user_and_session(prefix="LFILE_"):
    user_id = f"{prefix}user_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}{uuid.uuid4().hex[:6]}@example.com"
    token = f"{prefix}tok_{uuid.uuid4().hex}"
    sid = uuid.uuid4().hex[:12]
    _db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": "Large File Tester",
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
    _db.large_files.delete_many({"user_id": user_id})
    _db.cleanups.delete_many({"device_id": user_id})


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
    uid, tok = _seed_user_and_session(prefix="LFILE_OTHER_")
    yield {"user_id": uid, "token": tok}
    _cleanup_user(uid, tok)


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


class TestRequiresAuth:
    def test_get_requires_auth(self, client):
        assert client.get(f"{API}/device/large-files").status_code == 401

    def test_scan_requires_auth(self, client):
        assert client.post(f"{API}/device/large-files/scan").status_code == 401

    def test_delete_requires_auth(self, client):
        r = client.post(f"{API}/device/large-files/delete", json={"file_ids": ["x"]})
        assert r.status_code == 401


class TestPersistedGeneration:
    def test_first_get_generates_and_persists(self, client, user):
        r = client.get(f"{API}/device/large-files", headers=_auth(user["token"]))
        assert r.status_code == 200
        files = r.json()
        assert 5 <= len(files) <= 8
        for f in files:
            assert f["size_mb"] > 0
            assert f["type"] in ("video", "audio", "doc", "photo")
            assert f["name"]
            assert f["modified_at"]
        doc_count = _db.large_files.count_documents({"user_id": user["user_id"]})
        assert doc_count == len(files)

    def test_repeated_get_is_stable(self, client, user):
        h = _auth(user["token"])
        first = client.get(f"{API}/device/large-files", headers=h).json()
        second = client.get(f"{API}/device/large-files", headers=h).json()
        assert {f["id"] for f in first} == {f["id"] for f in second}

    def test_two_users_get_independent_files(self, client, user, other_user):
        client.get(f"{API}/device/large-files", headers=_auth(user["token"]))
        client.get(f"{API}/device/large-files", headers=_auth(other_user["token"]))
        ids_a = {d["id"] for d in _db.large_files.find({"user_id": user["user_id"]})}
        ids_b = {d["id"] for d in _db.large_files.find({"user_id": other_user["user_id"]})}
        assert ids_a.isdisjoint(ids_b)

    def test_sorted_by_size_descending(self, client, user):
        files = client.get(f"{API}/device/large-files", headers=_auth(user["token"])).json()
        sizes = [f["size_mb"] for f in files]
        assert sizes == sorted(sizes, reverse=True)


class TestScan:
    def test_scan_appends_without_losing_existing(self, client, user):
        h = _auth(user["token"])
        before = client.get(f"{API}/device/large-files", headers=h).json()
        before_ids = {f["id"] for f in before}

        r = client.post(f"{API}/device/large-files/scan", headers=h)
        assert r.status_code == 200
        result = r.json()
        assert 1 <= result["new_files_found"] <= 2

        after_ids = {f["id"] for f in result["files"]}
        assert before_ids.issubset(after_ids)
        assert len(after_ids) == len(before_ids) + result["new_files_found"]


class TestDelete:
    def test_unknown_id_404s(self, client, user):
        client.get(f"{API}/device/large-files", headers=_auth(user["token"]))
        r = client.post(
            f"{API}/device/large-files/delete",
            headers=_auth(user["token"]),
            json={"file_ids": ["does-not-exist"]},
        )
        assert r.status_code == 404

    def test_empty_file_ids_400s(self, client, user):
        client.get(f"{API}/device/large-files", headers=_auth(user["token"]))
        r = client.post(
            f"{API}/device/large-files/delete",
            headers=_auth(user["token"]),
            json={"file_ids": []},
        )
        assert r.status_code == 400

    def test_delete_permanently_removes_and_records_cleanup(self, client, user):
        h = _auth(user["token"])
        files = client.get(f"{API}/device/large-files", headers=h).json()
        target = files[0]

        before_cleanups = _db.cleanups.count_documents({"device_id": user["user_id"]})
        r = client.post(f"{API}/device/large-files/delete", headers=h, json={"file_ids": [target["id"]]})
        assert r.status_code == 200
        result = r.json()
        assert result["deleted_count"] == 1
        assert abs(result["freed_mb"] - target["size_mb"]) < 0.01
        assert all(f["id"] != target["id"] for f in result["files"])

        after_cleanups = _db.cleanups.count_documents({"device_id": user["user_id"]})
        assert after_cleanups == before_cleanups + 1
        cleanup = _db.cleanups.find_one({"device_id": user["user_id"]}, sort=[("completed_at", -1)])
        assert cleanup["categories"] == ["Large files"]
        assert abs(cleanup["reclaimed_mb"] - target["size_mb"]) < 0.01

        # File no longer appears in a subsequent GET, and re-deleting 404s.
        remaining = client.get(f"{API}/device/large-files", headers=h).json()
        assert all(f["id"] != target["id"] for f in remaining)
        r2 = client.post(f"{API}/device/large-files/delete", headers=h, json={"file_ids": [target["id"]]})
        assert r2.status_code == 404

    def test_delete_multiple_sums_freed_mb(self, client, user):
        h = _auth(user["token"])
        files = client.get(f"{API}/device/large-files", headers=h).json()
        targets = files[:2]
        expected = round(sum(f["size_mb"] for f in targets), 1)
        r = client.post(f"{API}/device/large-files/delete", headers=h, json={"file_ids": [f["id"] for f in targets]})
        assert r.status_code == 200
        assert r.json()["deleted_count"] == 2
        assert abs(r.json()["freed_mb"] - expected) < 0.05

    def test_idor_cannot_delete_another_users_file(self, client, user, other_user):
        client.get(f"{API}/device/large-files", headers=_auth(user["token"]))
        their_files = client.get(f"{API}/device/large-files", headers=_auth(other_user["token"])).json()
        target = their_files[0]

        r = client.post(
            f"{API}/device/large-files/delete",
            headers=_auth(user["token"]),
            json={"file_ids": [target["id"]]},
        )
        assert r.status_code == 404
        # Confirm the other user's file is untouched.
        still_there = _db.large_files.find_one({"id": target["id"], "user_id": other_user["user_id"]})
        assert still_there is not None
        assert still_there["status"] == "pending"


class TestAccountDeletionCleansUp:
    def test_delete_account_removes_large_files(self, client, user):
        h = _auth(user["token"])
        client.get(f"{API}/device/large-files", headers=h)
        assert _db.large_files.count_documents({"user_id": user["user_id"]}) > 0

        r = client.delete(f"{API}/auth/account", headers=h)
        assert r.status_code == 200
        assert _db.large_files.count_documents({"user_id": user["user_id"]}) == 0
