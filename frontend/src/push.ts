import { Platform } from 'react-native';
import { api } from './api';

// Registers this device's native push token with the backend, bound to the user.
// No-ops on web. Safe to call on every app open (tokens rotate; backend upserts).
export async function registerForPush(userId: string): Promise<void> {
  if (Platform.OS === 'web') return;
  try {
    const Notifications = require('expo-notifications');
    const { status } = await Notifications.requestPermissionsAsync();
    if (status !== 'granted') return;
    const tokenResp = await Notifications.getDevicePushTokenAsync();
    await api.registerPush({
      user_id: userId,
      platform: Platform.OS,
      device_token: tokenResp.data,
    });
  } catch (e) {
    console.log('push registration skipped/failed', e);
  }
}
