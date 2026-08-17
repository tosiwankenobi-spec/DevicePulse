from fastapi import FastAPI, APIRouter, HTTPException, Request
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
from datetime import datetime, timezone, timedelta

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
    device_id: Optional[str] = "anon"

class HistoryEntry(BaseModel):
    id: str
    categories: List[str]
    reclaimed_mb: float
    completed_at: str

class ReferralStatus(BaseModel):
    device_id: str
    code: str
    invited_count: int
    reward_days: int

class ReminderPrefs(BaseModel):
    device_id: str
    low_storage: bool = True
    weekly_cleanup: bool = True
    after_downloads: bool = True
    battery_alerts: bool = False

class FamilyMember(BaseModel):
    id: str
    name: str
    device_type: str  # phone, tablet
    added_at: str

class AddMemberRequest(BaseModel):
    name: str
    device_type: str = "phone"


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


# SEC-001: lightweight in-memory rate limiter for the paid LLM endpoint
import time as _time
_AI_CALLS: dict = {}
_AI_WINDOW_SEC = 60
_AI_MAX_PER_WINDOW = 10

def _allow_ai_call(client_key: str) -> bool:
    now = _time.time()
    bucket = [t for t in _AI_CALLS.get(client_key, []) if now - t < _AI_WINDOW_SEC]
    if len(bucket) >= _AI_MAX_PER_WINDOW:
        _AI_CALLS[client_key] = bucket
        return False
    bucket.append(now)
    _AI_CALLS[client_key] = bucket
    return True


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
        "device_id": req.device_id or "anon",
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

@api_router.get("/history", response_model=List[HistoryEntry])
async def get_history(device_id: str = "anon"):
    docs = await db.cleanups.find({"device_id": device_id}).sort("completed_at", -1).to_list(100)
    return [
        HistoryEntry(
            id=d["id"],
            categories=d.get("categories", []),
            reclaimed_mb=d.get("reclaimed_mb", 0.0),
            completed_at=d.get("completed_at", ""),
        )
        for d in docs
    ]

@api_router.get("/history/summary")
async def get_history_summary(device_id: str = "anon"):
    docs = await db.cleanups.find({"device_id": device_id}).to_list(1000)
    total_reclaimed = sum(d.get("reclaimed_mb", 0.0) for d in docs)
    return {
        "total_cleanups": len(docs),
        "total_reclaimed_mb": round(total_reclaimed, 1),
        "total_reclaimed_gb": round(total_reclaimed / 1024, 2),
    }

def _referral_code(device_id: str) -> str:
    seed = abs(hash(device_id)) % 100000
    return f"PULSE{seed:05d}"

@api_router.get("/referral/{device_id}", response_model=ReferralStatus)
async def get_referral(device_id: str):
    doc = await db.referrals.find_one({"device_id": device_id})
    if not doc:
        doc = {
            "device_id": device_id,
            "code": _referral_code(device_id),
            "invited_count": 0,
        }
        await db.referrals.insert_one(doc.copy())
    return ReferralStatus(
        device_id=device_id,
        code=doc["code"],
        invited_count=doc.get("invited_count", 0),
        reward_days=doc.get("invited_count", 0) * 7,
    )

@api_router.post("/referral/{device_id}/invite", response_model=ReferralStatus)
async def record_invite(device_id: str):
    doc = await db.referrals.find_one({"device_id": device_id})
    if not doc:
        doc = {"device_id": device_id, "code": _referral_code(device_id), "invited_count": 0}
        await db.referrals.insert_one(doc.copy())
    new_count = min(doc.get("invited_count", 0) + 1, 100)  # cap to prevent unbounded inflation
    await db.referrals.update_one({"device_id": device_id}, {"$set": {"invited_count": new_count}})
    return ReferralStatus(
        device_id=device_id,
        code=doc["code"],
        invited_count=new_count,
        reward_days=new_count * 7,
    )

@api_router.get("/reminders/{device_id}", response_model=ReminderPrefs)
async def get_reminders(device_id: str):
    doc = await db.reminders.find_one({"device_id": device_id})
    if not doc:
        prefs = ReminderPrefs(device_id=device_id)
        await db.reminders.insert_one(prefs.dict())
        return prefs
    return ReminderPrefs(
        device_id=device_id,
        low_storage=doc.get("low_storage", True),
        weekly_cleanup=doc.get("weekly_cleanup", True),
        after_downloads=doc.get("after_downloads", True),
        battery_alerts=doc.get("battery_alerts", False),
    )

@api_router.put("/reminders/{device_id}", response_model=ReminderPrefs)
async def update_reminders(device_id: str, prefs: ReminderPrefs):
    data = prefs.dict()
    data["device_id"] = device_id
    await db.reminders.update_one({"device_id": device_id}, {"$set": data}, upsert=True)
    return ReminderPrefs(**data)

@api_router.get("/streak/{device_id}")
async def get_streak(device_id: str):
    docs = await db.cleanups.find({"device_id": device_id}).sort("completed_at", -1).to_list(1000)
    total_cleanups = len(docs)

    weeks_with = set()
    for d in docs:
        try:
            dt = datetime.fromisoformat(d["completed_at"])
            iso = dt.isocalendar()
            weeks_with.add((iso[0], iso[1]))
        except Exception:
            pass

    # frozen weeks bridge gaps
    freeze_docs = await db.freezes.find({"device_id": device_id}).to_list(200)
    frozen_weeks = set()
    for f in freeze_docs:
        try:
            y, w = f["week_key"].split("-")
            frozen_weeks.add((int(y), int(w)))
        except Exception:
            pass

    active_weeks = weeks_with | frozen_weeks

    now = datetime.now(timezone.utc)
    cur_iso = now.isocalendar()
    cur_month = now.strftime("%Y-%m")

    def week_minus(base_year, base_week, n):
        ref = datetime.fromisocalendar(base_year, base_week, 1).replace(tzinfo=timezone.utc)
        ref = ref - timedelta(weeks=n)
        iso = ref.isocalendar()
        return (iso[0], iso[1])

    current_streak = 0
    start_offset = 0 if (cur_iso[0], cur_iso[1]) in active_weeks else 1
    if start_offset == 1 and week_minus(cur_iso[0], cur_iso[1], 1) not in active_weeks:
        current_streak = 0
    else:
        n = start_offset
        while week_minus(cur_iso[0], cur_iso[1], n) in active_weeks:
            current_streak += 1
            n += 1

    grid = []
    for i in range(7, -1, -1):
        wk = week_minus(cur_iso[0], cur_iso[1], i)
        grid.append({
            "active": wk in weeks_with,
            "frozen": wk in frozen_weeks and wk not in weeks_with,
        })

    milestones = [
        {"key": "first_clean", "label": "First Cleanup", "icon": "sparkles", "unlocked": total_cleanups >= 1, "req": 1},
        {"key": "streak_2", "label": "2-Week Streak", "icon": "flame", "unlocked": current_streak >= 2, "req": 2},
        {"key": "clean_5", "label": "5 Cleanups", "icon": "trophy", "unlocked": total_cleanups >= 5, "req": 5},
        {"key": "streak_4", "label": "4-Week Streak", "icon": "flame", "unlocked": current_streak >= 4, "req": 4},
        {"key": "clean_10", "label": "10 Cleanups", "icon": "medal", "unlocked": total_cleanups >= 10, "req": 10},
        {"key": "streak_8", "label": "8-Week Streak", "icon": "ribbon", "unlocked": current_streak >= 8, "req": 8},
    ]

    freeze_used_this_month = any(f.get("month_key") == cur_month for f in freeze_docs)

    return {
        "current_streak_weeks": current_streak,
        "total_cleanups": total_cleanups,
        "week_grid": grid,
        "milestones": milestones,
        "this_week_done": (cur_iso[0], cur_iso[1]) in weeks_with,
        "freeze_available": not freeze_used_this_month,
        "freezes_used": len([f for f in freeze_docs]),
    }

@api_router.post("/streak/{device_id}/freeze")
async def use_freeze(device_id: str):
    now = datetime.now(timezone.utc)
    cur_iso = now.isocalendar()
    cur_month = now.strftime("%Y-%m")

    existing = await db.freezes.find_one({"device_id": device_id, "month_key": cur_month})
    if existing:
        raise HTTPException(400, "You've already used your freeze this month")

    docs = await db.cleanups.find({"device_id": device_id}).to_list(1000)
    weeks_with = set()
    for d in docs:
        try:
            iso = datetime.fromisoformat(d["completed_at"]).isocalendar()
            weeks_with.add((iso[0], iso[1]))
        except Exception:
            pass
    freeze_docs = await db.freezes.find({"device_id": device_id}).to_list(200)
    frozen = set()
    for f in freeze_docs:
        y, w = f["week_key"].split("-")
        frozen.add((int(y), int(w)))

    def week_minus(n):
        ref = datetime.fromisocalendar(cur_iso[0], cur_iso[1], 1).replace(tzinfo=timezone.utc) - timedelta(weeks=n)
        iso = ref.isocalendar()
        return (iso[0], iso[1])

    # find the most recent missed week (gap) to bridge, within last 8 weeks
    target = None
    for n in range(0, 8):
        wk = week_minus(n)
        if wk not in weeks_with and wk not in frozen:
            target = wk
            break

    if target is None:
        raise HTTPException(400, "No missed week to protect right now")

    doc = {
        "device_id": device_id,
        "week_key": f"{target[0]}-{target[1]}",
        "month_key": cur_month,
        "applied_at": now.isoformat(),
    }
    await db.freezes.insert_one(doc.copy())
    return {"frozen_week": doc["week_key"], "month_key": cur_month}

@api_router.get("/device/cache-breakdown")
async def get_cache_breakdown(device_id: str = "anon"):
    apps = [
        {"app": "Instagram", "icon": "📷", "cache_mb": 342.6, "category": "Social"},
        {"app": "Chrome", "icon": "🌐", "cache_mb": 218.4, "category": "Browser"},
        {"app": "YouTube", "icon": "▶️", "cache_mb": 512.9, "category": "Media"},
        {"app": "WhatsApp", "icon": "💬", "cache_mb": 168.2, "category": "Messaging"},
        {"app": "Spotify", "icon": "🎵", "cache_mb": 286.1, "category": "Media"},
        {"app": "TikTok", "icon": "🎬", "cache_mb": 431.7, "category": "Social"},
        {"app": "Maps", "icon": "🗺️", "cache_mb": 94.3, "category": "Navigation"},
        {"app": "Gmail", "icon": "✉️", "cache_mb": 62.8, "category": "Productivity"},
    ]
    for a in apps:
        a["id"] = str(uuid.uuid4())
    apps.sort(key=lambda x: x["cache_mb"], reverse=True)
    total = round(sum(a["cache_mb"] for a in apps), 1)
    return {"total_mb": total, "apps": apps}

@api_router.get("/device/health-trend/{device_id}")
async def get_health_trend(device_id: str):
    docs = await db.cleanups.find({"device_id": device_id}).to_list(1000)
    weeks_with = {}
    for d in docs:
        try:
            iso = datetime.fromisoformat(d["completed_at"]).isocalendar()
            key = (iso[0], iso[1])
            weeks_with[key] = weeks_with.get(key, 0) + 1
        except Exception:
            pass

    now = datetime.now(timezone.utc)
    cur_iso = now.isocalendar()

    def week_info(n):
        ref = datetime.fromisocalendar(cur_iso[0], cur_iso[1], 1).replace(tzinfo=timezone.utc) - timedelta(weeks=n)
        iso = ref.isocalendar()
        return (iso[0], iso[1]), ref

    points = []
    score = 58
    for i in range(7, -1, -1):
        (wk, ref) = week_info(i)
        if wk in weeks_with:
            score = min(97, score + 8)
        else:
            score = max(45, score - 3)
        points.append({
            "label": ref.strftime("%b %d"),
            "score": score,
            "cleaned": wk in weeks_with,
        })

    first = points[0]["score"]
    last = points[-1]["score"]
    return {
        "points": points,
        "change": last - first,
        "current": last,
    }

@api_router.get("/forecast/{device_id}")
async def get_forecast(device_id: str):
    total_gb = 128.0
    used_gb = 94.2  # seed baseline

    # lifetime reclaimed reduces used slightly (capped)
    docs = await db.cleanups.find({"device_id": device_id}).to_list(1000)
    reclaimed_gb = min(20.0, sum(d.get("reclaimed_mb", 0.0) for d in docs) / 1024)
    used_gb = max(20.0, used_gb - reclaimed_gb)
    free_gb = round(total_gb - used_gb, 1)

    daily_growth_gb = 0.72  # typical media/cache accumulation
    days_until_full = int(free_gb / daily_growth_gb) if daily_growth_gb > 0 else 999
    projected_full = (datetime.now(timezone.utc) + timedelta(days=days_until_full))

    # projection samples every 5 days until full (max 12 points)
    projection = []
    d = 0
    while d <= days_until_full and len(projection) < 13:
        pu = min(total_gb, used_gb + daily_growth_gb * d)
        projection.append({"day": d, "used_gb": round(pu, 1), "pct": round(pu / total_gb * 100)})
        d += max(1, days_until_full // 12)

    if projection[-1]["day"] < days_until_full:
        projection.append({"day": days_until_full, "used_gb": total_gb, "pct": 100})

    return {
        "total_gb": total_gb,
        "used_gb": round(used_gb, 1),
        "free_gb": free_gb,
        "daily_growth_gb": daily_growth_gb,
        "days_until_full": days_until_full,
        "projected_full_date": projected_full.strftime("%b %d, %Y"),
        "projection": projection,
    }

@api_router.get("/family/{device_id}", response_model=List[FamilyMember])
async def get_family(device_id: str):
    docs = await db.family.find({"owner_id": device_id}).sort("added_at", 1).to_list(50)
    return [
        FamilyMember(id=d["id"], name=d["name"], device_type=d["device_type"], added_at=d["added_at"])
        for d in docs
    ]

@api_router.post("/family/{device_id}/member", response_model=FamilyMember)
async def add_family_member(device_id: str, req: AddMemberRequest):
    count = await db.family.count_documents({"owner_id": device_id})
    if count >= 5:
        raise HTTPException(400, "Family plan supports up to 5 devices")
    name = (req.name or "").strip()[:40]  # cap length to prevent oversized input
    if not name:
        raise HTTPException(400, "Name is required")
    device_type = req.device_type if req.device_type in ("phone", "tablet") else "phone"
    member = {
        "id": str(uuid.uuid4()),
        "owner_id": device_id,
        "name": name,
        "device_type": device_type,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.family.insert_one(member.copy())
    return FamilyMember(id=member["id"], name=member["name"], device_type=member["device_type"], added_at=member["added_at"])

@api_router.delete("/family/{device_id}/member/{member_id}")
async def remove_family_member(device_id: str, member_id: str):
    await db.family.delete_one({"owner_id": device_id, "id": member_id})
    return {"removed": member_id}

@api_router.post("/ai/recommendations", response_model=List[Recommendation])
async def get_ai_recommendations(req: RecommendationRequest, request: Request):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "LLM key not configured")

    # SEC-001: simple per-client rate limit on the paid LLM endpoint
    client_key = request.client.host if request.client else "unknown"
    if not _allow_ai_call(client_key):
        raise HTTPException(429, "Too many requests. Please wait a moment and try again.")

    # SEC-003: treat platform as data, not prompt text (allowlist)
    platform = req.platform if req.platform in ("android", "ios") else "android"

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
        f"- Platform: {platform}\n\n"
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
    allow_credentials=False,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
