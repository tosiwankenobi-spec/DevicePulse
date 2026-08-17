import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const SCHEDULED_KEY = 'dp:trialReminderFor';
const IDENTIFIER = 'trial-ending-reminder';

/**
 * Schedules a friendly local notification ~24h before a RevenueCat trial ends.
 * - No-ops on web / when not in a trial.
 * - Deduped by the trial's expiration date so we don't reschedule repeatedly.
 */
export async function scheduleTrialReminder(entitlement: any | undefined): Promise<void> {
  if (Platform.OS === 'web') return;
  try {
    const Notifications = require('expo-notifications');

    const isTrial =
      entitlement &&
      String(entitlement.periodType ?? '').toLowerCase().includes('trial') &&
      entitlement.expirationDate;

    // Not in a trial anymore → clear any pending reminder + saved marker
    if (!isTrial) {
      await Notifications.cancelScheduledNotificationAsync(IDENTIFIER).catch(() => {});
      await AsyncStorage.removeItem(SCHEDULED_KEY);
      return;
    }

    const expMs = new Date(entitlement.expirationDate).getTime();
    const already = await AsyncStorage.getItem(SCHEDULED_KEY);
    if (already === entitlement.expirationDate) return; // already scheduled for this trial

    // 24h before expiry; if that's already passed, fire in 5s as a fallback heads-up
    const fireMs = expMs - 24 * 60 * 60 * 1000;
    const fireDate = fireMs > Date.now() ? new Date(fireMs) : new Date(Date.now() + 5000);

    const { status } = await Notifications.getPermissionsAsync();
    if (status !== 'granted') return; // respect the user's choice; don't nag here

    await Notifications.cancelScheduledNotificationAsync(IDENTIFIER).catch(() => {});
    await Notifications.scheduleNotificationAsync({
      identifier: IDENTIFIER,
      content: {
        title: 'Your Pro trial ends tomorrow',
        body: "Heads up — your DevicePulse Pro free trial ends in 24 hours. Keep Pro, or cancel anytime so you're not charged.",
        data: { action_url: '/paywall' },
      },
      trigger: { date: fireDate },
    });
    await AsyncStorage.setItem(SCHEDULED_KEY, entitlement.expirationDate);
  } catch (e) {
    console.log('trial reminder scheduling skipped', e);
  }
}
