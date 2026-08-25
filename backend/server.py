from fastapi import FastAPI, APIRouter, HTTPException, Request, Header, Depends
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
import uuid
import html
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

class DuplicateGroupOut(BaseModel):
    id: str
    photo_count: int
    size_mb: float
    thumbnail_url: str
    taken_at: str
    ai_label: str          # "Exact duplicate" | "Burst photo" | "Similar photo"
    ai_confidence: int     # 0-100

class DuplicateScanResult(BaseModel):
    new_groups_found: int
    groups: List[DuplicateGroupOut]

class DuplicateRemoveRequest(BaseModel):
    group_ids: List[str]

class DuplicateRemoveResult(BaseModel):
    removed_count: int
    freed_mb: float
    groups: List[DuplicateGroupOut]

class LargeFileOut(BaseModel):
    id: str
    name: str
    size_mb: float
    type: str  # video, photo, doc, app
    modified_at: str

class LargeFileScanResult(BaseModel):
    new_files_found: int
    files: List[LargeFileOut]

class LargeFileDeleteRequest(BaseModel):
    file_ids: List[str]

class LargeFileDeleteResult(BaseModel):
    deleted_count: int
    freed_mb: float
    files: List[LargeFileOut]

class BatteryStateOut(BaseModel):
    level: int
    health_pct: int
    cycle_count: int
    temperature_c: float
    charging: bool
    time_to_empty_hours: float
    drain_apps: List[dict]
    last_optimized_at: Optional[str] = None
    optimizations_run: int = 0

class BatteryOptimizeResult(BaseModel):
    apps_optimized: int
    level_gained: int
    state: BatteryStateOut

class SecurityFinding(BaseModel):
    id: str
    source: str             # "session" | "device"
    severity: str            # low, medium, high
    category: str             # session, permission, network, backup, app
    title: str
    description: str
    action: Optional[str] = None         # "revoke_session" | "resolve" | None
    session_sid: Optional[str] = None    # set when source == "session"

class SecurityScanOut(BaseModel):
    status: str  # safe, at_risk
    last_scan_iso: str
    apps_scanned: int
    permissions_reviewed: int
    findings: List[SecurityFinding]

class SecurityScanResult(BaseModel):
    new_findings_found: int
    scan: SecurityScanOut

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

class FamilyMemberSnapshot(BaseModel):
    user_id: str
    name: str
    is_owner: bool
    joined_at: str
    score: int
    status: str  # Excellent | Good | Needs Attention | Poor
    streak_weeks: int
    days_until_full: int

class FamilyGroup(BaseModel):
    id: str
    invite_code: str
    is_owner: bool
    members: List[FamilyMemberSnapshot]

class JoinFamilyRequest(BaseModel):
    invite_code: str

class CleanupReport(BaseModel):
    share_code: str
    generated_at: str
    display_name: str
    health_score: int
    status: str  # Excellent | Good | Needs Attention | Poor
    total_cleanups: int
    total_reclaimed_mb: float
    total_reclaimed_gb: float
    current_streak_weeks: int
    top_category: Optional[str] = None
    days_until_full: int

class EntitlementSync(BaseModel):
    is_pro: bool

class AutoCleanSchedule(BaseModel):
    enabled: bool = True
    frequency: str  # "daily" | "weekly"
    day_of_week: Optional[int] = None  # 0=Monday..6=Sunday; required when weekly
    categories: List[str]
    last_run_at: Optional[str] = None

class AutoCleanRunResult(BaseModel):
    ran: bool
    reason: Optional[str] = None
    reclaimed_mb: Optional[float] = None
    categories: Optional[List[str]] = None

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
    await db.cleanup_reports.delete_many({"user_id": uid})
    await db.autoclean_schedules.delete_many({"user_id": uid})
    await db.duplicate_groups.delete_many({"user_id": uid})
    await db.security_findings.delete_many({"user_id": uid})
    await db.security_scan_state.delete_many({"user_id": uid})
    await db.battery_state.delete_many({"user_id": uid})
    await db.large_files.delete_many({"user_id": uid})
    await _leave_family_group(uid)
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

# ---------- Family Dashboard: real linked accounts, not name labels ----------
# Each member is a genuine DevicePulse account that joined via an invite code
# — not a free-text name the owner typed in — so the owner's dashboard shows
# each member's actual live health score, streak, and storage forecast
# (pulled from that member's own real per-user data), and the owner can
# trigger a real one-tap remote cleanup on a member's account. A user belongs
# to at most one family group at a time, either as its owner or a member.
FAMILY_MAX_MEMBERS = 5


async def _generate_unique_invite_code() -> str:
    for _ in range(5):
        code = f"FAM-{uuid.uuid4().hex[:6].upper()}"
        if not await db.family_groups.find_one({"invite_code": code}):
            return code
    return f"FAM-{uuid.uuid4().hex[:8].upper()}"  # fallback; collision here is astronomically unlikely


async def _build_family_snapshot(group_id: str) -> list:
    memberships = await db.family_memberships.find({"group_id": group_id}).sort("joined_at", 1).to_list(FAMILY_MAX_MEMBERS)
    out = []
    for m in memberships:
        uid = m["user_id"]
        u = await db.users.find_one({"user_id": uid}, {"_id": 0})
        cleanups = await db.cleanups.find({"device_id": uid}).to_list(1000)
        score, _cleaned_last_24h = _compute_daily_pulse_score(cleanups)
        streak_data = await _compute_streak_data(uid)
        forecast = await _compute_forecast(uid)
        out.append(FamilyMemberSnapshot(
            user_id=uid,
            name=(u.get("name") if u else None) or "Unknown",
            is_owner=m["role"] == "owner",
            joined_at=m["joined_at"],
            score=score,
            status=_pulse_status_band(score),
            streak_weeks=streak_data["current_streak_weeks"],
            days_until_full=forecast["days_until_full"],
        ))
    return out


async def _leave_family_group(user_id: str) -> bool:
    """Removes user_id from their family group, if any. If they were the
    owner and other members remain, ownership transfers to the
    earliest-joined remaining member instead of orphaning the group; if they
    were the sole member, the group is deleted. Returns False if they weren't
    in a group. Shared by POST /family/leave and account deletion."""
    membership = await db.family_memberships.find_one({"user_id": user_id})
    if not membership:
        return False
    if membership["role"] == "owner":
        others = await db.family_memberships.find(
            {"group_id": membership["group_id"], "user_id": {"$ne": user_id}}
        ).sort("joined_at", 1).to_list(FAMILY_MAX_MEMBERS)
        if others:
            new_owner_id = others[0]["user_id"]
            await db.family_memberships.update_one({"user_id": new_owner_id}, {"$set": {"role": "owner"}})
            await db.family_groups.update_one({"id": membership["group_id"]}, {"$set": {"owner_id": new_owner_id}})
        else:
            await db.family_groups.delete_one({"id": membership["group_id"]})
    await db.family_memberships.delete_one({"user_id": user_id})
    return True


@api_router.get("/family/group", response_model=Optional[FamilyGroup])
async def get_family_group(user=Depends(get_current_user)):
    """Returns None if the user isn't in a family plan yet — deliberately NOT
    auto-created here. Auto-creating on a plain read would silently enroll
    every user in their own solo group, which would then block them from
    joining someone else's family without first "leaving" a group they never
    knew they had. POST /family/create is the explicit action instead."""
    user_id = user["user_id"]
    membership = await db.family_memberships.find_one({"user_id": user_id})
    if not membership:
        return None
    group = await db.family_groups.find_one({"id": membership["group_id"]}, {"_id": 0})
    members = await _build_family_snapshot(group["id"])
    return FamilyGroup(
        id=group["id"],
        invite_code=group["invite_code"],
        is_owner=membership["role"] == "owner",
        members=members,
    )


@api_router.post("/family/create", response_model=FamilyGroup)
async def create_family_group(user=Depends(get_current_user)):
    user_id = user["user_id"]
    if await db.family_memberships.find_one({"user_id": user_id}):
        raise HTTPException(400, "You're already in a family plan")
    group_id = str(uuid.uuid4())
    invite_code = await _generate_unique_invite_code()
    await db.family_groups.insert_one({
        "id": group_id,
        "owner_id": user_id,
        "invite_code": invite_code,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.family_memberships.insert_one({
        "user_id": user_id,
        "group_id": group_id,
        "role": "owner",
        "joined_at": datetime.now(timezone.utc).isoformat(),
    })
    members = await _build_family_snapshot(group_id)
    return FamilyGroup(id=group_id, invite_code=invite_code, is_owner=True, members=members)


@api_router.post("/family/join", response_model=FamilyGroup)
async def join_family(req: JoinFamilyRequest, user=Depends(get_current_user)):
    user_id = user["user_id"]
    existing = await db.family_memberships.find_one({"user_id": user_id})
    if existing:
        raise HTTPException(400, "Leave your current family plan before joining another")

    code = (req.invite_code or "").strip().upper()
    group = await db.family_groups.find_one({"invite_code": code})
    if not group:
        raise HTTPException(404, "Invite code not found")

    count = await db.family_memberships.count_documents({"group_id": group["id"]})
    if count >= FAMILY_MAX_MEMBERS:
        raise HTTPException(400, f"Family plan supports up to {FAMILY_MAX_MEMBERS} members")

    await db.family_memberships.insert_one({
        "user_id": user_id,
        "group_id": group["id"],
        "role": "member",
        "joined_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        first_name = (user.get("name") or "Someone").split(" ")[0]
        await send_push(
            recipients=[group["owner_id"]],
            data={"title": "Family plan updated", "message": f"{first_name} joined your family plan.", "action_url": "/family"},
            idempotency_key=f"family-join-{group['id']}-{user_id}",
        )
    except Exception as e:
        logging.warning(f"Family join push failed (non-blocking): {e}")

    members = await _build_family_snapshot(group["id"])
    return FamilyGroup(id=group["id"], invite_code=group["invite_code"], is_owner=False, members=members)


@api_router.post("/family/leave")
async def leave_family(user=Depends(get_current_user)):
    left = await _leave_family_group(user["user_id"])
    if not left:
        raise HTTPException(400, "You're not in a family plan")
    return {"left": True}


@api_router.post("/family/remote-clean/{member_user_id}")
async def family_remote_clean(member_user_id: str, user=Depends(get_current_user)):
    """The "remote management" action: the family plan owner runs an
    immediate simulated cleanup on a member's actual account (same
    reclaimable estimate Smart Nudges/Predictive Storage use), and the
    member gets a push notification about it."""
    user_id = user["user_id"]
    membership = await db.family_memberships.find_one({"user_id": user_id})
    if not membership or membership["role"] != "owner":
        raise HTTPException(403, "Only the family plan owner can trigger a remote cleanup")
    if member_user_id == user_id:
        raise HTTPException(400, "Use Smart Scan on your own device instead")
    target = await db.family_memberships.find_one({"user_id": member_user_id, "group_id": membership["group_id"]})
    if not target:
        raise HTTPException(404, "That member isn't part of your family plan")

    cleanups = await db.cleanups.find({"device_id": member_user_id}).to_list(1000)
    reclaimed_mb = _estimate_reclaimable_mb(cleanups)
    await db.cleanups.insert_one({
        "id": str(uuid.uuid4()),
        "device_id": member_user_id,
        "categories": ["Remote family cleanup"],
        "reclaimed_mb": reclaimed_mb,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        await send_push(
            recipients=[member_user_id],
            data={
                "title": "Your family admin helped out",
                "message": f"Freed {round(reclaimed_mb / 1024, 1)} GB on your device remotely.",
                "action_url": "/(tabs)",
            },
            idempotency_key=f"family-remote-clean-{member_user_id}-{uuid.uuid4().hex[:8]}",
        )
    except Exception as e:
        logging.warning(f"Family remote-clean push failed (non-blocking): {e}")

    members = await _build_family_snapshot(membership["group_id"])
    updated = next((m for m in members if m.user_id == member_user_id), None)
    return {"reclaimed_mb": reclaimed_mb, "member": updated}


# ==================== Shareable Cleanup Report ====================
# A point-in-time recap of real account history that the user can share
# publicly. Unlike everything else in this file, GET /reports/{share_code}
# is intentionally NOT behind auth — the whole point of "shareable" is that
# someone without the app, and without an account, can open the link and see
# it. Each POST /reports/generate call snapshots real data (same helpers the
# rest of the app uses: streaks, forecast, top category, pulse score) and
# freezes it under a fresh share code; regenerating never mutates a report
# already shared under an older code, so a link someone was sent keeps
# showing what was true when it was shared, not a live-updating view.
#
# Mirrors the Family Dashboard's nullable-GET / explicit-POST-create design
# for the same reason: auto-creating a report on first read would be a
# surprising side effect of just opening the screen.

async def _generate_unique_report_code() -> str:
    for _ in range(5):
        code = f"CR-{uuid.uuid4().hex[:6].upper()}"
        if not await db.cleanup_reports.find_one({"share_code": code}):
            return code
    return f"CR-{uuid.uuid4().hex[:8].upper()}"


async def _build_cleanup_report(user: dict) -> dict:
    user_id = user["user_id"]
    cleanups = await db.cleanups.find({"device_id": user_id}).to_list(1000)
    total_reclaimed_mb = sum(d.get("reclaimed_mb", 0.0) for d in cleanups)
    score, _cleaned_last_24h = _compute_daily_pulse_score(cleanups)
    streak_data = await _compute_streak_data(user_id)
    forecast = await _compute_forecast(user_id)
    first_name = (user.get("name") or "A DevicePulse user").strip().split(" ")[0] or "A DevicePulse user"
    return {
        "id": str(uuid.uuid4()),
        "share_code": await _generate_unique_report_code(),
        "user_id": user_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "display_name": first_name,
        "health_score": score,
        "status": _pulse_status_band(score),
        "total_cleanups": len(cleanups),
        "total_reclaimed_mb": round(total_reclaimed_mb, 1),
        "total_reclaimed_gb": round(total_reclaimed_mb / 1024, 2),
        "current_streak_weeks": streak_data["current_streak_weeks"],
        "top_category": _detect_top_category(cleanups),
        "days_until_full": forecast["days_until_full"],
    }


def _report_public_view(doc: dict) -> CleanupReport:
    """Only ever returns the frozen, non-identifying snapshot fields — never
    user_id or email, since this same shape is served on the public route."""
    return CleanupReport(
        share_code=doc["share_code"],
        generated_at=doc["generated_at"],
        display_name=doc["display_name"],
        health_score=doc["health_score"],
        status=doc["status"],
        total_cleanups=doc["total_cleanups"],
        total_reclaimed_mb=doc["total_reclaimed_mb"],
        total_reclaimed_gb=doc["total_reclaimed_gb"],
        current_streak_weeks=doc["current_streak_weeks"],
        top_category=doc.get("top_category"),
        days_until_full=doc["days_until_full"],
    )


@api_router.get("/reports/mine", response_model=Optional[CleanupReport])
async def get_my_latest_report(user=Depends(get_current_user)):
    docs = await db.cleanup_reports.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("generated_at", -1).to_list(1)
    if not docs:
        return None
    return _report_public_view(docs[0])


@api_router.post("/reports/generate", response_model=CleanupReport)
async def generate_cleanup_report(user=Depends(get_current_user)):
    doc = await _build_cleanup_report(user)
    await db.cleanup_reports.insert_one(doc.copy())
    return _report_public_view(doc)


@api_router.get("/reports/{share_code}", response_model=CleanupReport)
async def get_public_report(share_code: str):
    """Public, unauthenticated by design — see module note above. Returns the
    JSON snapshot; the app uses this. A human opening the shared link in a
    plain browser instead lands on GET /r/{share_code} (below), which renders
    the same data as an actual page instead of raw JSON."""
    doc = await db.cleanup_reports.find_one(
        {"share_code": share_code.strip().upper()}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "Report not found")
    return _report_public_view(doc)


_REPORT_STAT = """
  <div class="stat">
    <div class="stat-value">{value}</div>
    <div class="stat-label">{label}</div>
  </div>
"""

_REPORT_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta name="description" content="{description}">
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
    padding: 32px 16px; background: linear-gradient(160deg, #050F14, #0B1B24);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }}
  .card {{
    width: 100%; max-width: 420px; border-radius: 24px; padding: 36px 28px;
    background: linear-gradient(135deg, #064E3B, #059669, #10B981);
    box-shadow: 0 20px 60px rgba(0,0,0,0.45); text-align: center;
  }}
  .badge {{
    width: 64px; height: 64px; border-radius: 32px; margin: 0 auto 18px;
    background: rgba(2,44,34,0.25); display: flex; align-items: center; justify-content: center;
    font-size: 30px;
  }}
  h1 {{ color: #022C22; font-size: 24px; font-weight: 800; margin: 0 0 4px; }}
  .sub {{ color: rgba(2,44,34,0.85); font-size: 14px; margin: 0 0 20px; }}
  .headline {{ color: #022C22; font-size: 42px; font-weight: 800; letter-spacing: -1px; margin: 0; }}
  .headline-label {{ color: rgba(2,44,34,0.75); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }}
  .stats {{
    margin-top: 24px; display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
    background: rgba(2,44,34,0.14); border-radius: 16px; padding: 18px;
  }}
  .stat-value {{ color: #022C22; font-size: 20px; font-weight: 800; }}
  .stat-label {{ color: rgba(2,44,34,0.7); font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; margin-top: 2px; }}
  .stamp {{ margin-top: 26px; color: rgba(2,44,34,0.8); font-size: 13px; font-weight: 700; }}
</style>
</head>
<body>
  <div class="card">
    <div class="badge">✅</div>
    <h1>{display_name}'s Cleanup Report</h1>
    <p class="sub">Generated with DevicePulse</p>
    <div class="headline-label">Total storage freed</div>
    <p class="headline">{total_gb} GB</p>
    <div class="stats">
      {stats}
    </div>
    <p class="stamp">⚡ DevicePulse</p>
  </div>
</body>
</html>
"""

_REPORT_NOT_FOUND_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Report not found</title>
<style>
  body {{
    margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
    background: #050F14; color: #F0FDFA; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    text-align: center; padding: 32px;
  }}
</style>
</head>
<body>
  <div>
    <h1>Report not found</h1>
    <p>This DevicePulse cleanup report link is invalid or no longer available.</p>
  </div>
</body>
</html>
"""


@app.get("/r/{share_code}", response_class=HTMLResponse)
async def view_public_report_page(share_code: str):
    """The human-facing counterpart to GET /api/reports/{share_code}: opening
    a shared link in a plain browser renders an actual page instead of raw
    JSON. Lives outside the /api prefix since it's a page, not an API call."""
    doc = await db.cleanup_reports.find_one(
        {"share_code": share_code.strip().upper()}, {"_id": 0}
    )
    if not doc:
        return HTMLResponse(content=_REPORT_NOT_FOUND_PAGE, status_code=404)

    name = html.escape(doc["display_name"])
    stats = []
    stats.append(_REPORT_STAT.format(value=doc["total_cleanups"], label="Cleanups"))
    stats.append(_REPORT_STAT.format(value=f'{doc["current_streak_weeks"]}wk', label="Streak"))
    stats.append(_REPORT_STAT.format(value=f'{doc["health_score"]}/100', label=html.escape(doc["status"])))
    if doc.get("top_category"):
        stats.append(_REPORT_STAT.format(value=html.escape(doc["top_category"]), label="Top category"))
    else:
        stats.append(_REPORT_STAT.format(value=f'{doc["days_until_full"]}d', label="Until storage full"))

    description = (
        f"{name} freed {doc['total_reclaimed_gb']} GB across {doc['total_cleanups']} cleanups "
        f"with DevicePulse."
    )
    page = _REPORT_PAGE.format(
        title=f"{name}'s DevicePulse Cleanup Report",
        description=html.escape(description),
        display_name=name,
        total_gb=doc["total_reclaimed_gb"],
        stats="".join(stats),
    )
    return HTMLResponse(content=page)


# ==================== Entitlements (Pro) ====================
# This sandbox has no RevenueCat secret key or webhook receiver configured,
# so the backend cannot independently verify a purchase against RevenueCat's
# own servers. Given that limit (per explicit user choice — see project
# notes), this stores a real, persisted, server-enforced `is_pro` flag on the
# user record instead of trusting a value passed on each individual request:
# the client (which holds a genuine RevenueCat subscription result) reports
# it once via POST /entitlements/sync, and every Pro-gated endpoint below
# checks this STORED flag. A production build would close the remaining gap
# with a RevenueCat webhook that updates this same flag from RevenueCat's own
# servers instead of the client self-reporting it.

@api_router.get("/entitlements/me")
async def get_my_entitlement(user=Depends(get_current_user)):
    return {"is_pro": bool(user.get("is_pro", False))}

@api_router.post("/entitlements/sync")
async def sync_entitlement(body: EntitlementSync, user=Depends(get_current_user)):
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"is_pro": body.is_pro}})
    return {"is_pro": body.is_pro}


# ==================== Auto-Clean Scheduling (Pro-only) ====================
AUTOCLEAN_ALLOWED_CATEGORIES = ["Junk files", "Duplicates", "App cache"]
# "Large files" is deliberately excluded from what auto-clean is allowed to
# touch — it's the one category likely to contain something a user actually
# wants to keep (a big saved video, a download), so removing it without a
# look first is too aggressive for something that runs with no user present.
AUTOCLEAN_DAILY_COOLDOWN_HOURS = 20
AUTOCLEAN_WEEKLY_COOLDOWN = timedelta(days=6, hours=12)


def _validate_autoclean_schedule(body: "AutoCleanSchedule"):
    if body.frequency not in ("daily", "weekly"):
        raise HTTPException(400, "frequency must be 'daily' or 'weekly'")
    if body.frequency == "weekly":
        if body.day_of_week is None or not (0 <= body.day_of_week <= 6):
            raise HTTPException(400, "day_of_week (0=Monday..6=Sunday) is required for a weekly schedule")
    if not body.categories:
        raise HTTPException(400, "Choose at least one category to auto-clean")
    bad = [c for c in body.categories if c not in AUTOCLEAN_ALLOWED_CATEGORIES]
    if bad:
        raise HTTPException(400, f"Unsupported categories for auto-clean: {bad}. Allowed: {AUTOCLEAN_ALLOWED_CATEGORIES}")


@api_router.get("/autoclean/schedule", response_model=Optional[AutoCleanSchedule])
async def get_autoclean_schedule(user=Depends(get_current_user)):
    """Nullable by design, same reasoning as GET /family/group and
    GET /reports/mine: never silently create a schedule on a plain read."""
    doc = await db.autoclean_schedules.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        return None
    return AutoCleanSchedule(
        enabled=doc.get("enabled", True),
        frequency=doc["frequency"],
        day_of_week=doc.get("day_of_week"),
        categories=doc.get("categories", []),
        last_run_at=doc.get("last_run_at"),
    )


@api_router.put("/autoclean/schedule", response_model=AutoCleanSchedule)
async def save_autoclean_schedule(body: AutoCleanSchedule, user=Depends(get_current_user)):
    """Upsert (mirrors PUT /reminders) — Pro-gated using the STORED
    entitlement flag, never a value the caller supplies."""
    if not user.get("is_pro", False):
        raise HTTPException(403, "Auto-Clean Scheduling is a Pro feature")
    _validate_autoclean_schedule(body)
    user_id = user["user_id"]
    existing = await db.autoclean_schedules.find_one({"user_id": user_id})
    last_run_at = existing.get("last_run_at") if existing else None
    doc = {
        "user_id": user_id,
        "enabled": body.enabled,
        "frequency": body.frequency,
        "day_of_week": body.day_of_week if body.frequency == "weekly" else None,
        "categories": body.categories,
        "last_run_at": last_run_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.autoclean_schedules.update_one({"user_id": user_id}, {"$set": doc}, upsert=True)
    return AutoCleanSchedule(
        enabled=doc["enabled"], frequency=doc["frequency"], day_of_week=doc["day_of_week"],
        categories=doc["categories"], last_run_at=doc["last_run_at"],
    )


@api_router.delete("/autoclean/schedule")
async def delete_autoclean_schedule(user=Depends(get_current_user)):
    """Deleting/turning off a schedule is never Pro-gated — a lapsed
    subscriber must still be able to remove their own configuration."""
    res = await db.autoclean_schedules.delete_one({"user_id": user["user_id"]})
    return {"deleted": res.deleted_count > 0}


def _autoclean_is_due(schedule: dict, now: datetime) -> bool:
    last_run_at = schedule.get("last_run_at")
    last_run_dt = None
    if last_run_at:
        try:
            last_run_dt = datetime.fromisoformat(last_run_at)
            if last_run_dt.tzinfo is None:
                last_run_dt = last_run_dt.replace(tzinfo=timezone.utc)
        except Exception:
            last_run_dt = None

    if schedule["frequency"] == "daily":
        return last_run_dt is None or (now - last_run_dt) >= timedelta(hours=AUTOCLEAN_DAILY_COOLDOWN_HOURS)

    # weekly: only fires on the chosen weekday, and not sooner than ~once a week
    if now.weekday() != schedule.get("day_of_week"):
        return False
    return last_run_dt is None or (now - last_run_dt) >= AUTOCLEAN_WEEKLY_COOLDOWN


@api_router.post("/autoclean/run-if-due", response_model=AutoCleanRunResult)
async def run_autoclean_if_due(user=Depends(get_current_user)):
    """The 'lazy cron' pattern used throughout this app (Daily Pulse Check,
    Coach Insights, Nudges): there's no real background scheduler in this
    sandbox, so 'due' is checked and acted on whenever the client calls this
    (e.g. once on app open) — the same way every other 'scheduled' thing
    here actually works under the hood."""
    user_id = user["user_id"]
    schedule = await db.autoclean_schedules.find_one({"user_id": user_id})
    if not schedule:
        return AutoCleanRunResult(ran=False, reason="no_schedule")
    if not schedule.get("enabled", True):
        return AutoCleanRunResult(ran=False, reason="disabled")
    if not user.get("is_pro", False):
        # The schedule itself is left alone (not deleted) so it resumes
        # exactly as configured if the user re-subscribes.
        return AutoCleanRunResult(ran=False, reason="not_pro")

    now = datetime.now(timezone.utc)
    if not _autoclean_is_due(schedule, now):
        return AutoCleanRunResult(ran=False, reason="not_due")

    cleanups = await db.cleanups.find({"device_id": user_id}).to_list(1000)
    reclaimed_mb = _estimate_reclaimable_mb(cleanups)
    categories = schedule["categories"]
    await db.cleanups.insert_one({
        "id": str(uuid.uuid4()),
        "device_id": user_id,
        "categories": categories,
        "reclaimed_mb": reclaimed_mb,
        "completed_at": now.isoformat(),
    })
    await db.autoclean_schedules.update_one(
        {"user_id": user_id}, {"$set": {"last_run_at": now.isoformat()}}
    )
    try:
        await send_push(
            recipients=[user_id],
            data={
                "title": "Auto-Clean ran for you",
                "message": f"Freed {round(reclaimed_mb / 1024, 1)} GB automatically — no tap needed.",
                "action_url": "/(tabs)",
            },
            idempotency_key=f"autoclean-{user_id}-{now.date().isoformat()}",
        )
    except Exception as e:
        logging.warning(f"Auto-clean push failed (non-blocking): {e}")

    return AutoCleanRunResult(ran=True, reclaimed_mb=reclaimed_mb, categories=categories)


# ==================== Duplicate Photo AI ====================
# The old GET /device/duplicates was unauthenticated and returned a fresh
# random batch of fake groups on every single call (random count/size, fixed
# stock photo URLs) — nothing was per-user, nothing persisted, and the old
# "Remove" button in the app never called the backend at all. This section
# replaces it with real per-user, persisted duplicate groups: an "AI" label +
# confidence score per group (deterministic classification, not an LLM call —
# consistent with every other "AI" feature in this app, e.g. Smart Nudges and
# Predictive Storage), and removing a group actually deletes it from the
# user's pending list and records a real cleanup that feeds streak/forecast/
# cleanup-report/coach-insights exactly like any other cleanup action.
DUPLICATE_THUMBS = [
    "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=400",
    "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=400",
    "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=400",
    "https://images.unsplash.com/photo-1519681393784-d120267933ba?w=400",
    "https://images.unsplash.com/photo-1501785888041-af3ef285b470?w=400",
    "https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=400",
]
DUPLICATE_LABELS = ["Exact duplicate", "Burst photo", "Similar photo"]
DUPLICATE_LABEL_WEIGHTS = [0.5, 0.3, 0.2]
DUPLICATE_CONFIDENCE_RANGES = {
    "Exact duplicate": (94, 99),
    "Burst photo": (78, 92),
    "Similar photo": (62, 80),
}
# "Unlimited duplicate cleanup" is a Pro perk paywall.tsx has advertised since
# before this session, with nothing backing it — the same shape of gap Auto-
# Clean Scheduling closed for "Scheduled cleanups." Free users can remove a
# capped number of duplicate groups per UTC day; Pro users (checked via the
# same stored is_pro flag) are unlimited.
FREE_DUPLICATE_REMOVE_DAILY_LIMIT = 3


def _make_duplicate_group(user_id: str) -> dict:
    label = random.choices(DUPLICATE_LABELS, weights=DUPLICATE_LABEL_WEIGHTS, k=1)[0]
    lo, hi = DUPLICATE_CONFIDENCE_RANGES[label]
    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "photo_count": random.randint(2, 6),
        "size_mb": round(random.uniform(4.5, 48.0), 1),
        "thumbnail_url": random.choice(DUPLICATE_THUMBS),
        "taken_at": f"2025-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        "ai_label": label,
        "ai_confidence": random.randint(lo, hi),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "removed_at": None,
    }


def _duplicate_group_out(d: dict) -> DuplicateGroupOut:
    return DuplicateGroupOut(
        id=d["id"], photo_count=d["photo_count"], size_mb=d["size_mb"],
        thumbnail_url=d["thumbnail_url"], taken_at=d["taken_at"],
        ai_label=d["ai_label"], ai_confidence=d["ai_confidence"],
    )


@api_router.get("/device/duplicates", response_model=List[DuplicateGroupOut])
async def get_duplicate_groups(user=Depends(get_current_user)):
    """Generates a user's initial AI-scanned duplicate groups once, lazily,
    on first read, and persists them — so unlike the old endpoint, revisiting
    this screen shows the same groups instead of a freshly-randomized set."""
    uid = user["user_id"]
    existing = await db.duplicate_groups.count_documents({"user_id": uid})
    if existing == 0:
        initial = [_make_duplicate_group(uid) for _ in range(random.randint(5, 7))]
        await db.duplicate_groups.insert_many([g.copy() for g in initial])
    docs = await db.duplicate_groups.find({"user_id": uid, "status": "pending"}).sort("size_mb", -1).to_list(200)
    return [_duplicate_group_out(d) for d in docs]


@api_router.post("/device/duplicates/scan", response_model=DuplicateScanResult)
async def scan_duplicate_groups(user=Depends(get_current_user)):
    """Runs another AI scan, simulating newly-taken duplicate/burst photos
    found since the last scan — appends to (never replaces) the pending list."""
    uid = user["user_id"]
    new_groups = [_make_duplicate_group(uid) for _ in range(random.randint(1, 3))]
    await db.duplicate_groups.insert_many([g.copy() for g in new_groups])
    docs = await db.duplicate_groups.find({"user_id": uid, "status": "pending"}).sort("size_mb", -1).to_list(200)
    return DuplicateScanResult(new_groups_found=len(new_groups), groups=[_duplicate_group_out(d) for d in docs])


@api_router.post("/device/duplicates/remove", response_model=DuplicateRemoveResult)
async def remove_duplicate_groups(req: DuplicateRemoveRequest, user=Depends(get_current_user)):
    uid = user["user_id"]
    if not req.group_ids:
        raise HTTPException(400, "group_ids is required")

    docs = await db.duplicate_groups.find({
        "id": {"$in": req.group_ids}, "user_id": uid, "status": "pending",
    }).to_list(len(req.group_ids))
    found_ids = {d["id"] for d in docs}
    missing = [gid for gid in req.group_ids if gid not in found_ids]
    if missing:
        raise HTTPException(404, f"Unknown or already-removed group id(s): {', '.join(missing)}")

    if not user.get("is_pro", False):
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        removed_docs = await db.duplicate_groups.find({"user_id": uid, "status": "removed"}).to_list(1000)
        removed_today = 0
        for d in removed_docs:
            try:
                dt = datetime.fromisoformat(d["removed_at"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= today_start:
                    removed_today += 1
            except Exception:
                continue
        if removed_today + len(docs) > FREE_DUPLICATE_REMOVE_DAILY_LIMIT:
            raise HTTPException(
                403,
                f"Free plan allows removing {FREE_DUPLICATE_REMOVE_DAILY_LIMIT} duplicate groups per day. "
                f"Upgrade to Pro for unlimited duplicate cleanup.",
            )

    now_iso = datetime.now(timezone.utc).isoformat()
    freed_mb = round(sum(d["size_mb"] for d in docs), 1)
    await db.duplicate_groups.update_many(
        {"id": {"$in": list(found_ids)}, "user_id": uid},
        {"$set": {"status": "removed", "removed_at": now_iso}},
    )
    if freed_mb > 0:
        await db.cleanups.insert_one({
            "id": str(uuid.uuid4()),
            "device_id": uid,
            "categories": ["Duplicates"],
            "reclaimed_mb": freed_mb,
            "completed_at": now_iso,
        })
    remaining = await db.duplicate_groups.find({"user_id": uid, "status": "pending"}).sort("size_mb", -1).to_list(200)
    return DuplicateRemoveResult(
        removed_count=len(docs), freed_mb=freed_mb, groups=[_duplicate_group_out(d) for d in remaining],
    )


# ==================== Security (real account signals) ====================
# The old GET /device/security was unauthenticated, took no user, and always
# returned the exact same single hardcoded finding with status hardcoded to
# "safe" regardless — nothing was per-user, nothing was actionable, and the
# status text didn't even agree with the one threat being shown.
#
# Scoped explicitly via AskUserQuestion to real account signals only (no
# external breach-check service, to avoid sending user emails to a third
# party): this app already has genuine per-user session data (db.user_sessions,
# already exposed read-only via GET /auth/sessions) that's a real security
# signal never surfaced as one. Every OTHER concurrent sign-in is now a real,
# actionable finding — computed live from that real data, never persisted,
# so it's always exactly current — with a one-tap revoke wired straight to
# the existing POST /auth/sessions/{sid}/revoke. Device-level findings
# (permissions, backups, network, app hygiene) stay simulated, same honest
# framing as the rest of this app's device layer, but — like Duplicate Photo
# AI before it — are now persisted per user and dismissible instead of a
# single fact fabricated fresh on every call.
SECURITY_FINDING_POOL = [
    {"key": "excessive_permissions", "category": "permission", "severity": "low",
     "title": "Excessive permissions detected",
     "description": "2 apps have access to your location while running in background."},
    {"key": "camera_background", "category": "permission", "severity": "medium",
     "title": "Camera access outside app use",
     "description": "1 app can access your camera even when it isn't open."},
    {"key": "unencrypted_backup", "category": "backup", "severity": "medium",
     "title": "Unencrypted local backup found",
     "description": "A local backup isn't encrypted — anyone with file access could read it."},
    {"key": "outdated_app", "category": "app", "severity": "low",
     "title": "Outdated app version detected",
     "description": "1 installed app hasn't been updated in over 6 months and may carry known vulnerabilities."},
    {"key": "open_wifi", "category": "network", "severity": "high",
     "title": "Unsecured Wi-Fi network used recently",
     "description": "Your device recently connected to an open network with no encryption."},
]
SECURITY_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _pick_new_security_findings(existing_open_keys: set, max_new: int) -> list:
    """A previously-resolved finding is allowed to reappear on a later scan
    (a real scanner can flag the same category of issue again) — only
    currently-OPEN keys are excluded from the candidate pool."""
    candidates = [f for f in SECURITY_FINDING_POOL if f["key"] not in existing_open_keys]
    if not candidates or max_new <= 0:
        return []
    random.shuffle(candidates)
    n = random.randint(0, min(max_new, len(candidates)))
    return candidates[:n]


async def _real_session_findings(user_id: str, current_token: str) -> list:
    """Every OTHER active session is a real, verifiable, actionable security
    signal — computed live from db.user_sessions (never persisted, so it's
    always exactly current; naturally disappears once revoked)."""
    docs = await db.user_sessions.find({"user_id": user_id}).sort("created_at", -1).to_list(50)
    other_sessions = [d for d in docs if d.get("session_token") != current_token and d.get("sid")]
    if not other_sessions:
        return []
    severity = "medium" if len(docs) >= 4 else "low"
    findings = []
    for d in other_sessions:
        created = d.get("created_at")
        created_iso = created.isoformat() if isinstance(created, datetime) else str(created)
        findings.append({
            "id": f"session-{d['sid']}",
            "source": "session",
            "severity": severity,
            "category": "session",
            "title": "Active sign-in on another device",
            "description": f"Signed in since {created_iso[:10]}. If this wasn't you, revoke it now.",
            "action": "revoke_session",
            "session_sid": d["sid"],
        })
    return findings


def _security_status(findings: list) -> str:
    return "at_risk" if any(f["severity"] in ("medium", "high") for f in findings) else "safe"


def _security_finding_out(f: dict) -> SecurityFinding:
    return SecurityFinding(
        id=f["id"], source=f["source"], severity=f["severity"], category=f["category"],
        title=f["title"], description=f["description"],
        action=f.get("action"), session_sid=f.get("session_sid"),
    )


async def _build_security_scan(user_id: str, current_token: str) -> SecurityScanOut:
    device_docs = await db.security_findings.find({"user_id": user_id, "status": "open"}).to_list(50)
    device_findings = [
        {"id": d["id"], "source": "device", "severity": d["severity"], "category": d["category"],
         "title": d["title"], "description": d["description"], "action": "resolve"}
        for d in device_docs
    ]
    session_findings = await _real_session_findings(user_id, current_token)
    all_findings = session_findings + device_findings
    all_findings.sort(key=lambda f: SECURITY_SEVERITY_ORDER.get(f["severity"], 3))

    state = await db.security_scan_state.find_one({"user_id": user_id}, {"_id": 0})
    return SecurityScanOut(
        status=_security_status(all_findings),
        last_scan_iso=(state or {}).get("last_scan_at", datetime.now(timezone.utc).isoformat()),
        apps_scanned=(state or {}).get("apps_scanned", 0),
        permissions_reviewed=(state or {}).get("permissions_reviewed", 0),
        findings=[_security_finding_out(f) for f in all_findings],
    )


@api_router.get("/device/security", response_model=SecurityScanOut)
async def get_security(user=Depends(get_current_user), authorization: Optional[str] = Header(default=None)):
    uid = user["user_id"]
    cur_token = authorization.split(" ", 1)[1].strip() if authorization and authorization.startswith("Bearer ") else ""

    state = await db.security_scan_state.find_one({"user_id": uid})
    if not state:
        initial = _pick_new_security_findings(set(), max_new=2)
        now_iso = datetime.now(timezone.utc).isoformat()
        if initial:
            docs = [{
                "id": str(uuid.uuid4()), "user_id": uid, "key": f["key"], "category": f["category"],
                "severity": f["severity"], "title": f["title"], "description": f["description"],
                "status": "open", "created_at": now_iso, "resolved_at": None,
            } for f in initial]
            await db.security_findings.insert_many([d.copy() for d in docs])
        await db.security_scan_state.update_one(
            {"user_id": uid},
            {"$set": {
                "apps_scanned": random.randint(80, 220),
                "permissions_reviewed": random.randint(200, 450),
                "last_scan_at": now_iso,
            }},
            upsert=True,
        )

    return await _build_security_scan(uid, cur_token)


@api_router.post("/device/security/scan", response_model=SecurityScanResult)
async def scan_security(user=Depends(get_current_user), authorization: Optional[str] = Header(default=None)):
    uid = user["user_id"]
    cur_token = authorization.split(" ", 1)[1].strip() if authorization and authorization.startswith("Bearer ") else ""

    existing_open = await db.security_findings.find({"user_id": uid, "status": "open"}).to_list(50)
    existing_open_keys = {d["key"] for d in existing_open}
    new_findings = _pick_new_security_findings(existing_open_keys, max_new=1)
    now_iso = datetime.now(timezone.utc).isoformat()
    if new_findings:
        docs = [{
            "id": str(uuid.uuid4()), "user_id": uid, "key": f["key"], "category": f["category"],
            "severity": f["severity"], "title": f["title"], "description": f["description"],
            "status": "open", "created_at": now_iso, "resolved_at": None,
        } for f in new_findings]
        await db.security_findings.insert_many([d.copy() for d in docs])

    await db.security_scan_state.update_one(
        {"user_id": uid}, {"$set": {"last_scan_at": now_iso}}, upsert=True,
    )
    scan = await _build_security_scan(uid, cur_token)
    return SecurityScanResult(new_findings_found=len(new_findings), scan=scan)


@api_router.post("/device/security/findings/{finding_id}/resolve")
async def resolve_security_finding(finding_id: str, user=Depends(get_current_user)):
    """Only device-level findings live in this collection — a session
    finding's id is derived (\"session-{sid}\") and is resolved by revoking
    the session itself via POST /auth/sessions/{sid}/revoke, not this route."""
    res = await db.security_findings.update_one(
        {"id": finding_id, "user_id": user["user_id"], "status": "open"},
        {"$set": {"status": "resolved", "resolved_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Unknown or already-resolved finding id")
    return {"resolved": True}


# ==================== Battery Health & Optimizer ====================
# The old GET /device/battery was unauthenticated and returned the exact same
# hardcoded fixture on every call (level=54, health=87%, the same five drain
# apps at the same percentages) — nothing was per-user or persisted, and
# there was no optimize action anywhere despite paywall.tsx advertising
# "Battery optimizer" as a Pro perk (the same shape of gap Auto-Clean
# Scheduling closed for "Scheduled cleanups"). This section replaces it with
# a real per-user, persisted battery state and a genuine, Pro-gated
# POST /device/battery/optimize action.
#
# Deliberately honest scope: optimizing restricts background activity for
# the highest-drain apps (removing them from the drain list and recovering
# some of their battery cost as level/estimated-time-to-empty), which is a
# real thing a battery optimizer does — but it does NOT touch health_pct or
# cycle_count, since no software action changes actual battery hardware
# wear. Faking a hardware-health improvement would be a dishonest claim.
DRAIN_APP_POOL = [
    {"name": "Instagram", "icon": "📷"},
    {"name": "YouTube", "icon": "▶️"},
    {"name": "Chrome", "icon": "🌐"},
    {"name": "Spotify", "icon": "🎵"},
    {"name": "WhatsApp", "icon": "💬"},
    {"name": "TikTok", "icon": "🎬"},
    {"name": "Maps", "icon": "🗺️"},
    {"name": "Gmail", "icon": "✉️"},
]
BATTERY_OPTIMIZE_MAX_APPS = 2


async def _get_or_init_battery_state(uid: str) -> dict:
    doc = await db.battery_state.find_one({"user_id": uid})
    if doc:
        return doc
    chosen = random.sample(DRAIN_APP_POOL, k=random.randint(4, 6))
    drain_apps = [
        {**app, "pct": pct}
        for app, pct in zip(chosen, sorted((random.randint(4, 26) for _ in chosen), reverse=True))
    ]
    doc = {
        "user_id": uid,
        "level": random.randint(28, 62),
        "health_pct": random.randint(78, 96),
        "cycle_count": random.randint(150, 650),
        "temperature_c": round(random.uniform(29.0, 36.0), 1),
        "charging": False,
        "baseline_full_hours": round(random.uniform(10.0, 16.0), 1),
        "drain_apps": drain_apps,
        "last_optimized_at": None,
        "optimizations_run": 0,
    }
    await db.battery_state.update_one({"user_id": uid}, {"$set": doc}, upsert=True)
    return doc


def _battery_state_out(doc: dict) -> BatteryStateOut:
    time_to_empty = round((doc["level"] / 100.0) * doc["baseline_full_hours"], 1)
    return BatteryStateOut(
        level=doc["level"], health_pct=doc["health_pct"], cycle_count=doc["cycle_count"],
        temperature_c=doc["temperature_c"], charging=doc["charging"], time_to_empty_hours=time_to_empty,
        drain_apps=doc["drain_apps"], last_optimized_at=doc.get("last_optimized_at"),
        optimizations_run=doc.get("optimizations_run", 0),
    )


@api_router.get("/device/battery", response_model=BatteryStateOut)
async def get_battery(user=Depends(get_current_user)):
    """Generates a user's initial battery state once, lazily, on first read,
    and persists it — so unlike the old endpoint, revisiting this screen
    shows the same numbers instead of an identical hardcoded fixture."""
    doc = await _get_or_init_battery_state(user["user_id"])
    return _battery_state_out(doc)


@api_router.post("/device/battery/optimize", response_model=BatteryOptimizeResult)
async def optimize_battery(user=Depends(get_current_user)):
    """Pro-gated via the same stored is_pro flag as Auto-Clean Scheduling —
    matches what paywall.tsx already promises for 'Battery optimizer'."""
    if not user.get("is_pro", False):
        raise HTTPException(403, "Battery Optimizer is a Pro feature")
    uid = user["user_id"]
    doc = await _get_or_init_battery_state(uid)

    drain_apps = sorted(doc["drain_apps"], key=lambda a: a["pct"], reverse=True)
    to_restrict = drain_apps[:BATTERY_OPTIMIZE_MAX_APPS]
    remaining = drain_apps[BATTERY_OPTIMIZE_MAX_APPS:]
    freed_pct = sum(a["pct"] for a in to_restrict)
    level_gained = min(100 - doc["level"], freed_pct // 2)

    new_level = doc["level"] + level_gained
    now_iso = datetime.now(timezone.utc).isoformat()
    update = {
        "level": new_level,
        "drain_apps": remaining,
        "last_optimized_at": now_iso,
        "optimizations_run": doc.get("optimizations_run", 0) + 1,
    }
    await db.battery_state.update_one({"user_id": uid}, {"$set": update})
    doc.update(update)
    return BatteryOptimizeResult(
        apps_optimized=len(to_restrict), level_gained=level_gained, state=_battery_state_out(doc),
    )


# ==================== Large File Cleanup ====================
# The old GET /device/large-files was unauthenticated and returned the exact
# same fixed eight-file hardcoded array on every call — not per-user, not
# persisted. Worse than the other pre-existing gaps: the "Delete X GB" button
# on the large-files screen was 100% cosmetic (onPress={() => router.back()})
# — it never called the backend at all, so nothing was ever actually
# "deleted." This section replaces both with real per-user, persisted large
# files and a genuine delete action that records a real cleanup.
#
# Unlike Auto-Clean Scheduling — which deliberately excludes "Large files"
# from its allowed categories, since unattended/automatic deletion of a
# category likely to contain something the user wants to keep is too
# aggressive — deletion here is always an explicit, individually-selected
# user action on this screen, the same trust level as Duplicate Photo AI's
# manual review-then-remove flow. No Pro gate: unlike duplicate cleanup and
# the battery optimizer, paywall.tsx has never advertised a "large file"
# perk, so there's no promise to enforce here — this is free for everyone.
LARGE_FILE_POOL = [
    ("Vacation_Highlights.mp4", "video", (400, 2200)),
    ("Family_Wedding.mp4", "video", (600, 2400)),
    ("Screen_Recording.mov", "video", (150, 900)),
    ("Tutorial_Series.mp4", "video", (300, 1400)),
    ("Podcast_Episode.mp3", "audio", (40, 180)),
    ("Voice_Memos_Backup.m4a", "audio", (20, 120)),
    ("Project_Backup.zip", "doc", (200, 1200)),
    ("Design_Assets_Master.psd", "doc", (100, 600)),
    ("Old_Games_Archive.zip", "doc", (300, 1400)),
    ("Camera_Roll_Export.zip", "photo", (200, 1000)),
    ("Screenshots_2025.zip", "photo", (80, 400)),
]


def _make_large_file() -> dict:
    name, ftype, (lo, hi) = random.choice(LARGE_FILE_POOL)
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "size_mb": round(random.uniform(lo, hi), 1),
        "type": ftype,
        "modified_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "deleted_at": None,
    }


def _large_file_out(d: dict) -> LargeFileOut:
    return LargeFileOut(id=d["id"], name=d["name"], size_mb=d["size_mb"], type=d["type"], modified_at=d["modified_at"])


@api_router.get("/device/large-files", response_model=List[LargeFileOut])
async def get_large_files(user=Depends(get_current_user)):
    """Generates a user's initial large-file list once, lazily, on first
    read, and persists it to Mongo — so unlike the old endpoint, revisiting
    this screen shows the same files instead of an identical fixed array."""
    uid = user["user_id"]
    existing = await db.large_files.count_documents({"user_id": uid})
    if existing == 0:
        initial = [{**_make_large_file(), "user_id": uid} for _ in range(random.randint(5, 8))]
        await db.large_files.insert_many([f.copy() for f in initial])
    docs = await db.large_files.find({"user_id": uid, "status": "pending"}).sort("size_mb", -1).to_list(200)
    return [_large_file_out(d) for d in docs]


@api_router.post("/device/large-files/scan", response_model=LargeFileScanResult)
async def scan_large_files(user=Depends(get_current_user)):
    """Simulates newly-detected large files since the last scan — appends to
    (never replaces) the pending list, same pattern as Duplicate Photo AI."""
    uid = user["user_id"]
    new_files = [{**_make_large_file(), "user_id": uid} for _ in range(random.randint(1, 2))]
    await db.large_files.insert_many([f.copy() for f in new_files])
    docs = await db.large_files.find({"user_id": uid, "status": "pending"}).sort("size_mb", -1).to_list(200)
    return LargeFileScanResult(new_files_found=len(new_files), files=[_large_file_out(d) for d in docs])


@api_router.post("/device/large-files/delete", response_model=LargeFileDeleteResult)
async def delete_large_files(req: LargeFileDeleteRequest, user=Depends(get_current_user)):
    uid = user["user_id"]
    if not req.file_ids:
        raise HTTPException(400, "file_ids is required")

    docs = await db.large_files.find({
        "id": {"$in": req.file_ids}, "user_id": uid, "status": "pending",
    }).to_list(len(req.file_ids))
    found_ids = {d["id"] for d in docs}
    missing = [fid for fid in req.file_ids if fid not in found_ids]
    if missing:
        raise HTTPException(404, f"Unknown or already-deleted file id(s): {', '.join(missing)}")

    now_iso = datetime.now(timezone.utc).isoformat()
    freed_mb = round(sum(d["size_mb"] for d in docs), 1)
    await db.large_files.update_many(
        {"id": {"$in": list(found_ids)}, "user_id": uid},
        {"$set": {"status": "deleted", "deleted_at": now_iso}},
    )
    if freed_mb > 0:
        await db.cleanups.insert_one({
            "id": str(uuid.uuid4()),
            "device_id": uid,
            "categories": ["Large files"],
            "reclaimed_mb": freed_mb,
            "completed_at": now_iso,
        })
    remaining = await db.large_files.find({"user_id": uid, "status": "pending"}).sort("size_mb", -1).to_list(200)
    return LargeFileDeleteResult(
        deleted_count=len(docs), freed_mb=freed_mb, files=[_large_file_out(d) for d in remaining],
    )


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
        await db.cleanup_reports.create_index("share_code", unique=True)
        await db.cleanup_reports.create_index("user_id")
        await db.autoclean_schedules.create_index("user_id", unique=True)
        await db.duplicate_groups.create_index("user_id")
        await db.duplicate_groups.create_index([("user_id", 1), ("status", 1)])
        await db.security_findings.create_index([("user_id", 1), ("status", 1)])
        await db.security_scan_state.create_index("user_id", unique=True)
        await db.battery_state.create_index("user_id", unique=True)
        await db.large_files.create_index("user_id")
        await db.large_files.create_index([("user_id", 1), ("status", 1)])
    except Exception:
        logging.exception("Index creation failed")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    try:
        await _push_client.aclose()
    except Exception:
        pass
