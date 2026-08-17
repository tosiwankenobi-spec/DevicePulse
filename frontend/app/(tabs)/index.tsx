import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, RefreshControl, ActivityIndicator } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { HealthRing } from '@/src/components/HealthRing';
import { GlassCard } from '@/src/components/GlassCard';
import { VLogo } from '@/src/components/VLogo';
import { api } from '@/src/api';
import { getDeviceId } from '@/src/device';
import { useAuth } from '@/src/AuthContext';
import { theme } from '@/src/theme';

type Health = {
  score: number;
  status: string;
  storage_used_gb: number;
  storage_total_gb: number;
  ram_used_pct: number;
  battery_pct: number;
  battery_health_pct: number;
  security_status: string;
  issues_found: number;
};

type Rec = { title: string; description: string; impact: string };

export default function Home() {
  const router = useRouter();
  const { user, justLoggedIn, clearJustLoggedIn } = useAuth();
  const [health, setHealth] = useState<Health | null>(null);
  const [recs, setRecs] = useState<Rec[] | null>(null);
  const [loadingRecs, setLoadingRecs] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [streak, setStreak] = useState<number | null>(null);
  const [forecastDays, setForecastDays] = useState<number | null>(null);

  const load = async () => {
    try {
      const h = await api.health();
      setHealth(h);
    } catch (e) { console.log(e); }
    try {
      const id = await getDeviceId();
      const [s, f] = await Promise.all([api.streak(), api.forecast()]);
      setStreak(s.current_streak_weeks);
      setForecastDays(f.days_until_full);
    } catch (e) { console.log(e); }
  };

  const loadRecs = async (h: Health) => {
    try {
      setLoadingRecs(true);
      const r = await api.recommendations({
        health_score: h.score,
        storage_used_pct: (h.storage_used_gb / h.storage_total_gb) * 100,
        battery_health_pct: h.battery_health_pct,
        duplicates_mb: 480,
        junk_mb: 890,
        threats: h.issues_found,
        platform: 'android',
      });
      setRecs(r);
    } catch (e) { console.log(e); }
    finally { setLoadingRecs(false); }
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (justLoggedIn) {
      const t = setTimeout(() => clearJustLoggedIn(), 5000);
      return () => clearTimeout(t);
    }
  }, [justLoggedIn]);
  useFocusEffect(React.useCallback(() => {
    getDeviceId().then((id) => Promise.all([api.streak(), api.forecast()]).then(([s, f]) => {
      setStreak(s.current_streak_weeks);
      setForecastDays(f.days_until_full);
    }).catch(() => {}));
  }, []));
  useEffect(() => { if (health && !recs) loadRecs(health); }, [health]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    if (health) await loadRecs(health);
    setRefreshing(false);
  };

  const onSmartScan = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    router.push('/smart-scan');
  };

  if (!health) {
    return (
      <View style={[styles.container, { alignItems: 'center', justifyContent: 'center' }]}>
        <ActivityIndicator color={theme.color.brand} />
      </View>
    );
  }

  const storagePct = Math.round((health.storage_used_gb / health.storage_total_gb) * 100);
  const stats = [
    { label: 'Storage', value: `${storagePct}%`, sub: `${health.storage_used_gb.toFixed(1)} / ${health.storage_total_gb} GB`, icon: 'server-outline' as const, color: theme.color.info, route: '/insights' },
    { label: 'Memory', value: `${health.ram_used_pct}%`, sub: 'RAM in use', icon: 'hardware-chip-outline' as const, color: '#8B5CF6', route: null },
    { label: 'Battery', value: `${health.battery_pct}%`, sub: `${health.battery_health_pct}% health`, icon: 'battery-half-outline' as const, color: theme.color.warning, route: '/insights' },
    { label: 'Security', value: 'Safe', sub: health.security_status, icon: 'shield-checkmark-outline' as const, color: theme.color.brand, route: '/insights' },
  ];

  return (
    <View style={styles.container} testID="home-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <ScrollView
          contentContainerStyle={{ paddingBottom: 140 }}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.color.brand} />}
        >
          {/* Header */}
          <View style={styles.header}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <VLogo size={38} glow={false} />
              <View>
                <Text style={styles.hello}>DevicePulse</Text>
                <Text style={styles.subHello}>{health.status}</Text>
              </View>
            </View>
            <Pressable onPress={() => router.push('/paywall')} testID="header-pro-button">
              <LinearGradient colors={theme.gradients.brand} style={styles.proBadge} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}>
                <Ionicons name="sparkles" size={12} color={theme.color.onBrand} />
                <Text style={styles.proBadgeText}>Pro</Text>
              </LinearGradient>
            </Pressable>
          </View>

          {/* Welcome back banner */}
          {justLoggedIn && user && (
            <Animated.View entering={FadeInDown} style={styles.welcomeBanner} testID="welcome-banner">
              <View style={styles.welcomeIcon}>
                <Ionicons name="hand-right" size={18} color={theme.color.brand} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.welcomeTitle}>Welcome back, {user.name?.split(' ')[0] || 'there'}!</Text>
                <Text style={styles.welcomeBody}>
                  {streak != null && streak > 0 ? `🔥 You're on a ${streak}-week streak — keep it going.` : 'Run a Smart Scan to start your streak.'}
                </Text>
              </View>
              <Pressable onPress={clearJustLoggedIn} hitSlop={8} testID="welcome-dismiss">
                <Ionicons name="close" size={18} color={theme.color.onSurface3} />
              </Pressable>
            </Animated.View>
          )}

          {/* Hero Ring */}
          <GlassCard style={styles.hero} testID="home-hero-card">
            <View style={{ alignItems: 'center' }}>
              <Pressable onPress={() => router.push('/trends')} testID="home-health-ring-btn">
                <HealthRing score={health.score} testID="home-health-ring" />
              </Pressable>
              <Text style={styles.heroSubtitle}>
                {health.issues_found} items can be optimized
              </Text>
              <Pressable style={styles.scanBtn} onPress={onSmartScan} testID="smart-scan-button">
                <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
                <Ionicons name="scan" size={20} color={theme.color.onBrand} />
                <Text style={styles.scanBtnText}>Run Smart Scan</Text>
              </Pressable>
            </View>
          </GlassCard>

          {/* Smart reminder banner */}
          {storagePct >= 70 && (
            <Pressable style={styles.reminderBanner} onPress={() => router.push('/smart-scan')} testID="home-reminder-banner">
              <View style={styles.reminderIcon}>
                <Ionicons name="notifications" size={18} color={theme.color.warning} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.reminderTitle}>Storage is filling up</Text>
                <Text style={styles.reminderBody}>You&apos;re at {storagePct}% — a quick scan can free up space.</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={theme.color.onSurface3} />
            </Pressable>
          )}

          {/* Quick access: Streak + Forecast */}
          <View style={styles.quickRow}>
            <Pressable style={styles.quickCard} onPress={() => router.push('/streak')} testID="home-streak-card">
              <View style={[styles.quickIcon, { backgroundColor: '#F59E0B22' }]}>
                <Ionicons name="flame" size={20} color={theme.color.warning} />
              </View>
              <Text style={styles.quickLabel}>Streak</Text>
              <Text style={styles.quickValue}>{streak != null ? `${streak}wk` : '—'}</Text>
            </Pressable>
            <Pressable style={styles.quickCard} onPress={() => router.push('/forecast')} testID="home-forecast-card">
              <View style={[styles.quickIcon, { backgroundColor: theme.color.info + '22' }]}>
                <Ionicons name="trending-up" size={20} color={theme.color.info} />
              </View>
              <Text style={styles.quickLabel}>Until full</Text>
              <Text style={styles.quickValue}>{forecastDays != null ? `${forecastDays}d` : '—'}</Text>
            </Pressable>
          </View>

          {/* Stat grid */}
          <View style={styles.statGrid}>
            {stats.map((s) => (
              <Pressable
                key={s.label}
                style={styles.statCard}
                onPress={() => s.route && router.push(s.route as any)}
                testID={`stat-card-${s.label.toLowerCase()}`}
              >
                <View style={[styles.statIcon, { backgroundColor: s.color + '22' }]}>
                  <Ionicons name={s.icon} size={20} color={s.color} />
                </View>
                <Text style={styles.statValue}>{s.value}</Text>
                <Text style={styles.statLabel}>{s.label}</Text>
                <Text style={styles.statSub}>{s.sub}</Text>
              </Pressable>
            ))}
          </View>

          {/* AI Recommendations */}
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>AI Recommendations</Text>
            <View style={styles.aiTag}>
              <Ionicons name="sparkles" size={11} color={theme.color.brand} />
              <Text style={styles.aiTagText}>Claude Sonnet</Text>
            </View>
          </View>

          {loadingRecs && !recs && (
            <View style={{ paddingVertical: 20, alignItems: 'center' }}>
              <ActivityIndicator color={theme.color.brand} />
              <Text style={{ color: theme.color.onSurface2, marginTop: 8, fontSize: 12 }}>Analyzing your device…</Text>
            </View>
          )}

          {recs?.map((r, i) => (
            <GlassCard key={i} style={styles.recCard} testID={`recommendation-${i}`}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <View style={[styles.impactDot, {
                  backgroundColor: r.impact === 'high' ? theme.color.brand : r.impact === 'medium' ? theme.color.warning : theme.color.info,
                }]} />
                <Text style={styles.recTitle}>{r.title}</Text>
              </View>
              <Text style={styles.recBody}>{r.description}</Text>
            </GlassCard>
          ))}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.md, paddingBottom: theme.space.md },
  hello: { color: theme.color.onSurface, fontSize: 18, fontWeight: '700' },
  subHello: { color: theme.color.onSurface2, fontSize: 12 },
  proBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: theme.radius.pill },
  proBadgeText: { color: theme.color.onBrand, fontSize: 12, fontWeight: '700' },
  hero: { marginHorizontal: theme.space.lg, marginTop: theme.space.sm, paddingVertical: theme.space.xl },
  heroSubtitle: { color: theme.color.onSurface2, fontSize: 13, marginTop: theme.space.md },
  scanBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    marginTop: theme.space.lg, paddingHorizontal: 28, paddingVertical: 14, borderRadius: theme.radius.pill, overflow: 'hidden',
  },
  scanBtnText: { color: theme.color.onBrand, fontSize: 15, fontWeight: '700' },
  statGrid: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: theme.space.md, marginTop: theme.space.md, gap: theme.space.sm },
  statCard: {
    width: '48%', backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg,
    padding: theme.space.lg, borderWidth: 1, borderColor: theme.color.border,
  },
  statIcon: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  statValue: { color: theme.color.onSurface, fontSize: 22, fontWeight: '800', letterSpacing: -0.5 },
  statLabel: { color: theme.color.onSurface, fontSize: 13, fontWeight: '600', marginTop: 2 },
  statSub: { color: theme.color.onSurface3, fontSize: 11, marginTop: 2 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, marginTop: theme.space.xl, marginBottom: theme.space.sm },
  sectionTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  aiTag: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: theme.color.brand3, paddingHorizontal: 8, paddingVertical: 4, borderRadius: theme.radius.pill },
  aiTagText: { color: theme.color.brand, fontSize: 10, fontWeight: '700' },
  recCard: { marginHorizontal: theme.space.lg, marginTop: theme.space.sm },
  recTitle: { color: theme.color.onSurface, fontSize: 14, fontWeight: '700', flex: 1 },
  recBody: { color: theme.color.onSurface2, fontSize: 13, marginTop: 6, lineHeight: 19 },
  impactDot: { width: 8, height: 8, borderRadius: 4 },
  reminderBanner: { flexDirection: 'row', alignItems: 'center', gap: 12, marginHorizontal: theme.space.lg, marginTop: theme.space.md, padding: theme.space.md, backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.warning + '55' },
  reminderIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: theme.color.warning + '22', alignItems: 'center', justifyContent: 'center' },
  reminderTitle: { color: theme.color.onSurface, fontSize: 14, fontWeight: '700' },
  reminderBody: { color: theme.color.onSurface2, fontSize: 12, marginTop: 2 },
  quickRow: { flexDirection: 'row', gap: theme.space.sm, paddingHorizontal: theme.space.lg, marginTop: theme.space.md },
  quickCard: { flex: 1, backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.md, borderWidth: 1, borderColor: theme.color.border, flexDirection: 'row', alignItems: 'center', gap: 10 },
  quickIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  quickLabel: { color: theme.color.onSurface2, fontSize: 13, flex: 1 },
  quickValue: { color: theme.color.onSurface, fontSize: 18, fontWeight: '800' },
  welcomeBanner: { flexDirection: 'row', alignItems: 'center', gap: 12, marginHorizontal: theme.space.lg, marginBottom: theme.space.sm, padding: theme.space.md, backgroundColor: theme.color.brand3, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.brand + '55' },
  welcomeIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: 'rgba(16,185,129,0.18)', alignItems: 'center', justifyContent: 'center' },
  welcomeTitle: { color: theme.color.onSurface, fontSize: 14, fontWeight: '700' },
  welcomeBody: { color: theme.color.onSurface2, fontSize: 12, marginTop: 2 },
});
