import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Switch, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { api } from '@/src/api';
import { getDeviceId } from '@/src/device';
import { theme } from '@/src/theme';

const OPTIONS = [
  { key: 'low_storage', icon: 'server-outline', title: 'Low storage alert', desc: 'Nudge me when free space drops below 15%.' },
  { key: 'weekly_cleanup', icon: 'calendar-outline', title: 'Weekly cleanup', desc: 'A gentle reminder to run a Smart Scan every week.' },
  { key: 'after_downloads', icon: 'cloud-download-outline', title: 'After big downloads', desc: 'Suggest a cleanup after large files pile up.' },
  { key: 'battery_alerts', icon: 'battery-charging-outline', title: 'Battery insights', desc: 'Let me know when a high-drain app appears.' },
] as const;

export default function Reminders() {
  const router = useRouter();
  const [prefs, setPrefs] = useState<any>(null);
  const [deviceId, setDeviceId] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const id = await getDeviceId();
      setDeviceId(id);
      try { setPrefs(await api.getReminders(id)); } catch (e) { console.log(e); }
      finally { setLoading(false); }
    })();
  }, []);

  const toggle = async (key: string, val: boolean) => {
    Haptics.selectionAsync();
    const next = { ...prefs, [key]: val };
    setPrefs(next);
    try {
      await api.updateReminders(deviceId, {
        low_storage: next.low_storage,
        weekly_cleanup: next.weekly_cleanup,
        after_downloads: next.after_downloads,
        battery_alerts: next.battery_alerts,
      });
    } catch (e) { console.log(e); }
  };

  return (
    <View style={styles.container} testID="reminders-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="reminders-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Smart Reminders</Text>
          <View style={{ width: 26 }} />
        </View>

        {loading ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : (
          <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
            <View style={styles.hero}>
              <Ionicons name="notifications" size={30} color={theme.color.brand} />
              <Text style={styles.heroText}>Stay ahead of clutter. DevicePulse will quietly nudge you at the right moments.</Text>
            </View>

            {OPTIONS.map((o) => (
              <View key={o.key} style={styles.row} testID={`reminder-${o.key}`}>
                <View style={styles.rowIcon}>
                  <Ionicons name={o.icon as any} size={20} color={theme.color.brand} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.rowTitle}>{o.title}</Text>
                  <Text style={styles.rowDesc}>{o.desc}</Text>
                </View>
                <Switch
                  value={!!prefs?.[o.key]}
                  onValueChange={(v) => toggle(o.key, v)}
                  trackColor={{ true: theme.color.brand, false: theme.color.border }}
                  thumbColor="#fff"
                  testID={`reminder-toggle-${o.key}`}
                />
              </View>
            ))}

            <View style={styles.note}>
              <Ionicons name="phone-portrait-outline" size={16} color={theme.color.onSurface3} />
              <Text style={styles.noteText}>
                Delivered as push notifications on a real device after you publish and install the built app.
              </Text>
            </View>
          </ScrollView>
        )}
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  hero: { flexDirection: 'row', gap: 12, alignItems: 'center', backgroundColor: theme.color.brand3, borderRadius: theme.radius.lg, padding: theme.space.lg, marginBottom: theme.space.lg },
  heroText: { color: theme.color.onSurface, fontSize: 14, flex: 1, lineHeight: 20 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, padding: theme.space.md, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.sm },
  rowIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: theme.color.brand3, alignItems: 'center', justifyContent: 'center' },
  rowTitle: { color: theme.color.onSurface, fontSize: 15, fontWeight: '600' },
  rowDesc: { color: theme.color.onSurface2, fontSize: 12, marginTop: 2, lineHeight: 17 },
  note: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', marginTop: theme.space.lg, paddingHorizontal: theme.space.sm },
  noteText: { color: theme.color.onSurface3, fontSize: 12, flex: 1, lineHeight: 17 },
});
