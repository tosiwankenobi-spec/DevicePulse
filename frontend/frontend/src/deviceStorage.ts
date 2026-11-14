import { Directory, Paths } from 'expo-file-system';
import { Linking, Platform } from 'react-native';
import * as Battery from 'expo-battery';
import { api } from './api';

const MB = 1024 * 1024;

export type LocalDeviceScan = {
  id: string;
  started_at: string;
  completed_at: string;
  cache_mb: number;
  total_reclaimable_mb: number;
  storage_total_mb: number;
  storage_used_mb: number;
  storage_free_mb: number;
  health_before: number;
  health_after: number;
  source: 'device';
};

const toMb = (bytes: number) => Math.max(0, bytes / MB);

function storageHealth(totalBytes: number, freeBytes: number): number {
  const freePct = (freeBytes / totalBytes) * 100;
  return Math.max(35, Math.min(98, Math.round(45 + freePct * 1.5)));
}

export function scanLocalDevice(): LocalDeviceScan {
  const startedAt = new Date().toISOString();
  const totalBytes = Math.max(0, Paths.totalDiskSpace || 0);
  const freeBytes = Math.max(0, Paths.availableDiskSpace || 0);
  if (!totalBytes) {
    // Never substitute a guessed score when Android doesn't report disk size.
    throw new Error('Storage reading unavailable');
  }
  const cacheBytes = Math.max(0, Paths.cache.size || 0);
  const healthBefore = storageHealth(totalBytes, freeBytes);

  return {
    id: `local-${Date.now()}`,
    started_at: startedAt,
    completed_at: new Date().toISOString(),
    cache_mb: toMb(cacheBytes),
    total_reclaimable_mb: toMb(cacheBytes),
    storage_total_mb: toMb(totalBytes),
    storage_used_mb: toMb(Math.max(0, totalBytes - freeBytes)),
    storage_free_mb: toMb(freeBytes),
    health_before: healthBefore,
    // Re-measured after an actual cleanup; until then it equals the current reading.
    health_after: healthBefore,
    source: 'device',
  };
}

/** Same as scanLocalDevice, but null when Android doesn't report storage. */
export function tryScanLocalDevice(): LocalDeviceScan | null {
  try {
    return scanLocalDevice();
  } catch {
    return null;
  }
}

/** Sends a real measured reading to the server, which derives every score,
 * trend and forecast from these. Failures are ignored; nothing is guessed. */
export async function reportReading(scan: LocalDeviceScan | null): Promise<void> {
  if (!scan) return;
  let battery_pct: number | null = null;
  let charging: boolean | null = null;
  try {
    const power = await Battery.getPowerStateAsync();
    battery_pct = power.batteryLevel >= 0 ? Math.round(power.batteryLevel * 100) : null;
    charging = power.batteryState === Battery.BatteryState.CHARGING || power.batteryState === Battery.BatteryState.FULL;
  } catch {
    /* battery not exposed */
  }
  try {
    await api.postReading({
      storage_total_mb: scan.storage_total_mb,
      storage_free_mb: scan.storage_free_mb,
      cache_mb: scan.cache_mb,
      battery_pct,
      charging,
    });
  } catch {
    /* offline or signed out: the reading stays on the phone */
  }
}

export function clearDevicePulseCache(): number {
  const cache = new Directory(Paths.cache);
  if (!cache.exists) return 0;

  let removedBytes = 0;
  for (const entry of cache.list()) {
    try {
      removedBytes += Math.max(0, entry.size || 0);
      entry.delete();
    } catch {
      // Some active runtime files can be protected. Leave those untouched.
    }
  }
  return toMb(removedBytes);
}

export async function openDeviceStorageManager(): Promise<void> {
  if (Platform.OS === 'android') {
    try {
      await Linking.sendIntent('android.settings.INTERNAL_STORAGE_SETTINGS');
      return;
    } catch {
      // Fall through to the app settings screen when a vendor removes this intent.
    }
  }
  await Linking.openSettings();
}

async function openAndroidSetting(action: string): Promise<void> {
  if (Platform.OS === 'android') {
    try {
      await Linking.sendIntent(action);
      return;
    } catch {
      // Device vendors occasionally omit a standard settings intent.
    }
  }
  await Linking.openSettings();
}

export const openBatterySettings = () => openAndroidSetting('android.settings.BATTERY_SAVER_SETTINGS');
export const openSecuritySettings = () => openAndroidSetting('android.settings.SECURITY_SETTINGS');
export const openApplicationSettings = () => Linking.openSettings();
