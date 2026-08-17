const BASE = process.env.EXPO_PUBLIC_BACKEND_URL;

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export const api = {
  health: () => req<any>('/device/health'),
  storage: () => req<any>('/device/storage'),
  duplicates: () => req<any[]>('/device/duplicates'),
  largeFiles: () => req<any[]>('/device/large-files'),
  battery: () => req<any>('/device/battery'),
  security: () => req<any>('/device/security'),
  runScan: () => req<any>('/device/scan', { method: 'POST' }),
  runClean: (body: { categories: string[]; reclaimable_mb: number; device_id?: string }) =>
    req<any>('/device/clean', { method: 'POST', body: JSON.stringify(body) }),
  recommendations: (body: any) =>
    req<any[]>('/ai/recommendations', { method: 'POST', body: JSON.stringify(body) }),
  history: (deviceId: string) => req<any[]>(`/history?device_id=${deviceId}`),
  historySummary: (deviceId: string) => req<any>(`/history/summary?device_id=${deviceId}`),
  referral: (deviceId: string) => req<any>(`/referral/${deviceId}`),
  recordInvite: (deviceId: string) => req<any>(`/referral/${deviceId}/invite`, { method: 'POST' }),
  getReminders: (deviceId: string) => req<any>(`/reminders/${deviceId}`),
  updateReminders: (deviceId: string, prefs: any) =>
    req<any>(`/reminders/${deviceId}`, { method: 'PUT', body: JSON.stringify({ device_id: deviceId, ...prefs }) }),
  streak: (deviceId: string) => req<any>(`/streak/${deviceId}`),
  useFreeze: (deviceId: string) => req<any>(`/streak/${deviceId}/freeze`, { method: 'POST' }),
  cacheBreakdown: (deviceId: string) => req<any>(`/device/cache-breakdown?device_id=${deviceId}`),
  healthTrend: (deviceId: string) => req<any>(`/device/health-trend/${deviceId}`),
  forecast: (deviceId: string) => req<any>(`/forecast/${deviceId}`),
  family: (deviceId: string) => req<any[]>(`/family/${deviceId}`),
  addMember: (deviceId: string, body: { name: string; device_type: string }) =>
    req<any>(`/family/${deviceId}/member`, { method: 'POST', body: JSON.stringify(body) }),
  removeMember: (deviceId: string, memberId: string) =>
    req<any>(`/family/${deviceId}/member/${memberId}`, { method: 'DELETE' }),
};
