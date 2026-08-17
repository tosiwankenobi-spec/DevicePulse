"""DevicePulse backend API tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://verolane-pulse.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---- Device Health ----
class TestHealth:
    def test_root(self, client):
        r = client.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("app") == "DevicePulse"

    def test_device_health(self, client):
        r = client.get(f"{API}/device/health")
        assert r.status_code == 200
        data = r.json()
        for k in ["score", "status", "storage_used_gb", "storage_total_gb",
                  "ram_used_pct", "battery_pct", "battery_health_pct",
                  "security_status", "issues_found"]:
            assert k in data
        assert 0 <= data["score"] <= 100


# ---- Storage ----
class TestStorage:
    def test_storage(self, client):
        r = client.get(f"{API}/device/storage")
        assert r.status_code == 200
        d = r.json()
        assert "breakdown" in d and isinstance(d["breakdown"], list)
        assert len(d["breakdown"]) > 0
        assert d["total_gb"] > 0
        for b in d["breakdown"]:
            assert "category" in b and "size_gb" in b and "color" in b and "pct" in b


# ---- Duplicates ----
class TestDuplicates:
    def test_duplicates(self, client):
        r = client.get(f"{API}/device/duplicates")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        for g in data:
            assert "id" in g and "count" in g and "size_mb" in g and "thumbnail_url" in g
            assert g["thumbnail_url"].startswith("http")


# ---- Large Files ----
class TestLargeFiles:
    def test_large_files(self, client):
        r = client.get(f"{API}/device/large-files")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        for f in data:
            assert set(["id", "name", "size_mb", "type", "modified_at"]).issubset(f.keys())


# ---- Battery ----
class TestBattery:
    def test_battery(self, client):
        r = client.get(f"{API}/device/battery")
        assert r.status_code == 200
        d = r.json()
        assert "drain_apps" in d and isinstance(d["drain_apps"], list)
        assert len(d["drain_apps"]) >= 1
        assert 0 <= d["level"] <= 100


# ---- Security ----
class TestSecurity:
    def test_security(self, client):
        r = client.get(f"{API}/device/security")
        assert r.status_code == 200
        d = r.json()
        assert "threats" in d and isinstance(d["threats"], list)
        assert "apps_scanned" in d and d["apps_scanned"] > 0


# ---- Scan ----
class TestScan:
    def test_scan(self, client):
        r = client.post(f"{API}/device/scan")
        assert r.status_code == 200
        d = r.json()
        for k in ["id", "junk_mb", "duplicates_mb", "large_files_mb",
                  "cache_mb", "total_reclaimable_mb", "health_before", "health_after"]:
            assert k in d
        total = d["junk_mb"] + d["duplicates_mb"] + d["large_files_mb"] + d["cache_mb"]
        assert abs(total - d["total_reclaimable_mb"]) < 1.0
        assert d["health_after"] >= d["health_before"]


# ---- Clean ----
class TestClean:
    def test_clean(self, client):
        payload = {"categories": ["junk", "cache", "duplicates"], "reclaimable_mb": 1200.5}
        r = client.post(f"{API}/device/clean", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["reclaimed_mb"] == 1200.5
        assert set(d["categories"]) == set(payload["categories"])
        assert "health_before" in d and "health_after" in d
        assert d["health_after"] >= d["health_before"]


# ---- AI Recommendations ----
class TestAIRecommendations:
    def test_recommendations(self, client):
        payload = {
            "health_score": 68,
            "storage_used_pct": 73.6,
            "battery_health_pct": 87,
            "duplicates_mb": 420,
            "junk_mb": 890,
            "threats": 1,
            "platform": "android",
        }
        r = client.post(f"{API}/ai/recommendations", json=payload, timeout=45)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 4
        for rec in data:
            assert "title" in rec and "description" in rec and "impact" in rec
            assert rec["impact"] in ["low", "medium", "high"]
