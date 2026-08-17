import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { api } from '@/src/api';
import { getDeviceId } from '@/src/device';
import { theme } from '@/src/theme';

const DAYS = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'Now'];

export default function Streak() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const id = await getDeviceId();
      try { setData(await api.streak(id)); } catch (e) { console.log(e); }
      finally { setLoading(false); }
    })();
  }, []);

  return (
    <View style={styles.container} testID="streak-screen">
      <LinearGradient colors={theme.gradients.hero2} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="streak-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Cleanup Streak</Text>
          <View style={{ width: 26 }} />
        </View>

        {loading ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : (
          <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
            {/* Flame hero */}
            <View style={styles.flameWrap}>
              <LinearGradient colors={['#F59E0B', '#EF4444']} style={styles.flameCircle}>
                <Ionicons name="flame" size={56} color="#fff" />
              </LinearGradient>
              <Text style={styles.streakNumber} testID="streak-count">{data.current_streak_weeks}</Text>
              <Text style={styles.streakLabel}>week streak</Text>
              <Text style={styles.streakSub}>
                {data.this_week_done ? "You've cleaned up this week — keep it going!" : 'Run a scan this week to extend your streak.'}
              </Text>
            </View>

            {/* Week grid */}
            <Text style={styles.section}>Last 8 weeks</Text>
            <View style={styles.weekRow}>
              {data.week_grid.map((w: any, i: number) => (
                <View key={i} style={{ alignItems: 'center', flex: 1 }}>
                  <View style={[styles.weekDot, w.active && styles.weekDotActive]}>
                    {w.active && <Ionicons name="checkmark" size={14} color={theme.color.onBrand} />}
                  </View>
                  <Text style={styles.weekLabel}>{DAYS[i]}</Text>
                </View>
              ))}
            </View>

            {/* Milestones */}
            <Text style={styles.section}>Badges</Text>
            <View style={styles.badgeGrid}>
              {data.milestones.map((m: any, i: number) => (
                <Animated.View key={m.key} entering={FadeInDown.delay(i * 60)} style={styles.badgeCard} testID={`badge-${m.key}`}>
                  <View style={[styles.badgeIcon, m.unlocked ? styles.badgeIconOn : styles.badgeIconOff]}>
                    <Ionicons name={m.icon} size={26} color={m.unlocked ? theme.color.onBrand : theme.color.onSurface3} />
                  </View>
                  <Text style={[styles.badgeLabel, !m.unlocked && { color: theme.color.onSurface3 }]}>{m.label}</Text>
                  {!m.unlocked && (
                    <View style={styles.lockRow}>
                      <Ionicons name="lock-closed" size={10} color={theme.color.onSurface3} />
                      <Text style={styles.lockText}>Locked</Text>
                    </View>
                  )}
                </Animated.View>
              ))}
            </View>

            <Pressable style={styles.cta} onPress={() => router.push('/smart-scan')} testID="streak-scan-cta">
              <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
              <Ionicons name="flame" size={18} color={theme.color.onBrand} />
              <Text style={styles.ctaText}>Keep the streak alive</Text>
            </Pressable>
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
  flameWrap: { alignItems: 'center', marginTop: theme.space.md },
  flameCircle: { width: 110, height: 110, borderRadius: 55, alignItems: 'center', justifyContent: 'center' },
  streakNumber: { color: theme.color.onSurface, fontSize: 56, fontWeight: '800', marginTop: theme.space.md, letterSpacing: -2 },
  streakLabel: { color: theme.color.onSurface2, fontSize: 15, textTransform: 'uppercase', letterSpacing: 1.5, marginTop: -6 },
  streakSub: { color: theme.color.onSurface2, fontSize: 14, textAlign: 'center', marginTop: 12, lineHeight: 20, paddingHorizontal: theme.space.lg },
  section: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '700', letterSpacing: 1.1, textTransform: 'uppercase', marginTop: theme.space.xl, marginBottom: theme.space.md },
  weekRow: { flexDirection: 'row', backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.md, borderWidth: 1, borderColor: theme.color.border },
  weekDot: { width: 32, height: 32, borderRadius: 16, backgroundColor: theme.color.surface3, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: theme.color.border },
  weekDotActive: { backgroundColor: theme.color.brand, borderColor: theme.color.brand },
  weekLabel: { color: theme.color.onSurface3, fontSize: 10, marginTop: 6 },
  badgeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: theme.space.sm },
  badgeCard: { width: '31.5%', backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, padding: theme.space.md, alignItems: 'center', borderWidth: 1, borderColor: theme.color.border, gap: 6 },
  badgeIcon: { width: 52, height: 52, borderRadius: 26, alignItems: 'center', justifyContent: 'center' },
  badgeIconOn: { backgroundColor: theme.color.brand },
  badgeIconOff: { backgroundColor: theme.color.surface3 },
  badgeLabel: { color: theme.color.onSurface, fontSize: 11, fontWeight: '600', textAlign: 'center' },
  lockRow: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  lockText: { color: theme.color.onSurface3, fontSize: 10 },
  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 54, borderRadius: theme.radius.pill, overflow: 'hidden', marginTop: theme.space.xl },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
});
