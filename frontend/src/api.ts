import { getToken } from './authStorage';

const BASE = process.env.EXPO_PUBLIC_BACKEND_URL;

// Public, human-viewable page for a shared Cleanup Report (GET /r/{code},
// outside the /api prefix) — this is the link that goes in the share sheet.
export const reportShareUrl = (shareCode: string) => `${BASE}/r/${shareCode}`;

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getToken();
  const res = await fetch(`${BASE}/api${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers || {}),
    },
  });
  if (res.status === 401) {
    if (onUnauthorized) onUnauthorized();
    throw new Error('unauthorized');
  }
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export const api = {
  // Auth
  createSession: (sessionId: string) =>
    req<any>('/auth/session', { method: 'POST', body: JSON.stringify({ session_id: sessionId }) }),
  me: () => req<any>('/auth/me'),
  logout: () => req<any>('/auth/logout', { method: 'POST' }),
  sessions: () => req<any[]>('/auth/sessions'),
  revokeSession: (sid: string) => req<any>(`/auth/sessions/${sid}/revoke`, { method: 'POST' }),
  deleteAccount: () => req<any>('/auth/account', { method: 'DELETE' }),
  registerPush: (body: { user_id: string; platform: string; device_token: string }) =>
    req<any>('/register-push', { method: 'POST', body: JSON.stringify(body) }),
  testPush: () => req<any>('/push/test', { method: 'POST' }),

  // Device (simulated)
  health: () => req<any>('/device/health'),
  storage: () => req<any>('/device/storage'),
  duplicates: () => req<any[]>('/device/duplicates'),
  scanDuplicates: () => req<any>('/device/duplicates/scan', { method: 'POST' }),
  removeDuplicates: (groupIds: string[]) =>
    req<any>('/device/duplicates/remove', { method: 'POST', body: JSON.stringify({ group_ids: groupIds }) }),
  largeFiles: () => req<any[]>('/device/large-files'),
  battery: () => req<any>('/device/battery'),
  optimizeBattery: () => req<any>('/device/battery/optimize', { method: 'POST' }),
  security: () => req<any>('/device/security'),
  scanSecurity: () => req<any>('/device/security/scan', { method: 'POST' }),
  resolveSecurityFinding: (id: string) => req<any>(`/device/security/findings/${id}/resolve`, { method: 'POST' }),
  runScan: () => req<any>('/device/scan', { method: 'POST' }),
  runClean: (body: { categories: string[]; reclaimable_mb: number }) =>
    req<any>('/device/clean', { method: 'POST', body: JSON.stringify(body) }),
  recommendations: (body: any) =>
    req<any[]>('/ai/recommendations', { method: 'POST', body: JSON.stringify(body) }),

  // Per-user (identity derived from token)
  history: () => req<any[]>('/history'),
  historySummary: () => req<any>('/history/summary'),
  referral: () => req<any>('/referral'),
  recordInvite: () => req<any>('/referral/invite', { method: 'POST' }),
  getReminders: () => req<any>('/reminders'),
  updateReminders: (prefs: any) =>
    req<any>('/reminders', { method: 'PUT', body: JSON.stringify({ device_id: 'self', ...prefs }) }),
  streak: () => req<any>('/streak'),
  useFreeze: () => req<any>('/streak/freeze', { method: 'POST' }),
  cacheBreakdown: () => req<any>('/device/cache-breakdown'),
  healthTrend: () => req<any>('/device/health-trend'),
  forecast: () => req<any>('/forecast'),
  forecastQuickFix: () => req<any>('/forecast/quick-fix', { method: 'POST' }),
  pulseDaily: () => req<any>('/pulse/daily'),
  widgetSummary: () => req<any>('/widget/summary'),
  activeNudge: () => req<any>('/nudges/active'),
  dismissNudge: (type: string) => req<any>(`/nudges/${type}/dismiss`, { method: 'POST' }),
  familyGroup: () => req<any>('/family/group'),
  createFamily: () => req<any>('/family/create', { method: 'POST' }),
  joinFamily: (inviteCode: string) =>
    req<any>('/family/join', { method: 'POST', body: JSON.stringify({ invite_code: inviteCode }) }),
  leaveFamily: () => req<any>('/family/leave', { method: 'POST' }),
  familyRemoteClean: (memberUserId: string) =>
    req<any>(`/family/remote-clean/${memberUserId}`, { method: 'POST' }),
  reportMine: () => req<any>('/reports/mine'),
  generateReport: () => req<any>('/reports/generate', { method: 'POST' }),

  // Entitlements (Pro) — synced from the real RevenueCat state, see revenuecat.tsx
  myEntitlement: () => req<any>('/entitlements/me'),
  syncEntitlement: (isPro: boolean) =>
    req<any>('/entitlements/sync', { method: 'POST', body: JSON.stringify({ is_pro: isPro }) }),

  // Auto-Clean Scheduling (Pro-only)
  autoCleanSchedule: () => req<any>('/autoclean/schedule'),
  saveAutoCleanSchedule: (body: { enabled: boolean; frequency: string; day_of_week?: number; categories: string[] }) =>
    req<any>('/autoclean/schedule', { method: 'PUT', body: JSON.stringify(body) }),
  deleteAutoCleanSchedule: () => req<any>('/autoclean/schedule', { method: 'DELETE' }),
  runAutoCleanIfDue: () => req<any>('/autoclean/run-if-due', { method: 'POST' }),

  // AI Health Coach
  coachDaily: () => req<any>('/coach/daily'),
  coachHistory: () => req<any[]>('/coach/history'),
  coachChat: (body: { message: string; health_score?: number; storage_used_pct?: number; battery_health_pct?: number }) =>
    req<any>('/coach/chat', { method: 'POST', body: JSON.stringify(body) }),
  clearCoach: () => req<any>('/coach/history', { method: 'DELETE' }),
  coachInsights: () => req<any[]>('/coach/insights'),
  ackCoachInsight: (key: string) => req<any>(`/coach/insights/${key}/ack`, { method: 'POST' }),
};
