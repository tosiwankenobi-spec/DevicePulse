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
  runClean: (body: { categories: string[]; reclaimable_mb: number }) =>
    req<any>('/device/clean', { method: 'POST', body: JSON.stringify(body) }),
  recommendations: (body: any) =>
    req<any[]>('/ai/recommendations', { method: 'POST', body: JSON.stringify(body) }),
};
