"""DevicePulse backend — Family Dashboard upgrade tests.

Covers the roadmap ask: "remote management of the whole family's devices,"
built by replacing the old cosmetic model (owner types in a name + device
type, nothing real behind it) with real linked accounts:

  * GET /family/group, POST /family/create, POST /family/join,
    POST /family/leave, and POST /family/remote-clean/{member_user_id} all
    require auth (401)
  * GET /family/group returns null until the user explicitly creates or
    joins one — it deliberately does NOT auto-create on a plain read, since
    that would silently enroll every user in a solo group and then block
    them from joining someone else's family without "leaving" a group they
    never knew they had. POST /family/create makes a unique FAM-XXXXXX
    invite code and makes the caller its sole owner.
  * Joining via invite code adds a real membership; the group is capped at
    FAMILY_MAX_MEMBERS (5) total
  * A user already in a group (even just their own) cannot join another
    without leaving first; an unknown invite code is rejected
  * Each member's snapshot reflects their OWN real per-user data (pulse
    score, streak weeks, forecast days) — not a shared/fake number — proven
    by giving two members different cleanup histories and checking their
    snapshots differ accordingly
  * Only the group owner can trigger POST /family/remote-clean on another
    member; a non-owner gets 403, and it's a no-op against a user outside
    the group (404); it actually records a cleanup on the TARGET's account
    (not the caller's) and improves the target's own forecast
  * Leaving a group works for both a solo owner (tears the group down) and
    a member (group persists for the owner)
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


def _seed_user_and_session(prefix="FAMDASH_"):
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
    _db.family_memberships.delete_many({"user_id": user_id})
    _db.family_groups.delete_many({"owner_id": user_id})


def _insert_cleanup(user_id, hours_ago, reclaimed_mb=100.0):
    completed_at = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    _db.cleanups.insert_one({
        "id": str(uuid.uuid4()),
        "device_id": user_id,
        "categories": ["Junk files"],
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


class TestFamilyRequiresAuth:
    def test_get_group_requires_auth(self, client):
        assert client.get(f"{API}/family/group").status_code == 401

    def test_create_requires_auth(self, client):
        assert client.post(f"{API}/family/create").status_code == 401

    def test_join_requires_auth(self, client):
        assert client.post(f"{API}/family/join", json={"invite_code": "X"}).status_code == 401

    def test_leave_requires_auth(self, client):
        assert client.post(f"{API}/family/leave").status_code == 401

    def test_remote_clean_requires_auth(self, client):
        assert client.post(f"{API}/family/remote-clean/someone").status_code == 401


class TestGroupLifecycle:
    def test_no_group_until_explicitly_created(self, client, seeded_user):
        # A plain read must NOT silently enroll the user in a solo group —
        # that would later block them from joining someone else's family
        # without "leaving" a group they never knew they had.
        r = client.get(f"{API}/family/group", headers=_auth(seeded_user["token"]))
        assert r.status_code == 200
        assert r.json() is None

    def test_create_group_with_unique_code(self, client, seeded_user):
        r = client.post(f"{API}/family/create", headers=_auth(seeded_user["token"]))
        body = r.json()
        assert body["is_owner"] is True
        assert body["invite_code"].startswith("FAM-")
        assert len(body["members"]) == 1

        # GET now reflects the same group, not a new one each time.
        r2 = client.get(f"{API}/family/group", headers=_auth(seeded_user["token"]))
        assert r2.json()["id"] == body["id"]
        assert r2.json()["invite_code"] == body["invite_code"]

    def test_cannot_create_twice(self, client, seeded_user):
        h = _auth(seeded_user["token"])
        client.post(f"{API}/family/create", headers=h)
        r = client.post(f"{API}/family/create", headers=h)
        assert r.status_code == 400

    def test_join_caps_at_max_members(self, client):
        owner_id, owner_tok = _seed_user_and_session(prefix="FAMDASH_CAP_OWN_")
        joiners = [_seed_user_and_session(prefix=f"FAMDASH_CAP_{i}_") for i in range(4)]
        overflow_id, overflow_tok = _seed_user_and_session(prefix="FAMDASH_CAP_OVER_")
        try:
            ho = _auth(owner_tok)
            code = client.post(f"{API}/family/create", headers=ho).json()["invite_code"]
            for uid, tok in joiners:
                r = client.post(f"{API}/family/join", headers=_auth(tok), json={"invite_code": code})
                assert r.status_code == 200, r.text
            # owner + 4 joiners = 5 = FAMILY_MAX_MEMBERS -> the 6th is rejected
            r = client.post(f"{API}/family/join", headers=_auth(overflow_tok), json={"invite_code": code})
            assert r.status_code == 400
        finally:
            _cleanup_user(owner_id, owner_tok)
            for uid, tok in joiners:
                _cleanup_user(uid, tok)
            _cleanup_user(overflow_id, overflow_tok)

    def test_cannot_join_while_already_in_a_group(self, client, seeded_user):
        other_id, other_tok = _seed_user_and_session(prefix="FAMDASH_OTHER_")
        try:
            client.post(f"{API}/family/create", headers=_auth(seeded_user["token"]))
            other_code = client.post(f"{API}/family/create", headers=_auth(other_tok)).json()["invite_code"]
            r = client.post(f"{API}/family/join", headers=_auth(seeded_user["token"]),
                             json={"invite_code": other_code})
            assert r.status_code == 400
        finally:
            _cleanup_user(other_id, other_tok)

    def test_join_unknown_code_is_404(self, client, seeded_user):
        r = client.post(f"{API}/family/join", headers=_auth(seeded_user["token"]),
                         json={"invite_code": "FAM-ZZZZZZ"})
        assert r.status_code == 404


class TestPerMemberLiveSnapshots:
    def test_members_reflect_their_own_real_data_not_a_shared_number(self, client):
        owner_id, owner_tok = _seed_user_and_session(prefix="FAMDASH_SNAP_OWN_")
        member_id, member_tok = _seed_user_and_session(prefix="FAMDASH_SNAP_MEM_")
        try:
            ho, hm = _auth(owner_tok), _auth(member_tok)
            code = client.post(f"{API}/family/create", headers=ho).json()["invite_code"]
            client.post(f"{API}/family/join", headers=hm, json={"invite_code": code})

            # Give the member a very different cleanup history from the owner.
            for _ in range(5):
                _insert_cleanup(member_id, hours_ago=1, reclaimed_mb=50.0)

            group = client.get(f"{API}/family/group", headers=ho).json()
            by_id = {m["user_id"]: m for m in group["members"]}
            assert by_id[owner_id]["streak_weeks"] != by_id[member_id]["streak_weeks"] or \
                   by_id[owner_id]["score"] != by_id[member_id]["score"], \
                "member snapshots look identical/faked instead of derived from real per-user data"
        finally:
            _cleanup_user(owner_id, owner_tok)
            _cleanup_user(member_id, member_tok)


class TestRemoteClean:
    def test_non_owner_member_cannot_remote_clean(self, client):
        owner_id, owner_tok = _seed_user_and_session(prefix="FAMDASH_RC_OWN_")
        member_id, member_tok = _seed_user_and_session(prefix="FAMDASH_RC_MEM_")
        try:
            ho, hm = _auth(owner_tok), _auth(member_tok)
            code = client.post(f"{API}/family/create", headers=ho).json()["invite_code"]
            client.post(f"{API}/family/join", headers=hm, json={"invite_code": code})
            r = client.post(f"{API}/family/remote-clean/{owner_id}", headers=hm)
            assert r.status_code == 403
        finally:
            _cleanup_user(owner_id, owner_tok)
            _cleanup_user(member_id, member_tok)

    def test_remote_clean_rejects_target_outside_group(self, client, seeded_user):
        outsider_id, outsider_tok = _seed_user_and_session(prefix="FAMDASH_RC_OUT_")
        try:
            client.post(f"{API}/family/create", headers=_auth(seeded_user["token"]))
            r = client.post(f"{API}/family/remote-clean/{outsider_id}", headers=_auth(seeded_user["token"]))
            assert r.status_code == 404
        finally:
            _cleanup_user(outsider_id, outsider_tok)

    def test_owner_cannot_remote_clean_self(self, client, seeded_user):
        h = _auth(seeded_user["token"])
        client.post(f"{API}/family/create", headers=h)  # establishes ownership of their own group
        r = client.post(f"{API}/family/remote-clean/{seeded_user['user_id']}", headers=h)
        assert r.status_code == 400

    def test_remote_clean_records_cleanup_on_target_and_improves_their_forecast(self, client):
        owner_id, owner_tok = _seed_user_and_session(prefix="FAMDASH_RC2_OWN_")
        member_id, member_tok = _seed_user_and_session(prefix="FAMDASH_RC2_MEM_")
        try:
            ho, hm = _auth(owner_tok), _auth(member_tok)
            code = client.post(f"{API}/family/create", headers=ho).json()["invite_code"]
            client.post(f"{API}/family/join", headers=hm, json={"invite_code": code})

            # Member has been idle a long time -> a low days_until_full before the fix.
            _insert_cleanup(member_id, hours_ago=900, reclaimed_mb=300.0)
            before = client.get(f"{API}/forecast", headers=hm).json()

            before_count = _db.cleanups.count_documents({"device_id": member_id})
            r = client.post(f"{API}/family/remote-clean/{member_id}", headers=ho)
            assert r.status_code == 200, r.text
            assert r.json()["reclaimed_mb"] > 0
            assert r.json()["member"]["user_id"] == member_id

            after_count = _db.cleanups.count_documents({"device_id": member_id})
            assert after_count == before_count + 1
            doc = _db.cleanups.find_one({"device_id": member_id}, sort=[("completed_at", -1)])
            assert doc["categories"] == ["Remote family cleanup"]

            after = client.get(f"{API}/forecast", headers=hm).json()
            assert after["days_until_full"] > before["days_until_full"]
        finally:
            _cleanup_user(owner_id, owner_tok)
            _cleanup_user(member_id, member_tok)


class TestLeave:
    def test_leave_when_not_in_a_group(self, client, seeded_user):
        r = client.post(f"{API}/family/leave", headers=_auth(seeded_user["token"]))
        assert r.status_code == 400

    def test_solo_owner_leaving_tears_down_group(self, client, seeded_user):
        h = _auth(seeded_user["token"])
        group_id = client.post(f"{API}/family/create", headers=h).json()["id"]
        r = client.post(f"{API}/family/leave", headers=h)
        assert r.status_code == 200 and r.json() == {"left": True}
        assert _db.family_groups.find_one({"id": group_id}) is None

    def test_member_leaving_keeps_group_alive_for_owner(self, client):
        owner_id, owner_tok = _seed_user_and_session(prefix="FAMDASH_LEAVE_OWN_")
        member_id, member_tok = _seed_user_and_session(prefix="FAMDASH_LEAVE_MEM_")
        try:
            ho, hm = _auth(owner_tok), _auth(member_tok)
            code = client.post(f"{API}/family/create", headers=ho).json()["invite_code"]
            client.post(f"{API}/family/join", headers=hm, json={"invite_code": code})

            r = client.post(f"{API}/family/leave", headers=hm)
            assert r.status_code == 200

            group = client.get(f"{API}/family/group", headers=ho).json()
            assert group["is_owner"] is True
            assert len(group["members"]) == 1
            assert group["members"][0]["user_id"] == owner_id
        finally:
            _cleanup_user(owner_id, owner_tok)
            _cleanup_user(member_id, member_tok)
