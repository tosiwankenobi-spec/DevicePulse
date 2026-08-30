import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, RefreshControl, ActivityIndicator } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/src/theme';
import { api } from '@/src/api';

type Size = 'small' | 'medium';

type WidgetSummary = {
  score: number;
  status: string;
  storage_used_pct: number;
  storage_used_gb: number;
  storage_total_gb: number;
  battery_pct: number;
  security_ok: boolean;
  updated_at: string;
};

// How often the preview re-polls the live snapshot while this screen is open —
// stands in for the OS refreshing an installed home-screen widget on a timeline.
const LIVE_POLL_MS = 20000;

function relativeUpdated(iso: string | undefined, nowMs: number): string {
  if (!iso) return 'Connecting…';
  const diffS = Math.max(0, Math.floor((nowMs - new Date(iso).getTime()) / 1000));
  if (diffS < 5) return 'Updated just now';
  if (diffS < 60) return `Updated ${diffS}s ago`;
  const m = Math.floor(diffS / 60);
  return `Updated ${m}m ago`;
}

export default function WidgetPreview() {
  const router = useRouter();
  const [size, setSize] = useState<Size>('medium');
  const [summary, setSummary] = useState<WidgetSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const fetchSummary = async () => {
    try {
      const s = await api.widgetSummary();
      setSummary(s);
    } catch (e) {
      console.log(e);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchSummary();
    setRefreshing(false);
  };

  // Fetch immediately, then keep polling on the same cadence a real widget
  // would refresh on, only while this screen is actually focused.
  useFocusEffect(
    React.useCallback(() => {
      fetchSummary();
      const poll = setInterval(fetchSummary, LIVE_POLL_MS);
      return () => clearInterval(poll);
    }, [])
  );

  // Separate 1s tick purely to keep the "Updated Xs ago" label moving between polls.
  useEffect(() => {
    const tick = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(tick);
  }, []);

  return (
    <View style={styles.container} testID="widget-preview-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="widget-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Home Screen Widget</Text>
          <View style={{ width: 26 }} />
        </View>

        <ScrollView
          contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.color.onSurface2} />}
        >
          <Text style={styles.lead}>Keep your device health one glance away — right on your home screen.</Text>

          {/* Size toggle */}
          <View style={styles.sizeToggle}>
            {(['small', 'medium'] as Size[]).map((s) => (
              <Pressable key={s} style={[styles.sizeBtn, size === s && styles.sizeBtnActive]} onPress={() => setSize(s)} testID={`widget-size-${s}`}>
                <Text style={[styles.sizeText, size === s && styles.sizeTextActive]}>{s === 'small' ? 'Small' : 'Medium'}</Text>
              </Pressable>
            ))}
          </View>

          {/* Wallpaper mock */}
          <LinearGradient colors={['#1a2f3a', '#0d1f28', '#08161d']} style={styles.wallpaper}>
            {/* faux app icons */}
            <View style={styles.iconRow}>
              {['#F59E0B', '#0EA5E9', '#EF4444', '#8B5CF6'].map((c, i) => (
                <View key={i} style={[styles.appIcon, { backgroundColor: c }]} />
              ))}
            </View>

            {size === 'small' ? <SmallWidget summary={summary} loading={loading} /> : <MediumWidget summary={summary} loading={loading} />}

            <View style={styles.iconRow}>
              {['#10B981', '#EC4899', '#64748B', '#0EA5E9'].map((c, i) => (
                <View key={i} style={[styles.appIcon, { backgroundColor: c }]} />
              ))}
            </View>
          </LinearGradient>

          <View style={styles.liveRow} testID="widget-live-indicator">
            <View style={[styles.liveDot, !summary && styles.liveDotOff]} />
            <Text style={styles.liveText}>{relativeUpdated(summary?.updated_at, nowMs)}</Text>
          </View>

          <View style={styles.infoCard}>
            <Ionicons name="information-circle-outline" size={20} color={theme.color.info} />
            <Text style={styles.infoText}>
              This preview is live — it's pulling your real health score right now, and refreshes automatically like the real widget will. Add one from your home screen once you install the built app.
            </Text>
          </View>

          <Pressable style={styles.cta} onPress={() => router.back()} testID="widget-done">
            <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
            <Text style={styles.ctaText}>Looks great</Text>
          </Pressable>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

type WidgetProps = { summary: WidgetSummary | null; loading: boolean };

const SmallWidget = ({ summary, loading }: WidgetProps) => (
  <View style={styles.smallWidget} testID="widget-small">
    <LinearGradient colors={theme.gradients.hero2} style={StyleSheet.absoluteFill} />
    <View style={styles.miniRing}>
      {loading && !summary ? (
        <ActivityIndicator color={theme.color.onSurface} size="small" />
      ) : (
        <Text style={styles.miniScore}>{summary ? summary.score : '--'}</Text>
      )}
    </View>
    <Text style={styles.widgetLabel}>DevicePulse</Text>
    <Text style={styles.widgetSub}>{summary ? summary.status : 'Loading…'}</Text>
  </View>
);

const MediumWidget = ({ summary, loading }: WidgetProps) => (
  <View style={styles.mediumWidget} testID="widget-medium">
    <LinearGradient colors={theme.gradients.hero2} style={StyleSheet.absoluteFill} />
    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
      <View style={styles.miniRing}>
        {loading && !summary ? (
          <ActivityIndicator color={theme.color.onSurface} size="small" />
        ) : (
          <Text style={styles.miniScore}>{summary ? summary.score : '--'}</Text>
        )}
      </View>
      <View style={{ flex: 1, marginLeft: 14 }}>
        <Text style={styles.widgetLabel}>Device Health</Text>
        <View style={styles.miniStat}>
          <Ionicons name="server-outline" size={13} color={theme.color.info} />
          <Text style={styles.miniStatText}>Storage {summary ? `${summary.storage_used_pct}%` : '--'}</Text>
        </View>
        <View style={styles.miniStat}>
          <Ionicons name="battery-half-outline" size={13} color={theme.color.warning} />
          <Text style={styles.miniStatText}>Battery {summary ? `${summary.battery_pct}%` : '--'}</Text>
        </View>
        <View style={styles.miniStat}>
          <Ionicons
            name={summary?.security_ok ? 'shield-checkmark-outline' : 'shield-outline'}
            size={13}
            color={summary?.security_ok ? theme.color.brand : theme.color.warning}
          />
          <Text style={styles.miniStatText}>{summary ? (summary.security_ok ? 'Secure' : 'Review needed') : '--'}</Text>
        </View>
      </View>
    </View>
  </View>
);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  lead: { color: theme.color.onSurface2, fontSize: 14, lineHeight: 20, marginBottom: theme.space.lg },
  sizeToggle: { flexDirection: 'row', backgroundColor: theme.color.surface2, borderRadius: theme.radius.pill, padding: 4, alignSelf: 'center', borderWidth: 1, borderColor: theme.color.border },
  sizeBtn: { paddingHorizontal: 28, paddingVertical: 8, borderRadius: theme.radius.pill },
  sizeBtnActive: { backgroundColor: theme.color.brand },
  sizeText: { color: theme.color.onSurface2, fontSize: 14, fontWeight: '600' },
  sizeTextActive: { color: theme.color.onBrand, fontWeight: '700' },
  wallpaper: { borderRadius: 32, padding: theme.space.xl, marginTop: theme.space.xl, alignItems: 'center', gap: theme.space.xl, borderWidth: 1, borderColor: theme.color.border },
  iconRow: { flexDirection: 'row', gap: 18 },
  appIcon: { width: 44, height: 44, borderRadius: 12, opacity: 0.7 },
  smallWidget: { width: 150, height: 150, borderRadius: 24, overflow: 'hidden', alignItems: 'center', justifyContent: 'center', gap: 6, borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  mediumWidget: { width: 300, height: 150, borderRadius: 24, overflow: 'hidden', justifyContent: 'center', padding: theme.space.lg, borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  miniRing: { width: 66, height: 66, borderRadius: 33, borderWidth: 6, borderColor: theme.color.brand, borderRightColor: theme.color.border, borderBottomColor: theme.color.border, alignItems: 'center', justifyContent: 'center', transform: [{ rotate: '-45deg' }] },
  miniScore: { color: theme.color.onSurface, fontSize: 24, fontWeight: '800', transform: [{ rotate: '45deg' }] },
  widgetLabel: { color: theme.color.onSurface, fontSize: 15, fontWeight: '700' },
  widgetSub: { color: theme.color.onSurface2, fontSize: 12 },
  miniStat: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  miniStatText: { color: theme.color.onSurface2, fontSize: 12 },
  liveRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: theme.space.md },
  liveDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: theme.color.success },
  liveDotOff: { backgroundColor: theme.color.onSurface3 },
  liveText: { color: theme.color.onSurface2, fontSize: 12 },
  infoCard: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, padding: theme.space.md, marginTop: theme.space.xl, borderWidth: 1, borderColor: theme.color.border },
  infoText: { color: theme.color.onSurface2, fontSize: 13, flex: 1, lineHeight: 19 },
  cta: { height: 54, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden', marginTop: theme.space.lg },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
});
