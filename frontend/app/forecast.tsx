import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/api';
import { getDeviceId } from '@/src/device';
import { theme } from '@/src/theme';

export default function Forecast() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const id = await getDeviceId();
      try { setData(await api.forecast()); } catch (e) { console.log(e); }
      finally { setLoading(false); }
    })();
  }, []);

  const soon = data && data.days_until_full <= 30;

  return (
    <View style={styles.container} testID="forecast-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="forecast-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Storage Forecast</Text>
          <View style={{ width: 26 }} />
        </View>

        {loading || !data ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : (
          <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
            {/* Headline */}
            <LinearGradient
              colors={soon ? theme.gradients.danger : theme.gradients.hero2}
              style={styles.headline}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
            >
              <Ionicons name={soon ? 'warning' : 'trending-up'} size={30} color={soon ? '#fff' : theme.color.brand} />
              <Text style={styles.headlineNum} testID="forecast-days">~{data.days_until_full} days</Text>
              <Text style={styles.headlineLabel}>until your storage is full</Text>
              <Text style={styles.headlineDate}>Projected: {data.projected_full_date}</Text>
            </LinearGradient>

            {/* Current state */}
            <View style={styles.statRow}>
              <View style={[styles.statCard, styles.statHalf]}>
                <Text style={styles.statLabel}>Free now</Text>
                <Text style={styles.statValue}>{data.free_gb} GB</Text>
              </View>
              <View style={[styles.statCard, styles.statHalf]}>
                <Text style={styles.statLabel}>Filling at</Text>
                <Text style={styles.statValue}>{data.daily_growth_gb}<Text style={styles.statUnit}> GB/day</Text></Text>
              </View>
            </View>

            {/* Projection chart (bars) */}
            <Text style={styles.section}>Projected fill</Text>
            <View style={styles.chartCard}>
              <View style={styles.chart}>
                {data.projection.map((p: any, i: number) => (
                  <View key={i} style={styles.barCol}>
                    <View style={styles.barTrack}>
                      <View style={[styles.barFill, {
                        height: `${p.pct}%`,
                        backgroundColor: p.pct >= 90 ? theme.color.error : p.pct >= 75 ? theme.color.warning : theme.color.brand,
                      }]} />
                    </View>
                    <Text style={styles.barLabel}>{p.day}d</Text>
                  </View>
                ))}
              </View>
              <Text style={styles.chartCaption}>Days from now →</Text>
            </View>

            {/* Tip */}
            <View style={styles.tip}>
              <View style={styles.tipIcon}>
                <Ionicons name="bulb" size={18} color={theme.color.brand} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.tipTitle}>Stay ahead of it</Text>
                <Text style={styles.tipBody}>
                  A weekly Smart Scan clears ~1.5 GB and can push your "full" date back by weeks.
                </Text>
              </View>
            </View>

            <Pressable style={styles.cta} onPress={() => router.push('/smart-scan')} testID="forecast-scan-cta">
              <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
              <Text style={styles.ctaText}>Free up space now</Text>
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
  headline: { borderRadius: theme.radius.lg, padding: theme.space.xl, alignItems: 'center' },
  headlineNum: { color: theme.color.onSurface, fontSize: 42, fontWeight: '800', marginTop: 10, letterSpacing: -1.5 },
  headlineLabel: { color: theme.color.onSurface2, fontSize: 14, marginTop: 2 },
  headlineDate: { color: theme.color.onSurface3, fontSize: 12, marginTop: 8 },
  statRow: { flexDirection: 'row', gap: theme.space.md, marginTop: theme.space.md },
  statCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, padding: theme.space.lg, borderWidth: 1, borderColor: theme.color.border },
  statHalf: { flex: 1 },
  statLabel: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '600' },
  statValue: { color: theme.color.onSurface, fontSize: 24, fontWeight: '800', marginTop: 4 },
  statUnit: { color: theme.color.onSurface3, fontSize: 13, fontWeight: '500' },
  section: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '700', letterSpacing: 1.1, textTransform: 'uppercase', marginTop: theme.space.xl, marginBottom: theme.space.md },
  chartCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.md, borderWidth: 1, borderColor: theme.color.border },
  chart: { flexDirection: 'row', height: 160, alignItems: 'flex-end', gap: 4 },
  barCol: { flex: 1, alignItems: 'center', height: '100%', justifyContent: 'flex-end' },
  barTrack: { width: '70%', flex: 1, backgroundColor: theme.color.surface3, borderRadius: 4, justifyContent: 'flex-end', overflow: 'hidden' },
  barFill: { width: '100%', borderRadius: 4 },
  barLabel: { color: theme.color.onSurface3, fontSize: 9, marginTop: 4 },
  chartCaption: { color: theme.color.onSurface3, fontSize: 11, textAlign: 'right', marginTop: 8 },
  tip: { flexDirection: 'row', gap: 12, alignItems: 'center', backgroundColor: theme.color.brand3, borderRadius: theme.radius.md, padding: theme.space.md, marginTop: theme.space.lg },
  tipIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: 'rgba(16,185,129,0.15)', alignItems: 'center', justifyContent: 'center' },
  tipTitle: { color: theme.color.onSurface, fontSize: 14, fontWeight: '700' },
  tipBody: { color: theme.color.onSurface2, fontSize: 13, marginTop: 2, lineHeight: 18 },
  cta: { height: 54, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden', marginTop: theme.space.xl },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
});
