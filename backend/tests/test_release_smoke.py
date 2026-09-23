"""In-process release smoke test that does not require a local Mongo daemon."""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

os.environ.setdefault("MONGO_URL", "mongodb://unused")
os.environ.setdefault("DB_NAME", "devicepulse_release_test")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend import server  # noqa: E402


class _FakePushResponse:
    status_code = 201

    def raise_for_status(self):
        return None


class _FakePushClient:
    async def post(self, *_args, **_kwargs):
        return _FakePushResponse()

    async def aclose(self):
        return None


def _seed_user():
    async def seed():
        await server.db.users.insert_one(
            {
                "user_id": "release-user",
                "email": "release@example.com",
                "name": "Release Test",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        await server.db.user_sessions.insert_one(
            {
                "session_token": "release-token",
                "sid": "release-session",
                "user_id": "release-user",
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            }
        )

    asyncio.run(seed())


def test_release_critical_flows():
    mock_mongo = AsyncMongoMockClient()
    server.client = mock_mongo
    server.db = mock_mongo["devicepulse_release_test"]
    server.ENVIRONMENT = "development"
    server.EMERGENT_LLM_KEY = None
    server.REVENUECAT_SECRET_API_KEY = None
    server._push_client = _FakePushClient()
    _seed_user()

    auth = {"Authorization": "Bearer release-token"}
    with TestClient(server.app) as client:
        assert client.get("/api/").status_code == 200
        assert client.get("/api/healthz").status_code == 200
        server.ENVIRONMENT = "production"
        assert (
            client.post(
                "/api/entitlements/sync", headers=auth, json={"is_pro": True}
            ).status_code
            == 503
        )
        server.ENVIRONMENT = "development"
        assert (
            client.post(
                "/api/entitlements/sync", headers=auth, json={"is_pro": True}
            ).status_code
            == 200
        )

        for method, path in (
            ("get", "/api/device/health"),
            ("get", "/api/device/storage"),
            ("post", "/api/device/scan"),
            ("get", "/api/auth/me"),
            ("get", "/api/auth/sessions"),
            ("get", "/api/history"),
            ("get", "/api/history/summary"),
            ("get", "/api/referral"),
            ("post", "/api/referral/invite"),
            ("get", "/api/reminders"),
            ("get", "/api/streak"),
            ("get", "/api/device/cache-breakdown"),
            ("get", "/api/device/health-trend"),
            ("get", "/api/forecast"),
            ("post", "/api/forecast/quick-fix"),
            ("get", "/api/pulse/daily"),
            ("get", "/api/widget/summary"),
            ("get", "/api/nudges/active"),
            ("get", "/api/family/group"),
            ("get", "/api/reports/mine"),
            ("get", "/api/entitlements/me"),
            ("get", "/api/device/duplicates"),
            ("post", "/api/device/duplicates/scan"),
            ("get", "/api/device/security"),
            ("post", "/api/device/security/scan"),
            ("get", "/api/device/battery"),
            ("post", "/api/device/battery/optimize"),
            ("get", "/api/device/large-files"),
            ("post", "/api/device/large-files/scan"),
            ("get", "/api/device/memory"),
            ("post", "/api/device/memory/boost"),
            ("get", "/api/coach/daily"),
            ("get", "/api/coach/history"),
            ("get", "/api/coach/insights"),
        ):
            response = client.request(method, path, headers=auth)
            assert (
                response.status_code == 200
            ), f"{method.upper()} {path}: {response.text}"

        assert (
            client.put(
                "/api/reminders",
                headers=auth,
                json={
                    "device_id": "self",
                    "low_storage": True,
                    "weekly_cleanup": True,
                    "after_downloads": True,
                    "battery_alerts": True,
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/device/clean",
                headers=auth,
                json={"categories": ["junk", "cache"], "reclaimable_mb": 128},
            ).status_code
            == 200
        )
        assert client.post("/api/family/create", headers=auth).status_code == 200
        assert client.post("/api/family/leave", headers=auth).status_code == 200

        report = client.post("/api/reports/generate", headers=auth)
        assert report.status_code == 200
        share_code = report.json()["share_code"]
        assert client.get(f"/api/reports/{share_code}").status_code == 200
        assert client.get(f"/r/{share_code}").status_code == 200

        assert (
            client.put(
                "/api/autoclean/schedule",
                headers=auth,
                json={
                    "enabled": True,
                    "frequency": "daily",
                    "categories": ["Junk files"],
                },
            ).status_code
            == 200
        )
        assert client.get("/api/autoclean/schedule", headers=auth).status_code == 200
        assert client.post("/api/autoclean/run-if-due", headers=auth).status_code == 200

        recs = client.post(
            "/api/ai/recommendations",
            json={
                "health_score": 82,
                "storage_used_pct": 45,
                "battery_health_pct": 73,
                "duplicates_mb": 480,
                "junk_mb": 890,
                "threats": 0,
                "platform": "android",
            },
        )
        assert recs.status_code == 200 and len(recs.json()) == 4
        assert (
            client.post(
                "/api/coach/chat",
                headers=auth,
                json={"message": "What should I clean first?"},
            ).status_code
            == 200
        )

        assert (
            client.post(
                "/api/register-push",
                headers=auth,
                json={
                    "user_id": "release-user",
                    "platform": "android",
                    "device_token": "test-token",
                },
            ).status_code
            == 201
        )
        assert client.post("/api/push/test", headers=auth).status_code == 200
        assert (
            client.post("/api/push/cleanup-reminder", headers=auth).status_code == 200
        )
