from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
import uuid
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

from emergentintegrations.llm.chat import LlmChat, UserMessage


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

app = FastAPI()
api_router = APIRouter(prefix="/api")


# ==================== Models ====================
class DeviceHealth(BaseModel):
    score: int
    status: str
    storage_used_gb: float
    storage_total_gb: float
    ram_used_pct: int
    battery_pct: int
    battery_health_pct: int
    security_status: str
    issues_found: int

class StorageBreakdown(BaseModel):
    category: str
    size_gb: float
    color: str
    pct: float

class StorageAnalysis(BaseModel):
    total_gb: float
    used_gb: float
    free_gb: float
    breakdown: List[StorageBreakdown]

class DuplicateGroup(BaseModel):
    id: str
    count: int
    size_mb: float
    thumbnail_url: str
    taken_at: str

class LargeFile(BaseModel):
    id: str
    name: str
    size_mb: float
    type: str  # video, photo, doc, app
    modified_at: str

class BatteryInsight(BaseModel):
    level: int
    health_pct: int
    cycle_count: int
    temperature_c: float
    charging: bool
    time_to_empty_hours: float
    drain_apps: List[dict]

class SecurityThreat(BaseModel):
    id: str
    severity: str  # low, medium, high
    title: str
    description: str
    category: str  # malware, permission, network, privacy

class SecurityScan(BaseModel):
    status: str  # safe, at_risk
    last_scan_iso: str
    threats: List[SecurityThreat]
    apps_scanned: int
    permissions_reviewed: int

class ScanResult(BaseModel):
    id: str
    started_at: str
    completed_at: str
    junk_mb: float
    duplicates_mb: float
    large_files_mb: float
    cache_mb: float
    total_reclaimable_mb: float
    health_before: int
    health_after: int

class RecommendationRequest(BaseModel):
    health_score: int
    storage_used_pct: float
    battery_health_pct: int
    duplicates_mb: float
    junk_mb: float
    threats: int
    platform: Optional[str] = "android"

class Recommendation(BaseModel):
    title: str
    description: str
    impact: str  # low, medium, high

class CleanupRequest(BaseModel):
    categories: List[str]
    reclaimable_mb: float


# ==================== Helpers ====================
def _seed_health() -> DeviceHealth:
    return DeviceHealth(
        score=68,
        status="Needs Attention",
        storage_used_gb=94.2,
        storage_total_gb=128.0,
        ram_used_pct=72,
        battery_pct=54,
        battery_health_pct=87,
        security_status="1 minor issue",
        issues_found=7,
    )


# ==================== Routes ====================
@api_router.get("/")
async def root():
    return {"app": "DevicePulse", "version": "1.0.0"}

@api_router.get("/device/health", response_model=DeviceHealth)
async def get_device_health():
    return _seed_health()

@api_router.get("/device/storage", response_model=StorageAnalysis)
async def get_storage_analysis():
    breakdown = [
        StorageBreakdown(category="Photos", size_gb=32.4, color="#10B981", pct=25.3),
        StorageBreakdown(category="Videos", size_gb=24.1, color="#0EA5E9", pct=18.8),
        StorageBreakdown(category="Apps", size_gb=18.6, color="#8B5CF6", pct=14.5),
        StorageBreakdown(category="Cache", size_gb=8.9, color="#F59E0B", pct=6.9),
        StorageBreakdown(category="Documents", size_gb=6.2, color="#EC4899", pct=4.8),
        StorageBreakdown(category="Other", size_gb=4.0, color="#64748B", pct=3.1),
    ]
    return StorageAnalysis(
        total_gb=128.0,
        used_gb=sum(b.size_gb for b in breakdown),
        free_gb=128.0 - sum(b.size_gb for b in breakdown),
        breakdown=breakdown,
    )

@api_router.get("/device/duplicates", response_model=List[DuplicateGroup])
async def get_duplicates():
    thumbs = [
        "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=400",
        "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=400",
        "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=400",
        "https://images.unsplash.com/photo-1519681393784-d120267933ba?w=400",
        "https://images.unsplash.com/photo-1501785888041-af3ef285b470?w=400",
        "https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=400",
    ]
    groups = []
    for i, url in enumerate(thumbs):
        groups.append(DuplicateGroup(
            id=str(uuid.uuid4()),
            count=random.randint(2, 5),
            size_mb=round(random.uniform(4.5, 42.0), 1),
            thumbnail_url=url,
            taken_at=f"2025-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        ))
    return groups

@api_router.get("/device/large-files", response_model=List[LargeFile])
async def get_large_files():
    files = [
        ("Vacation_2024_Highlights.mp4", 1240.5, "video"),
        ("Podcast_Episode_47.mp3", 84.2, "audio"),
        ("Project_Backup.zip", 512.0, "doc"),
        ("Screen_Recording_Aug.mov", 342.7, "video"),
        ("Design_Assets_Master.psd", 218.4, "doc"),
        ("Old_Games_Archive.zip", 892.1, "doc"),
        ("Family_Wedding.mp4", 1580.3, "video"),
        ("Tutorial_Series.mp4", 620.9, "video"),
    ]
    now = datetime.now(timezone.utc).isoformat()
    return [
        LargeFile(id=str(uuid.uuid4()), name=n, size_mb=s, type=t, modified_at=now)
        for n, s, t in files
    ]

@api_router.get("/device/battery", response_model=BatteryInsight)
async def get_battery():
    return BatteryInsight(
        level=54,
        health_pct=87,
        cycle_count=423,
        temperature_c=32.4,
        charging=False,
        time_to_empty_hours=6.4,
        drain_apps=[
            {"name": "Instagram", "pct": 24, "icon": "📷"},
            {"name": "YouTube", "pct": 18, "icon": "▶️"},
            {"name": "Chrome", "pct": 12, "icon": "🌐"},
            {"name": "Spotify", "pct": 9, "icon": "🎵"},
            {"name": "WhatsApp", "pct": 6, "icon": "💬"},
        ],
    )

@api_router.get("/device/security", response_model=SecurityScan)
async def get_security():
    threats = [
        SecurityThreat(
            id=str(uuid.uuid4()),
            severity="low",
            title="Excessive permissions detected",
            description="2 apps have access to your location while running in background.",
            category="permission",
        ),
    ]
    return SecurityScan(
        status="safe",
        last_scan_iso=datetime.now(timezone.utc).isoformat(),
        threats=threats,
        apps_scanned=147,
        permissions_reviewed=328,
    )

@api_router.post("/device/scan", response_model=ScanResult)
async def run_scan():
    junk = round(random.uniform(680, 1200), 1)
    dups = round(random.uniform(320, 720), 1)
    large = round(random.uniform(800, 2200), 1)
    cache = round(random.uniform(150, 480), 1)
    total = junk + dups + large + cache
    result = ScanResult(
        id=str(uuid.uuid4()),
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        junk_mb=junk,
        duplicates_mb=dups,
        large_files_mb=large,
        cache_mb=cache,
        total_reclaimable_mb=round(total, 1),
        health_before=68,
        health_after=min(97, 68 + int(total / 120)),
    )
    await db.scans.insert_one(result.dict())
    return result

@api_router.post("/device/clean")
async def run_clean(req: CleanupRequest):
    doc = {
        "id": str(uuid.uuid4()),
        "categories": req.categories,
        "reclaimed_mb": req.reclaimable_mb,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.cleanups.insert_one(doc.copy())
    return {
        "reclaimed_mb": req.reclaimable_mb,
        "categories": req.categories,
        "health_after": min(97, 68 + int(req.reclaimable_mb / 120)),
        "health_before": 68,
        "completed_at": doc["completed_at"],
    }

@api_router.post("/ai/recommendations", response_model=List[Recommendation])
async def get_ai_recommendations(req: RecommendationRequest):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "LLM key not configured")

    system_message = (
        "You are DevicePulse AI, a professional device optimization assistant. "
        "Generate exactly 4 concise, actionable recommendations to improve device health. "
        "Return ONLY a valid JSON array (no markdown, no code fences) with objects: "
        '{"title": "short title (max 6 words)", "description": "1-2 sentence reason and action", "impact": "low|medium|high"}. '
        "Focus on real, practical device optimization. Be reassuring and clear."
    )

    prompt = (
        f"Device stats:\n"
        f"- Health score: {req.health_score}/100\n"
        f"- Storage used: {req.storage_used_pct:.0f}%\n"
        f"- Battery health: {req.battery_health_pct}%\n"
        f"- Duplicate files: {req.duplicates_mb:.0f} MB\n"
        f"- Junk/cache: {req.junk_mb:.0f} MB\n"
        f"- Security threats: {req.threats}\n"
        f"- Platform: {req.platform}\n\n"
        f"Generate 4 recommendations as a JSON array."
    )

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"rec-{uuid.uuid4()}",
            system_message=system_message,
        ).with_model("anthropic", "claude-sonnet-5")

        response = await chat.send_message(UserMessage(text=prompt))

        import json, re
        text = response if isinstance(response, str) else str(response)
        # strip code fences if any
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
        # extract JSON array
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            data = json.loads(match.group(0))
            return [Recommendation(**r) for r in data[:4]]
        raise ValueError("No JSON array found")
    except Exception as e:
        logging.exception("AI recommendation failed")
        # graceful fallback
        return [
            Recommendation(title="Free up storage", description=f"Clean {req.junk_mb:.0f}MB of junk and cache files to speed up your device.", impact="high"),
            Recommendation(title="Remove duplicate photos", description=f"You have {req.duplicates_mb:.0f}MB in duplicates—safe to remove after review.", impact="medium"),
            Recommendation(title="Optimize battery", description="Restrict background activity for high-drain apps to extend battery life.", impact="medium"),
            Recommendation(title="Review app permissions", description="Some apps have broader access than they need. A quick review improves privacy.", impact="low"),
        ]


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
