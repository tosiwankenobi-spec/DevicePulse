import { getToken } from './authStorage';

const BASE = process.env.EXPO_PUBLIC_BACKEND_URL;

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

  // Device (simulated)
  health: () => req<any>('/device/health'),
  storage: () => req<any>('/device/storage'),
  duplicates: () => req<any[]>('/device/duplicates'),
  largeFiles: () => req<any[]>('/device/large-files'),
  battery: () => req<any>('/device/battery'),
  security: () => req<any>('/device/security'),
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
  family: () => req<any[]>('/family'),
  addMember: (body: { name: string; device_type: string }) =>
    req<any>('/family/member', { method: 'POST', body: JSON.stringify(body) }),
  removeMember: (memberId: string) =>
    req<any>(`/family/member/${memberId}`, { method: 'DELETE' }),
};
