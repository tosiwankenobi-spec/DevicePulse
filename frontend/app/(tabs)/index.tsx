import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Battery from 'expo-battery';
import * as Haptics from 'expo-haptics';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { GlassCard } from '@/src/components/GlassCard';
import { HealthRing } from '@/src/components/HealthRing';
import { VLogo } from '@/src/components/VLogo';
import { scanLocalDevice, type LocalDeviceScan } from '@/src/deviceStorage';
import { useAuth } from '@/src/AuthContext';
import { theme } from '@/src/theme';

function formatMb(mb: number): string {
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(1)} MB`;
}

function statusFor(score: number): string {
  if (score >= 85) return 'Storage looks healthy';
  if (score >= 65) return 'Storage needs attention';
  return 'Storage is running low';
}

export default function Home() {
  const router = useRouter();
  const { user, justLoggedIn, clearJustLoggedIn } = useAuth();
  const [device, setDevice] = useState<LocalDeviceScan | null>(null);
  const [batteryLevel, setBatteryLevel] = useState<number | null>(null);
  const [powerSaver, setPowerSaver] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setDevice(scanLocalDevice());
    try {
      const power = await Battery.getPowerStateAsync();
      setBatteryLevel(power.batteryLevel >= 0 ? Math.round(power.batteryLevel * 100) : null);
      setPowerSaver(power.lowPowerMode);
    } catch {
      setBatteryLevel(null);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  useEffect(() => {
    if (!justLoggedIn) return;
    const timer = setTimeout(clearJustLoggedIn, 5000);
    return () => clearTimeout(timer);
  }, [clearJustLoggedIn, justLoggedIn]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  if (!device) {
    return <View style={[styles.container, styles.center]}><ActivityIndicator color={theme.color.brand} /></View>;
  }

  const storagePct = device.storage_total_mb > 0 ? Math.round((device.storage_used_mb / device.storage_total_mb) * 100) : 0;
  const score = device.health_before;
  const status = statusFor(score);

  const onSmartScan = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    router.push('/smart-scan');
  };

  return (
    <View style={styles.container} testID="home-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <ScrollView contentContainerStyle={{ paddingBottom: 140 }} showsVerticalScrollIndicator={false} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.color.brand} />}>
          <View style={styles.header}>
            <View style={styles.brandRow}>
              <VLogo size={38} glow={false} />
              <View>
                <Text style={styles.hello}>DevicePulse</Text>
                <Text style={styles.subHello}>{status}</Text>
              </View>
            </View>
            <Pressable onPress={() => router.push('/paywall')} testID="header-pro-button">
              <LinearGradient colors={theme.gradients.brand} style={styles.proBadge} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}>
                <Ionicons name="sparkles" size={12} color={theme.color.onBrand} />
                <Text style={styles.proBadgeText}>Pro</Text>
              </LinearGradient>
            </Pressable>
          </View>

          <Animated.View entering={FadeInDown}>
            <View style={styles.pulseCard}>
              <View style={styles.pulseIconWrap}><Ionicons name="server-outline" size={22} color={theme.color.brand} /></View>
              <View style={{ flex: 1 }}>
                <Text style={styles.pulseTitle}>Live Storage Check</Text>
                <Text style={styles.pulseHeadline}>{formatMb(device.storage_free_mb)} available to apps</Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={styles.pulseScore}>{score}</Text>
                <Text style={styles.pulseScoreLabel}>Storage score</Text>
              </View>
            </View>
          </Animated.View>

          {justLoggedIn && user && (
            <Animated.View entering={FadeInDown} style={styles.welcomeBanner} testID="welcome-banner">
              <View style={styles.welcomeIcon}><Ionicons name="hand-right" size={18} color={theme.color.brand} /></View>
              <View style={{ flex: 1 }}>
                <Text style={styles.welcomeTitle}>Welcome back, {user.name?.split(' ')[0] || 'there'}!</Text>
                <Text style={styles.welcomeBody}>Your live device readings are ready.</Text>
              </View>
              <Pressable onPress={clearJustLoggedIn} hitSlop={8}><Ionicons name="close" size={18} color={theme.color.onSurface3} /></Pressable>
            </Animated.View>
          )}

          <GlassCard style={styles.hero} testID="home-hero-card">
            <View style={{ alignItems: 'center' }}>
              <HealthRing score={score} testID="home-health-ring" />
              <Text style={styles.heroSubtitle}>Score based on app-accessible free storage</Text>
              <Pressable style={styles.scanBtn} onPress={onSmartScan} testID="smart-scan-button">
                <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
                <Ionicons name="scan" size={20} color={theme.color.onBrand} />
                <Text style={styles.scanBtnText}>Run Storage Check</Text>
              </Pressable>
            </View>
          </GlassCard>

          {storagePct >= 85 && (
            <Pressable style={styles.notice} onPress={() => router.push('/(tabs)/insights')}>
              <Ionicons name="warning-outline" size={20} color={theme.color.warning} />
              <View style={{ flex: 1 }}>
                <Text style={styles.noticeTitle}>Storage is {storagePct}% full</Text>
                <Text style={styles.noticeBody}>Review files with Android&apos;s protected storage manager.</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={theme.color.onSurface3} />
            </Pressable>
          )}

          <View style={styles.statGrid}>
            <StatCard label="Storage" value={`${storagePct}%`} sub={`${formatMb(device.storage_free_mb)} free`} icon="server-outline" color={theme.color.info} onPress={() => router.push('/(tabs)/insights')} />
            <StatCard label="Battery" value={batteryLevel == null ? '—' : `${batteryLevel}%`} sub={powerSaver ? 'Power saver on' : 'Live reading'} icon="battery-half-outline" color={theme.color.warning} onPress={() => router.push('/(tabs)/insights')} />
            <StatCard label="App cache" value={formatMb(device.cache_mb)} sub="DevicePulse only" icon="flash-outline" color={theme.color.brand} onPress={onSmartScan} />
            <StatCard label="Security" value="Review" sub="Android settings" icon="shield-checkmark-outline" color={theme.color.brand} onPress={() => router.push('/(tabs)/insights')} />
          </View>

          <View style={styles.transparencyCard}>
            <Ionicons name="lock-closed" size={22} color={theme.color.brand} />
            <View style={{ flex: 1 }}>
              <Text style={styles.transparencyTitle}>Truthful by design</Text>
              <Text style={styles.transparencyBody}>DevicePulse reports measurements it can verify and sends protected actions to Android for your approval.</Text>
            </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

function StatCard({ label, value, sub, icon, color, onPress }: { label: string; value: string; sub: string; icon: keyof typeof Ionicons.glyphMap; color: string; onPress: () => void }) {
  return (
    <Pressable style={styles.statCard} onPress={onPress}>
      <View style={[styles.statIcon, { backgroundColor: color + '22' }]}><Ionicons name={icon} size={20} color={color} /></View>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statSub}>{sub}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  center: { alignItems: 'center', justifyContent: 'center' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.md, paddingBottom: theme.space.md },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  hello: { color: theme.color.onSurface, fontSize: 18, fontWeight: '700' },
  subHello: { color: theme.color.onSurface2, fontSize: 12 },
  proBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: theme.radius.pill },
  proBadgeText: { color: theme.color.onBrand, fontSize: 12, fontWeight: '700' },
  pulseCard: { flexDirection: 'row', alignItems: 'center', gap: 12, marginHorizontal: theme.space.lg, marginBottom: theme.space.sm, padding: theme.space.md, backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.border },
  pulseIconWrap: { width: 36, height: 36, borderRadius: 10, backgroundColor: theme.color.brand3, alignItems: 'center', justifyContent: 'center' },
  pulseTitle: { color: theme.color.onSurface, fontSize: 13, fontWeight: '700' },
  pulseHeadline: { color: theme.color.onSurface2, fontSize: 12, marginTop: 2 },
  pulseScore: { color: theme.color.onSurface, fontSize: 20, fontWeight: '800' },
  pulseScoreLabel: { color: theme.color.onSurface3, fontSize: 10, marginTop: 1 },
  welcomeBanner: { flexDirection: 'row', alignItems: 'center', gap: 12, marginHorizontal: theme.space.lg, marginBottom: theme.space.sm, padding: theme.space.md, backgroundColor: theme.color.brand3, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.brand + '55' },
  welcomeIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: 'rgba(16,185,129,0.18)', alignItems: 'center', justifyContent: 'center' },
  welcomeTitle: { color: theme.color.onSurface, fontSize: 14, fontWeight: '700' },
  welcomeBody: { color: theme.color.onSurface2, fontSize: 12, marginTop: 2 },
  hero: { marginHorizontal: theme.space.lg, marginTop: theme.space.sm, paddingVertical: theme.space.xl },
  heroSubtitle: { color: theme.color.onSurface2, fontSize: 13, marginTop: theme.space.md },
  scanBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: theme.space.lg, paddingHorizontal: 28, paddingVertical: 14, borderRadius: theme.radius.pill, overflow: 'hidden' },
  scanBtnText: { color: theme.color.onBrand, fontSize: 15, fontWeight: '700' },
  notice: { flexDirection: 'row', alignItems: 'center', gap: 12, marginHorizontal: theme.space.lg, marginTop: theme.space.md, padding: theme.space.md, backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.warning + '66' },
  noticeTitle: { color: theme.color.onSurface, fontSize: 14, fontWeight: '700' },
  noticeBody: { color: theme.color.onSurface2, fontSize: 12, marginTop: 2 },
  statGrid: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: theme.space.md, marginTop: theme.space.md, gap: theme.space.sm },
  statCard: { width: '48%', backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.lg, borderWidth: 1, borderColor: theme.color.border },
  statIcon: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  statValue: { color: theme.color.onSurface, fontSize: 22, fontWeight: '800', letterSpacing: -0.5 },
  statLabel: { color: theme.color.onSurface, fontSize: 13, fontWeight: '600', marginTop: 2 },
  statSub: { color: theme.color.onSurface3, fontSize: 11, marginTop: 2 },
  transparencyCard: { flexDirection: 'row', gap: 12, marginHorizontal: theme.space.lg, marginTop: theme.space.xl, backgroundColor: theme.color.brand3, borderRadius: theme.radius.lg, padding: theme.space.lg },
  transparencyTitle: { color: theme.color.onSurface, fontSize: 14, fontWeight: '700' },
  transparencyBody: { color: theme.color.onSurface2, fontSize: 12, lineHeight: 18, marginTop: 3 },
});
