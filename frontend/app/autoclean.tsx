import React, { useCallback, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Switch, ActivityIndicator } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { api } from '@/src/api';
import { useSubscription } from '@/src/lib/revenuecat';
import { theme } from '@/src/theme';

// Categories Auto-Clean is allowed to touch — deliberately excludes "Large
// files": unattended deletion is riskier for a category likely to contain
// something the user actually wants to keep. Kept in sync with the backend's
// AUTOCLEAN_ALLOWED_CATEGORIES.
const CATEGORIES = ['Junk files', 'Duplicates', 'App cache'];
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

type Schedule = {
  enabled: boolean;
  frequency: 'daily' | 'weekly';
  day_of_week: number | null;
  categories: string[];
  last_run_at: string | null;
};

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never run yet';
  const d = new Date(iso).getTime();
  const mins = Math.max(0, Math.round((Date.now() - d) / 60000));
  if (mins < 60) return `Last ran ${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `Last ran ${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `Last ran ${days}d ago`;
}

export default function AutoClean() {
  const router = useRouter();
  const { isSubscribed, isLoading: subLoading } = useSubscription();

  const [loading, setLoading] = useState(true);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [frequency, setFrequency] = useState<'daily' | 'weekly'>('weekly');
  const [dayOfWeek, setDayOfWeek] = useState(6); // Sunday, matching the old cosmetic default
  const [categories, setCategories] = useState<string[]>(['Junk files', 'App cache']);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [errMsg, setErrMsg] = useState('');

  const load = useCallback(async () => {
    if (!isSubscribed) { setLoading(false); return; }
    try {
      const s = await api.autoCleanSchedule();
      setSchedule(s);
      if (s) {
        setEnabled(s.enabled);
        setFrequency(s.frequency);
        if (s.day_of_week != null) setDayOfWeek(s.day_of_week);
        setCategories(s.categories);
      }
    } catch (e) {
      console.log(e);
    } finally {
      setLoading(false);
    }
  }, [isSubscribed]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const toggleCategory = (c: string) => {
    setCategories((prev: string[]) => (prev.includes(c) ? prev.filter((x: string) => x !== c) : [...prev, c]));
  };

  const onSave = async () => {
    if (saving) return;
    setErrMsg('');
    if (categories.length === 0) {
      setErrMsg('Pick at least one category to clean.');
      return;
    }
    setSaving(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    try {
      const body: any = { enabled, frequency, categories };
      if (frequency === 'weekly') body.day_of_week = dayOfWeek;
      const s = await api.saveAutoCleanSchedule(body);
      setSchedule(s);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    } catch (e) {
      setErrMsg('Could not save your schedule. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    if (deleting) return;
    setDeleting(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    try {
      await api.deleteAutoCleanSchedule();
      setSchedule(null);
    } catch (e) {
      console.log(e);
    } finally {
      setDeleting(false);
    }
  };

  const body = (subLoading || loading) ? (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
      <ActivityIndicator color={theme.color.brand} />
    </View>
  ) : !isSubscribed ? (
    <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40, flexGrow: 1 }} showsVerticalScrollIndicator={false}>
      <LinearGradient colors={theme.gradients.brand} style={styles.hero} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
        <Ionicons name="time" size={36} color={theme.color.onBrand} />
        <Text style={styles.heroTitle}>Auto-Clean Scheduling</Text>
        <Text style={styles.heroSub}>
          Let DevicePulse clean junk files, duplicates, and app cache automatically — daily or weekly, on your schedule. This is a Pro feature.
        </Text>
      </LinearGradient>
      <Pressable style={styles.upgradeBtn} onPress={() => router.push('/paywall')} testID="autoclean-upgrade">
        <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
        <Text style={styles.upgradeBtnText}>Unlock with Pro</Text>
      </Pressable>
    </ScrollView>
  ) : (
    <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
      <View style={styles.statusRow}>
        <View style={[styles.statusDot, { backgroundColor: schedule?.enabled ? theme.color.brand : theme.color.onSurface3 }]} />
        <Text style={styles.statusText}>
          {schedule ? (schedule.enabled ? 'Active' : 'Paused') : 'Not set up yet'}
        </Text>
        {!!schedule && <Text style={styles.statusSub}>· {timeAgo(schedule.last_run_at)}</Text>}
      </View>

      <View style={styles.card}>
        <View style={styles.rowBetween}>
          <Text style={styles.cardLabel}>Enabled</Text>
          <Switch
            value={enabled}
            onValueChange={setEnabled}
            trackColor={{ true: theme.color.brand, false: theme.color.border }}
            thumbColor="#fff"
            testID="autoclean-enabled-toggle"
          />
        </View>
      </View>

      <Text style={styles.section}>Frequency</Text>
      <View style={styles.chipRow}>
        {(['daily', 'weekly'] as const).map((f) => (
          <Pressable
            key={f}
            style={[styles.chip, frequency === f && styles.chipActive]}
            onPress={() => setFrequency(f)}
            testID={`autoclean-freq-${f}`}
          >
            <Text style={[styles.chipText, frequency === f && styles.chipTextActive]}>
              {f === 'daily' ? 'Daily' : 'Weekly'}
            </Text>
          </Pressable>
        ))}
      </View>

      {frequency === 'weekly' && (
        <>
          <Text style={styles.section}>Day of week</Text>
          <View style={styles.chipRow}>
            {DAYS.map((d, i) => (
              <Pressable
                key={d}
                style={[styles.dayChip, dayOfWeek === i && styles.chipActive]}
                onPress={() => setDayOfWeek(i)}
                testID={`autoclean-day-${i}`}
              >
                <Text style={[styles.chipText, dayOfWeek === i && styles.chipTextActive]}>{d}</Text>
              </Pressable>
            ))}
          </View>
        </>
      )}

      <Text style={styles.section}>What to clean</Text>
      <View style={styles.card}>
        {CATEGORIES.map((c, i) => (
          <View key={c}>
            <View style={styles.rowBetween}>
              <Text style={styles.cardLabel}>{c}</Text>
              <Switch
                value={categories.includes(c)}
                onValueChange={() => toggleCategory(c)}
                trackColor={{ true: theme.color.brand, false: theme.color.border }}
                thumbColor="#fff"
                testID={`autoclean-cat-${c.replace(/\s+/g, '-').toLowerCase()}`}
              />
            </View>
            {i < CATEGORIES.length - 1 && <View style={styles.divider} />}
          </View>
        ))}
      </View>
      <Text style={styles.hint}>Large files are never touched automatically — you'll always review those yourself.</Text>

      {!!errMsg && <Text style={styles.errMsg} testID="autoclean-error">{errMsg}</Text>}

      <Pressable style={styles.saveBtn} onPress={onSave} disabled={saving} testID="autoclean-save">
        <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
        {saving ? <ActivityIndicator color={theme.color.onBrand} /> : <Text style={styles.saveBtnText}>{schedule ? 'Save changes' : 'Turn on Auto-Clean'}</Text>}
      </Pressable>

      {!!schedule && (
        <Pressable style={styles.deleteBtn} onPress={onDelete} disabled={deleting} testID="autoclean-delete">
          {deleting ? <ActivityIndicator size="small" color={theme.color.error} /> : <Text style={styles.deleteBtnText}>Turn off Auto-Clean</Text>}
        </Pressable>
      )}
    </ScrollView>
  );

  return (
    <View style={styles.container} testID="autoclean-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="autoclean-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Auto-Clean</Text>
          <View style={{ width: 26 }} />
        </View>
        {body}
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  hero: { borderRadius: theme.radius.lg, padding: theme.space.xl, alignItems: 'center' },
  heroTitle: { color: theme.color.onBrand, fontSize: 20, fontWeight: '800', marginTop: 10, textAlign: 'center' },
  heroSub: { color: 'rgba(2,44,34,0.85)', fontSize: 13, textAlign: 'center', marginTop: 8, lineHeight: 18 },
  upgradeBtn: { height: 54, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden', marginTop: theme.space.xl },
  upgradeBtnText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: theme.space.sm, marginBottom: theme.space.md },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { color: theme.color.onSurface, fontSize: 14, fontWeight: '700' },
  statusSub: { color: theme.color.onSurface3, fontSize: 13 },
  card: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, borderWidth: 1, borderColor: theme.color.border, padding: theme.space.md },
  cardLabel: { color: theme.color.onSurface, fontSize: 15, fontWeight: '600' },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 6 },
  divider: { height: 1, backgroundColor: theme.color.border, marginVertical: 4 },
  section: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '700', letterSpacing: 1.1, textTransform: 'uppercase', marginTop: theme.space.lg, marginBottom: theme.space.sm },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: theme.radius.pill, backgroundColor: theme.color.surface2, borderWidth: 1, borderColor: theme.color.border },
  dayChip: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.color.surface2, borderWidth: 1, borderColor: theme.color.border },
  chipActive: { backgroundColor: theme.color.brand3, borderColor: theme.color.brand },
  chipText: { color: theme.color.onSurface2, fontSize: 13, fontWeight: '600' },
  chipTextActive: { color: theme.color.brand },
  hint: { color: theme.color.onSurface3, fontSize: 11, marginTop: 8, lineHeight: 15 },
  errMsg: { color: theme.color.error, fontSize: 13, textAlign: 'center', marginTop: theme.space.md },
  saveBtn: { height: 54, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden', marginTop: theme.space.xl },
  saveBtnText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
  deleteBtn: { alignItems: 'center', justifyContent: 'center', paddingVertical: theme.space.md, marginTop: theme.space.sm },
  deleteBtnText: { color: theme.color.error, fontSize: 13, fontWeight: '600' },
});
