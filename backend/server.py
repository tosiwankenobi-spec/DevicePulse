from fastapi import FastAPI, APIRouter, HTTPException, Request, Header, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
import uuid
import httpx
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
EMERGENT_AUTH_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

# ---------- Emergent managed push ----------
PUSH_BASE_URL = "https://integrations.emergentagent.com"
PUSH_KEY = os.environ.get("EMERGENT_PUSH_KEY", "placeholder")
_push_client = httpx.AsyncClient(base_url=PUSH_BASE_URL, headers={"X-Push-Key": PUSH_KEY}, timeout=10.0)

class RegisterPushBody(BaseModel):
    user_id: str
    platform: str
    device_token: str

async def send_push(recipients: List[str], data: dict, idempotency_key: Optional[str] = None) -> None:
    if not recipients:
        return
    if len(recipients) > 100:
        raise ValueError("max 100 recipients per /trigger call; chunk before sending")
    if "title" not in data or "message" not in data:
        raise ValueError("data must include title and message")
    payload: dict = {"recipients": recipients, "data": data}
    if idempotency_key:
        payload["$idempotency_key"] = idempotency_key
    resp = await _push_client.post("/api/v1/push/trigger", json=payload)
    if resp.status_code == 401:
        raise HTTPException(500, "EMERGENT_PUSH_KEY missing or invalid")
    if resp.status_code >= 500:
        raise HTTPException(502, "Push provider unavailable")
    resp.raise_for_status()


app = FastAPI()
api_router = APIRouter(prefix="/api")


# ==================== Auth Models & Helpers ====================
class SessionRequest(BaseModel):
    session_id: str

class UserPublic(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None

async def get_current_user(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1].strip()
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = session.get("expires_at")
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Session expired")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


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

class CoachChatRequest(BaseModel):
    message: str
    health_score: Optional[int] = None
    storage_used_pct: Optional[float] = None
    battery_health_pct: Optional[int] = None

class CoachMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    created_at: str

class CoachDaily(BaseModel):
    date: str
    greeting: str
    tip_title: str
    tip_body: str
    focus: str  # storage | battery | security | photos | general
    action_label: str
    action_route: str

class CoachInsight(BaseModel):
    key: str          # stable id, e.g. "win_clean_5" or "pattern_duplicates"
    kind: str         # "win" | "pattern"
    title: str
    body: str
    icon: str         # Ionicons name
    action_label: Optional[str] = None
    action_route: Optional[str] = None

class PulseDaily(BaseModel):
    date: str
    score: int
    status: str  # Excellent | Good | Needs Attention | Poor
    headline: str
    delta: int  # change vs yesterday's pulse score; 0 if no prior data
    storage_used_pct: int
    battery_pct: int
    security_ok: bool

class WidgetSummary(BaseModel):
    score: int
    status: str  # Excellent | Good | Needs Attention | Poor
    storage_used_pct: int
    storage_used_gb: float
    storage_total_gb: float
    battery_pct: int
    security_ok: bool
    updated_at: str  # ISO timestamp of this computation — proves the widget is live

class Nudge(BaseModel):
    type: str  # storage_critical | security | storage_reclaim
    title: str
    message: str
    cta_label: str
    cta_route: str
    priority: int  # lower = more urgent; only the top qualifying nudge is ever returned


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


def _compute_daily_pulse_score(cleanups: list) -> tuple:
    """Deterministic, non-LLM health-score computation for the Daily Pulse Check
    card. Rewards recent activity (cleaned up in the last 24h) and gently
    penalizes long inactivity, anchored to the same baseline score used
    elsewhere in the app (_seed_health)."""
    now = datetime.now(timezone.utc)
    last_cleanup_dt = None
    cleanups_last_7d = 0
    for d in cleanups:
        try:
            dt = datetime.fromisoformat(d["completed_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if last_cleanup_dt is None or dt > last_cleanup_dt:
            last_cleanup_dt = dt
        if (now - dt).days < 7:
            cleanups_last_7d += 1

    score = _seed_health().score + min(24, cleanups_last_7d * 6)
    cleaned_last_24h = False
    if last_cleanup_dt:
        hours_since = (now - last_cleanup_dt).total_seconds() / 3600
        if hours_since <= 24:
            score += 5
            cleaned_last_24h = True
        elif hours_since > 24 * 7:
            score -= 8
    else:
        score -= 5  # never cleaned up yet
    score = max(40, min(97, score))
    return score, cleaned_last_24h


def _pulse_status_band(score: int) -> str:
    """Shared score->status banding, used by both the Daily Pulse Check card
    and the live Home Screen Widget summary so their labels always agree."""
    if score >= 85:
        return "Excellent"
    elif score >= 65:
        return "Good"
    elif score >= 50:
        return "Needs Attention"
    else:
        return "Poor"


def _pulse_headline(score: int, cleaned_last_24h: bool, storage_pct: int) -> str:
    if cleaned_last_24h:
        return "Nice work — you cleaned up recently and it shows."
    if score >= 85:
        return "Your device is in great shape today."
    if score >= 65:
        if storage_pct >= 80:
            return "Storage is getting tight — a quick scan would help."
        return "Looking solid. A quick scan keeps it that way."
    return "Your device could use some attention today."


NUDGE_DISMISS_COOLDOWN_HOURS = 24
NUDGE_TYPES = {"storage_reclaim", "security", "storage_forecast"}


def _estimate_reclaimable_mb(cleanups: list) -> float:
    """Deterministic, non-LLM estimate of currently-reclaimable junk/cache/
    duplicates. Junk re-accumulates over time after a cleanup (~35MB/hour),
    capped at a plausible ceiling; a user who has never cleaned up is treated
    as already at a steady-state amount of accumulated junk."""
    now = datetime.now(timezone.utc)
    last_cleanup_dt = None
    for d in cleanups:
        try:
            dt = datetime.fromisoformat(d["completed_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if last_cleanup_dt is None or dt > last_cleanup_dt:
            last_cleanup_dt = dt

    if last_cleanup_dt is None:
        return 1850.0

    hours_since = (now - last_cleanup_dt).total_seconds() / 3600
    return round(min(3600.0, hours_since * 35.0), 1)


def _build_nudge_candidates(seed: DeviceHealth, reclaimable_mb: float, forecast: Optional[dict] = None) -> list:
    """Smart Nudges: surface at most one nudge, and only when a condition
    actually crosses a threshold worth interrupting the user for — not on
    every open. Candidates are ranked by priority (lower = more urgent).

    Three conditions are wired up today, all driven by real per-user state:
    a genuinely time-sensitive storage forecast (Predictive Storage — only
    fires once there's real cleanup history to project a trend from, and
    outranks the other two since "you'll run out of space in N days" is more
    urgent than a generic reclaim suggestion), a meaningful amount of
    reclaimable junk (the flagship "You could reclaim 2.3 GB right now"
    case), and an open security finding (acts as an always-available fallback
    nudge under the app's current simulated baseline, which is a deliberately
    simpler starting set than a full multi-signal nudge engine — easy to
    extend with more candidates later)."""
    security_ok = "issue" not in seed.security_status.lower()
    candidates = []

    if forecast and forecast.get("has_trend") and forecast["days_until_full"] <= FORECAST_ALERT_DAYS:
        days = forecast["days_until_full"]
        candidates.append(Nudge(
            type="storage_forecast",
            title="Storage running low",
            message=f"At this rate you'll run out of space in {days} day{'s' if days != 1 else ''}.",
            cta_label="Fix now",
            cta_route="/forecast",
            priority=0,
        ))

    if reclaimable_mb >= 1500:
        gb = round(reclaimable_mb / 1024, 1)
        candidates.append(Nudge(
            type="storage_reclaim",
            title="Space to reclaim",
            message=f"You could reclaim {gb} GB right now.",
            cta_label="Free up space",
            cta_route="/smart-scan",
            priority=1,
        ))

    if not security_ok:
        candidates.append(Nudge(
            type="security",
            title="Security check needed",
            message=f"{seed.security_status.capitalize()} found on your device — worth a look.",
            cta_label="Review",
            cta_route="/insights",
            priority=2,
        ))

    candidates.sort(key=lambda n: n.priority)
    return candidates


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

# ---------- Auth ----------
@api_router.post("/auth/session")
async def create_session(body: SessionRequest):
    session_id = body.session_id
    try:
        async with httpx.AsyncClient(timeout=15) as hc:
            resp = await hc.get(EMERGENT_AUTH_URL, headers={"X-Session-ID": session_id})
    except Exception:
        raise HTTPException(status_code=401, detail="Auth service unavailable")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session")
    data = resp.json()
    email = data.get("email")
    name = data.get("name") or (email.split("@")[0] if email else "User")
    picture = data.get("picture")
    session_token = data.get("session_token")
    if not email or not session_token:
        raise HTTPException(status_code=401, detail="Incomplete session data")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id}, {"$set": {"name": name, "picture": picture}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    await db.user_sessions.insert_one({
        "session_token": session_token,
        "sid": uuid.uuid4().hex[:12],
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    })

    return {
        "session_token": session_token,
        "user": {"user_id": user_id, "email": email, "name": name, "picture": picture},
    }

@api_router.get("/auth/me", response_model=UserPublic)
async def auth_me(user=Depends(get_current_user)):
    return UserPublic(user_id=user["user_id"], email=user["email"], name=user["name"], picture=user.get("picture"))

@api_router.post("/auth/logout")
async def auth_logout(authorization: Optional[str] = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        await db.user_sessions.delete_one({"session_token": token})
    return {"ok": True}

@api_router.get("/auth/sessions")
async def list_sessions(user=Depends(get_current_user), authorization: Optional[str] = Header(default=None)):
    cur_token = authorization.split(" ", 1)[1].strip() if authorization and authorization.startswith("Bearer ") else ""
    docs = await db.user_sessions.find({"user_id": user["user_id"]}).sort("created_at", -1).to_list(50)
    out = []
    for d in docs:
        sid = d.get("sid")
        if not sid:
            sid = uuid.uuid4().hex[:12]
            await db.user_sessions.update_one({"session_token": d["session_token"]}, {"$set": {"sid": sid}})
        created = d.get("created_at")
        expires = d.get("expires_at")
        out.append({
            "sid": sid,
            "created_at": created.isoformat() if isinstance(created, datetime) else str(created),
            "expires_at": expires.isoformat() if isinstance(expires, datetime) else str(expires),
            "current": d.get("session_token") == cur_token,
        })
    return out

@api_router.post("/auth/sessions/{sid}/revoke")
async def revoke_session(sid: str, user=Depends(get_current_user)):
    res = await db.user_sessions.delete_one({"user_id": user["user_id"], "sid": sid})
    return {"revoked": res.deleted_count > 0}

@api_router.delete("/auth/account")
async def delete_account(user=Depends(get_current_user)):
    uid = user["user_id"]
    # Remove all data owned by this user
    await db.cleanups.delete_many({"device_id": uid})
    await db.referrals.delete_many({"device_id": uid})
    await db.reminders.delete_many({"device_id": uid})
    await db.freezes.delete_many({"device_id": uid})
    await db.family.delete_many({"owner_id": uid})
    await db.user_sessions.delete_many({"user_id": uid})
    await db.users.delete_one({"user_id": uid})
    return {"deleted": True}

# ---------- Push ----------
@api_router.post("/register-push", status_code=201)
async def register_push(body: RegisterPushBody, user=Depends(get_current_user)):
    # Derive identity from the authenticated token (ignore any client-supplied user_id)
    payload = {"user_id": user["user_id"], "platform": body.platform, "device_token": body.device_token}
    resp = await _push_client.post("/api/v1/push/users/register", json=payload)
    if resp.status_code == 401:
        raise HTTPException(500, "EMERGENT_PUSH_KEY missing or invalid")
    if resp.status_code >= 500:
        raise HTTPException(502, "Push provider unavailable")
    resp.raise_for_status()
    return {"status": "registered"}

@api_router.post("/push/test")
async def push_test(user=Depends(get_current_user)):
    try:
        await send_push(
            recipients=[user["user_id"]],
            data={
                "title": "DevicePulse",
                "message": "Push notifications are working! Your device is in good hands. ⚡",
                "action_url": "/(tabs)",
            },
            idempotency_key=f"test-{user['user_id']}-{uuid.uuid4().hex[:8]}",
        )
        return {"sent": True}
    except Exception as e:
        logging.warning(f"Test push failed (non-blocking): {e}")
        return {"sent": False, "reason": "Push delivers only on a real device after publishing a build."}

@api_router.post("/push/cleanup-reminder")
async def push_cleanup_reminder(user=Depends(get_current_user)):
    """Weekly cleanup reminder + streak-at-risk nudge for the current user."""
    uid = user["user_id"]
    # streak-at-risk check
    docs = await db.cleanups.find({"device_id": uid}).to_list(1000)
    weeks_with = set()
    for d in docs:
        try:
            iso = datetime.fromisoformat(d["completed_at"]).isocalendar()
            weeks_with.add((iso[0], iso[1]))
        except Exception:
            pass
    cur = datetime.now(timezone.utc).isocalendar()
    this_week_done = (cur[0], cur[1]) in weeks_with
    if this_week_done:
        title, message = "Nice work this week", "Your device is optimized. Keep the streak alive next week!"
    else:
        title, message = "Time to optimize", "Your device could use a quick scan to stay fast and clean."
    try:
        await send_push(recipients=[uid], data={"title": title, "message": message, "action_url": "/smart-scan"},
                        idempotency_key=f"reminder-{uid}-{cur[0]}-{cur[1]}")
        return {"sent": True}
    except Exception as e:
        logging.warning(f"Reminder push failed (non-blocking): {e}")
        return {"sent": False}



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
async def run_clean(req: CleanupRequest, user=Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "device_id": user["user_id"],
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
async def get_history(user=Depends(get_current_user)):
    device_id = user["user_id"]
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
async def get_history_summary(user=Depends(get_current_user)):
    device_id = user["user_id"]
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

@api_router.get("/referral", response_model=ReferralStatus)
async def get_referral(user=Depends(get_current_user)):
    device_id = user["user_id"]
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

@api_router.post("/referral/invite", response_model=ReferralStatus)
async def record_invite(user=Depends(get_current_user)):
    device_id = user["user_id"]
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

@api_router.get("/reminders", response_model=ReminderPrefs)
async def get_reminders(user=Depends(get_current_user)):
    device_id = user["user_id"]
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

@api_router.put("/reminders", response_model=ReminderPrefs)
async def update_reminders(prefs: ReminderPrefs, user=Depends(get_current_user)):
    device_id = user["user_id"]
    data = prefs.dict()
    data["device_id"] = device_id
    await db.reminders.update_one({"device_id": device_id}, {"$set": data}, upsert=True)
    return ReminderPrefs(**data)

async def _compute_streak_data(device_id: str) -> dict:
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

@api_router.get("/streak")
async def get_streak(user=Depends(get_current_user)):
    return await _compute_streak_data(user["user_id"])

@api_router.post("/streak/freeze")
async def use_freeze(user=Depends(get_current_user)):
    device_id = user["user_id"]
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
async def get_cache_breakdown(user=Depends(get_current_user)):
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

@api_router.get("/device/health-trend")
async def get_health_trend(user=Depends(get_current_user)):
    device_id = user["user_id"]
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

# ---------- Predictive Storage ----------
# The daily fill rate is no longer a fixed constant: it's derived from how
# long it's been since the user's last cleanup (the same idle-time signal
# Smart Nudges uses for its reclaimable-junk estimate). A user who cleans up
# regularly gets a slow, comfortable projection; a user who has let junk pile
# up unchecked for weeks gets a fast one — which is what makes "at this rate
# you'll run out of space in N days" an honest, personalized warning instead
# of a canned number. Deterministic and capped, so it stays fully testable.
DEFAULT_DAILY_GROWTH_GB = 0.3  # used only when there's no cleanup history yet to project from
FORECAST_ALERT_DAYS = 14


def _estimate_daily_growth_gb(cleanups: list) -> Optional[float]:
    """Returns None when there isn't enough history yet to project a trend
    (no cleanups on record) — mirrors the same "not enough signal" gating used
    elsewhere (Coach's pattern insight, Nudges' storage_critical decision)."""
    if not cleanups:
        return None
    now = datetime.now(timezone.utc)
    last_cleanup_dt = None
    for d in cleanups:
        try:
            dt = datetime.fromisoformat(d["completed_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if last_cleanup_dt is None or dt > last_cleanup_dt:
            last_cleanup_dt = dt
    if last_cleanup_dt is None:
        return None
    idle_days = max(0.0, (now - last_cleanup_dt).total_seconds() / 86400)
    # 0.3 GB/day baseline, climbing toward 3.0 GB/day the longer junk/cache
    # has been left unchecked, capped at 45 idle days.
    growth = 0.3 + min(2.7, idle_days * (2.7 / 45))
    return round(growth, 2)


async def _compute_forecast(device_id: str) -> dict:
    total_gb = 128.0
    used_gb = 94.2  # seed baseline

    # lifetime reclaimed reduces used slightly (capped)
    docs = await db.cleanups.find({"device_id": device_id}).to_list(1000)
    reclaimed_gb = min(20.0, sum(d.get("reclaimed_mb", 0.0) for d in docs) / 1024)
    used_gb = max(20.0, used_gb - reclaimed_gb)
    free_gb = round(total_gb - used_gb, 1)

    trend_growth = _estimate_daily_growth_gb(docs)
    daily_growth_gb = trend_growth if trend_growth is not None else DEFAULT_DAILY_GROWTH_GB
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
        "has_trend": trend_growth is not None,
    }


@api_router.get("/forecast")
async def get_forecast(user=Depends(get_current_user)):
    return await _compute_forecast(user["user_id"])


@api_router.post("/forecast/quick-fix")
async def forecast_quick_fix(user=Depends(get_current_user)):
    """The roadmap's "one-tap fix": runs an immediate simulated cleanup sized
    to the user's own reclaimable-junk estimate (same estimator Smart Nudges
    uses), no category picker or extra screen required, and returns the
    freshly-recomputed forecast so the caller can show the improvement."""
    user_id = user["user_id"]
    cleanups = await db.cleanups.find({"device_id": user_id}).to_list(1000)
    reclaimed_mb = _estimate_reclaimable_mb(cleanups)
    doc = {
        "id": str(uuid.uuid4()),
        "device_id": user_id,
        "categories": ["Predictive quick fix"],
        "reclaimed_mb": reclaimed_mb,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.cleanups.insert_one(doc.copy())
    forecast = await _compute_forecast(user_id)
    return {"reclaimed_mb": reclaimed_mb, "forecast": forecast}

# ---------- Daily Pulse Check ----------
# A lightweight, non-LLM "morning health score" — one glance, cached per
# user per (UTC) day, same caching shape as /coach/daily. Deliberately has
# no AI dependency: it should be fast and free to compute so it can run on
# every app open without rate limits or an LLM key.
@api_router.get("/pulse/daily", response_model=PulseDaily)
async def pulse_daily(user=Depends(get_current_user)):
    user_id = user["user_id"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    cached = await db.pulse_daily.find_one({"user_id": user_id, "date": today}, {"_id": 0})
    if cached:
        return PulseDaily(**{k: v for k, v in cached.items() if k not in ("user_id",)})

    cleanups = await db.cleanups.find({"device_id": user_id}).to_list(1000)
    score, cleaned_last_24h = _compute_daily_pulse_score(cleanups)

    seed = _seed_health()
    storage_pct = round(seed.storage_used_gb / seed.storage_total_gb * 100)
    security_ok = "issue" not in seed.security_status.lower()

    status = _pulse_status_band(score)
    headline = _pulse_headline(score, cleaned_last_24h, storage_pct)

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    prev = await db.pulse_daily.find_one({"user_id": user_id, "date": yesterday}, {"_id": 0, "score": 1})
    delta = (score - prev["score"]) if prev else 0

    card = PulseDaily(
        date=today,
        score=score,
        status=status,
        headline=headline,
        delta=delta,
        storage_used_pct=storage_pct,
        battery_pct=seed.battery_pct,
        security_ok=security_ok,
    )
    doc = card.dict()
    doc["user_id"] = user_id
    await db.pulse_daily.insert_one(doc.copy())
    return card

# ---------- Home Screen Widget (live) ----------
# Backs the in-app widget preview (and, once a native build exists, the real
# iOS/Android home-screen widget extension) with an actual live snapshot.
# Unlike /pulse/daily this is intentionally NOT cached per day: every call
# recomputes from current cleanup history and "now", so the score/labels
# genuinely move in real time (e.g. right after a cleanup) rather than
# waiting for the next calendar day like the once-daily Pulse Check card.
@api_router.get("/widget/summary", response_model=WidgetSummary)
async def widget_summary(user=Depends(get_current_user)):
    user_id = user["user_id"]
    cleanups = await db.cleanups.find({"device_id": user_id}).to_list(1000)
    score, _cleaned_last_24h = _compute_daily_pulse_score(cleanups)

    seed = _seed_health()
    storage_pct = round(seed.storage_used_gb / seed.storage_total_gb * 100)
    security_ok = "issue" not in seed.security_status.lower()

    return WidgetSummary(
        score=score,
        status=_pulse_status_band(score),
        storage_used_pct=storage_pct,
        storage_used_gb=seed.storage_used_gb,
        storage_total_gb=seed.storage_total_gb,
        battery_pct=seed.battery_pct,
        security_ok=security_ok,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

# ---------- Smart Nudges ----------
# "You could reclaim 2.3 GB right now" — surfaced only when it actually
# matters, not spam. At most ONE nudge is ever returned (the highest-priority
# qualifying condition), and once a user dismisses a nudge type it stays
# quiet for NUDGE_DISMISS_COOLDOWN_HOURS even if the underlying condition is
# still true.
@api_router.get("/nudges/active", response_model=Optional[Nudge])
async def get_active_nudge(user=Depends(get_current_user)):
    user_id = user["user_id"]
    cleanups = await db.cleanups.find({"device_id": user_id}).to_list(1000)
    reclaimable_mb = _estimate_reclaimable_mb(cleanups)
    seed = _seed_health()
    forecast = await _compute_forecast(user_id)
    candidates = _build_nudge_candidates(seed, reclaimable_mb, forecast)
    if not candidates:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(hours=NUDGE_DISMISS_COOLDOWN_HOURS)
    dismissals = await db.nudge_dismissals.find(
        {"user_id": user_id, "dismissed_at": {"$gte": cutoff}}
    ).to_list(10)
    dismissed_types = {d["type"] for d in dismissals}

    for candidate in candidates:
        if candidate.type not in dismissed_types:
            return candidate
    return None

@api_router.post("/nudges/{nudge_type}/dismiss")
async def dismiss_nudge(nudge_type: str, user=Depends(get_current_user)):
    if nudge_type not in NUDGE_TYPES:
        raise HTTPException(status_code=400, detail="Unknown nudge type")
    user_id = user["user_id"]
    await db.nudge_dismissals.update_one(
        {"user_id": user_id, "type": nudge_type},
        {"$set": {"dismissed_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"dismissed": True, "type": nudge_type}

@api_router.get("/family", response_model=List[FamilyMember])
async def get_family(user=Depends(get_current_user)):
    device_id = user["user_id"]
    docs = await db.family.find({"owner_id": device_id}).sort("added_at", 1).to_list(50)
    return [
        FamilyMember(id=d["id"], name=d["name"], device_type=d["device_type"], added_at=d["added_at"])
        for d in docs
    ]

@api_router.post("/family/member", response_model=FamilyMember)
async def add_family_member(req: AddMemberRequest, user=Depends(get_current_user)):
    device_id = user["user_id"]
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
    try:
        await send_push(
            recipients=[device_id],
            data={"title": "Family plan updated", "message": f"{name} was added to your family plan.", "action_url": "/family"},
            idempotency_key=f"family-{member['id']}",
        )
    except Exception as e:
        logging.warning(f"Family push failed (non-blocking): {e}")
    return FamilyMember(id=member["id"], name=member["name"], device_type=member["device_type"], added_at=member["added_at"])

@api_router.delete("/family/member/{member_id}")
async def remove_family_member(member_id: str, user=Depends(get_current_user)):
    device_id = user["user_id"]
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


# ==================== AI Health Coach ====================
async def _build_memory_context(user_id: str) -> str:
    """Assemble a compact, personalized memory summary from the user's history."""
    cleanups = await db.cleanups.find({"device_id": user_id}).sort("completed_at", -1).to_list(1000)
    total_reclaimed = sum(d.get("reclaimed_mb", 0.0) for d in cleanups)
    total_cleanups = len(cleanups)

    # weekly streak
    weeks_with = set()
    last_cleanup_date = None
    for d in cleanups:
        try:
            dt = datetime.fromisoformat(d["completed_at"])
            iso = dt.isocalendar()
            weeks_with.add((iso[0], iso[1]))
            if last_cleanup_date is None:
                last_cleanup_date = dt
        except Exception:
            pass

    parts = [
        f"- Total cleanups performed: {total_cleanups}",
        f"- Lifetime space reclaimed: {total_reclaimed/1024:.2f} GB ({total_reclaimed:.0f} MB)",
        f"- Weeks with at least one cleanup: {len(weeks_with)}",
    ]
    if last_cleanup_date:
        days_ago = (datetime.now(timezone.utc) - last_cleanup_date.replace(tzinfo=timezone.utc)).days
        parts.append(f"- Last cleanup: {days_ago} day(s) ago")
        recent = cleanups[0]
        parts.append(f"- Most recent cleanup freed {recent.get('reclaimed_mb', 0):.0f} MB from {', '.join(recent.get('categories', [])) or 'junk'}")
    else:
        parts.append("- No cleanups yet — this is a great time to start a healthy routine.")
    return "\n".join(parts)


@api_router.get("/coach/daily", response_model=CoachDaily)
async def coach_daily(user=Depends(get_current_user)):
    user_id = user["user_id"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    cached = await db.coach_daily.find_one({"user_id": user_id, "date": today}, {"_id": 0})
    if cached:
        return CoachDaily(**{k: v for k, v in cached.items() if k not in ("user_id",)})

    name = (user.get("name") or "there").split(" ")[0]
    memory = await _build_memory_context(user_id)

    fallback = CoachDaily(
        date=today,
        greeting=f"Good to see you, {name} 👋",
        tip_title="Run today's Pulse check",
        tip_body="A quick Smart Scan keeps your device fast and clutter-free. Small daily habits prevent big slowdowns.",
        focus="general",
        action_label="Start Smart Scan",
        action_route="/smart-scan",
    )

    if not EMERGENT_LLM_KEY:
        doc = fallback.dict(); doc["user_id"] = user_id
        await db.coach_daily.insert_one(doc.copy())
        return fallback

    system_message = (
        "You are DevicePulse Coach, a warm, encouraging personal device-health assistant. "
        "Using the user's history, produce ONE short daily coaching card. "
        "Return ONLY valid JSON (no markdown/code fences) with keys: "
        '{"greeting": "friendly 3-6 word greeting using their first name", '
        '"tip_title": "punchy title max 6 words", '
        '"tip_body": "1-2 warm, specific sentences referencing their history when relevant", '
        '"focus": "one of storage|battery|security|photos|general", '
        '"action_label": "2-3 word button text", '
        '"action_route": "one of /smart-scan|/duplicates|/large-files|/junk|/insights"}. '
        "Be positive and celebrate progress."
    )
    prompt = f"User's first name: {name}\nUser history:\n{memory}\n\nGenerate today's coaching card as JSON."

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"coach-daily-{uuid.uuid4()}",
            system_message=system_message,
        ).with_model("anthropic", "claude-sonnet-5")
        response = await chat.send_message(UserMessage(text=prompt))
        import json, re
        text = response if isinstance(response, str) else str(response)
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
        match = re.search(r"\{[\s\S]*\}", text)
        data = json.loads(match.group(0))
        allowed_focus = {"storage", "battery", "security", "photos", "general"}
        allowed_routes = {"/smart-scan", "/duplicates", "/large-files", "/junk", "/insights"}
        card = CoachDaily(
            date=today,
            greeting=str(data.get("greeting") or fallback.greeting)[:80],
            tip_title=str(data.get("tip_title") or fallback.tip_title)[:60],
            tip_body=str(data.get("tip_body") or fallback.tip_body)[:280],
            focus=data.get("focus") if data.get("focus") in allowed_focus else "general",
            action_label=str(data.get("action_label") or fallback.action_label)[:24],
            action_route=data.get("action_route") if data.get("action_route") in allowed_routes else "/smart-scan",
        )
        doc = card.dict(); doc["user_id"] = user_id
        await db.coach_daily.insert_one(doc.copy())
        return card
    except Exception:
        logging.exception("Coach daily generation failed")
        doc = fallback.dict(); doc["user_id"] = user_id
        await db.coach_daily.insert_one(doc.copy())
        return fallback


@api_router.get("/coach/history", response_model=List[CoachMessage])
async def coach_history(user=Depends(get_current_user)):
    user_id = user["user_id"]
    docs = await db.coach_messages.find({"user_id": user_id}).sort("created_at", 1).to_list(200)
    return [CoachMessage(role=d["role"], content=d["content"], created_at=d["created_at"]) for d in docs]


@api_router.delete("/coach/history")
async def coach_clear(user=Depends(get_current_user)):
    await db.coach_messages.delete_many({"user_id": user["user_id"]})
    return {"cleared": True}


@api_router.post("/coach/chat", response_model=CoachMessage)
async def coach_chat(req: CoachChatRequest, request: Request, user=Depends(get_current_user)):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "LLM key not configured")

    client_key = user["user_id"]
    if not _allow_ai_call(client_key):
        raise HTTPException(429, "Too many messages. Please wait a moment and try again.")

    message = (req.message or "").strip()
    if not message:
        raise HTTPException(422, "Message cannot be empty")
    message = message[:1000]

    user_id = user["user_id"]
    now = datetime.now(timezone.utc).isoformat()

    # persist user message (memory)
    await db.coach_messages.insert_one({"user_id": user_id, "role": "user", "content": message, "created_at": now})

    memory = await _build_memory_context(user_id)
    recent = await db.coach_messages.find({"user_id": user_id}).sort("created_at", -1).to_list(12)
    recent = list(reversed(recent))
    convo = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in recent[:-1])  # exclude current

    live = []
    if req.health_score is not None:
        live.append(f"- Current health score: {req.health_score}/100")
    if req.storage_used_pct is not None:
        live.append(f"- Storage used: {req.storage_used_pct:.0f}%")
    if req.battery_health_pct is not None:
        live.append(f"- Battery health: {req.battery_health_pct}%")
    live_ctx = "\n".join(live) if live else "- (no live device stats provided)"

    system_message = (
        "You are DevicePulse Coach, a friendly, knowledgeable personal device-health assistant inside the DevicePulse app. "
        "You help users keep phones fast, clean, secure, and battery-healthy. "
        "You remember the user's history and reference it naturally to feel personal and continuous. "
        "Keep replies concise (2-4 sentences), warm, and actionable. Suggest concrete DevicePulse actions "
        "(Smart Scan, duplicate cleanup, junk cleanup, large-file finder, battery insights) when relevant. "
        "Never invent scary claims; the app simulates cleanup for safety. If asked about non-device topics, gently steer back.\n\n"
        f"USER MEMORY (their history):\n{memory}\n\n"
        f"LIVE DEVICE STATS:\n{live_ctx}\n\n"
        f"RECENT CONVERSATION:\n{convo if convo else '(this is the first message)'}"
    )

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"coach-{user_id}",
            system_message=system_message,
        ).with_model("anthropic", "claude-sonnet-5")
        response = await chat.send_message(UserMessage(text=message))
        reply = (response if isinstance(response, str) else str(response)).strip()
    except Exception:
        logging.exception("Coach chat failed")
        reply = "I'm having trouble thinking right now. Try a Smart Scan in the meantime, and ask me again in a moment."

    reply = reply[:1500]
    reply_at = datetime.now(timezone.utc).isoformat()
    await db.coach_messages.insert_one({"user_id": user_id, "role": "assistant", "content": reply, "created_at": reply_at})
    return CoachMessage(role="assistant", content=reply, created_at=reply_at)


# ---- Coach upgrade: a running assistant, not a one-time report ----
# Everything below is deterministic (no LLM calls) so it's fully unit-testable
# and cheap to compute on every screen visit: it turns the Coach from a single
# cached daily card into a small ongoing feed that (a) learns the user's real
# cleanup habits from their history and proposes a monthly plan around their
# top category, and (b) celebrates milestones the moment they're crossed,
# without re-celebrating the same win twice.

MB_PER_GB = 1024.0

# min_cleanups / min_gb / min_streak are mutually exclusive per entry — each
# win is anchored to exactly one signal so it stays simple to reason about.
WIN_DEFS = [
    {"key": "win_first_clean", "min_cleanups": 1, "title": "First cleanup done! 🎉",
     "body": "You ran your very first cleanup — a great habit to start."},
    {"key": "win_clean_5", "min_cleanups": 5, "title": "5 cleanups milestone",
     "body": "You've completed 5 cleanups. Keep the momentum going!"},
    {"key": "win_clean_10", "min_cleanups": 10, "title": "10 cleanups milestone",
     "body": "10 cleanups and counting — your device thanks you."},
    {"key": "win_clean_25", "min_cleanups": 25, "title": "25 cleanups milestone",
     "body": "25 cleanups! You've built a real routine."},
    {"key": "win_gb_1", "min_gb": 1, "title": "1 GB reclaimed",
     "body": "You've freed up over 1 GB of space in total. Nice work."},
    {"key": "win_gb_5", "min_gb": 5, "title": "5 GB reclaimed",
     "body": "5 GB reclaimed lifetime — that's thousands of photos worth of space."},
    {"key": "win_gb_10", "min_gb": 10, "title": "10 GB reclaimed",
     "body": "10 GB reclaimed. Outstanding cleanup streak."},
    {"key": "win_streak_2", "min_streak": 2, "title": "2-week streak",
     "body": "Two weeks running — you're building a great habit."},
    {"key": "win_streak_4", "min_streak": 4, "title": "4-week streak",
     "body": "A full month of consistent cleanups. Impressive."},
    {"key": "win_streak_8", "min_streak": 8, "title": "8-week streak",
     "body": "8 weeks straight — you're a DevicePulse power user."},
]
WIN_KEYS = {w["key"] for w in WIN_DEFS}

CATEGORY_PLAN = {
    "Junk files": "Junk builds up fast from browsing and everyday app use. This month, run a Smart Scan weekly so it never piles up.",
    "Duplicates": "You clean up duplicate photos more than anything else. This month, run the Duplicate cleanup after big photo days (trips, events) so it doesn't build up.",
    "Large files": "Large files are your biggest space-taker. This month, check the Large Files finder every couple of weeks — old videos and downloads are the usual culprits.",
    "App cache": "App cache is what you clear most often. This month, a quick cache clear every 1-2 weeks should keep things smooth without losing anything important.",
}
DEFAULT_PLAN = "Once you've run a few cleanups, I'll spot your top habit and build a monthly plan around it."


def _build_win_candidates(total_cleanups: int, total_reclaimed_mb: float, current_streak_weeks: int) -> list:
    gb = total_reclaimed_mb / MB_PER_GB
    candidates = []
    for w in WIN_DEFS:
        if "min_cleanups" in w and total_cleanups >= w["min_cleanups"]:
            candidates.append(w)
        elif "min_gb" in w and gb >= w["min_gb"]:
            candidates.append(w)
        elif "min_streak" in w and current_streak_weeks >= w["min_streak"]:
            candidates.append(w)
    return candidates


def _detect_top_category(cleanups: list) -> Optional[str]:
    """Return the user's most-cleaned category once there's enough history to
    call it a pattern (3+ cleanups); otherwise None. Ties break alphabetically
    so the result is deterministic and testable."""
    if len(cleanups) < 3:
        return None
    counts: dict = {}
    for d in cleanups:
        for cat in d.get("categories", []):
            counts[cat] = counts.get(cat, 0) + 1
    if not counts:
        return None
    top_count = max(counts.values())
    top = sorted([c for c, n in counts.items() if n == top_count])
    return top[0]


@api_router.get("/coach/insights", response_model=List[CoachInsight])
async def coach_insights(user=Depends(get_current_user)):
    user_id = user["user_id"]
    cleanups = await db.cleanups.find({"device_id": user_id}).to_list(1000)
    total_cleanups = len(cleanups)
    total_reclaimed_mb = sum(d.get("reclaimed_mb", 0.0) for d in cleanups)

    streak_data = await _compute_streak_data(user_id)
    current_streak_weeks = streak_data["current_streak_weeks"]

    seen = await db.coach_seen_wins.find({"user_id": user_id}).to_list(200)
    seen_keys = {s["key"] for s in seen}

    insights: List[CoachInsight] = []

    for w in _build_win_candidates(total_cleanups, total_reclaimed_mb, current_streak_weeks):
        if w["key"] in seen_keys:
            continue
        insights.append(CoachInsight(
            key=w["key"], kind="win", title=w["title"], body=w["body"], icon="trophy",
        ))

    top_category = _detect_top_category(cleanups)
    if top_category:
        plan = CATEGORY_PLAN.get(top_category, DEFAULT_PLAN)
        insights.append(CoachInsight(
            key=f"pattern_{top_category.lower().replace(' ', '_')}",
            kind="pattern",
            title=f"You clean up {top_category} the most",
            body=plan,
            icon="analytics",
            action_label="Open Smart Scan",
            action_route="/smart-scan",
        ))

    return insights


@api_router.post("/coach/insights/{key}/ack")
async def ack_coach_insight(key: str, user=Depends(get_current_user)):
    if key not in WIN_KEYS:
        raise HTTPException(status_code=400, detail="Unknown insight key")
    user_id = user["user_id"]
    await db.coach_seen_wins.update_one(
        {"user_id": user_id, "key": key},
        {"$set": {"seen_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"acknowledged": True, "key": key}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

@app.on_event("startup")
async def create_indexes():
    try:
        await db.users.create_index("email", unique=True)
        await db.users.create_index("user_id", unique=True)
        await db.user_sessions.create_index("session_token", unique=True)
        await db.user_sessions.create_index("user_id")
        await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)
    except Exception:
        logging.exception("Index creation failed")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    try:
        await _push_client.aclose()
    except Exception:
        pass
