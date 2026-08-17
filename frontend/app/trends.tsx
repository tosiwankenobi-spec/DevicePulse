import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator, useWindowDimensions } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { TrendChart } from '@/src/components/TrendChart';
import { api } from '@/src/api';
import { getDeviceId } from '@/src/device';
import { theme } from '@/src/theme';

export default function Trends() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const id = await getDeviceId();
      try { setData(await api.healthTrend(id)); } catch (e) { console.log(e); }
      finally { setLoading(false); }
    })();
  }, []);

  const chartWidth = width - theme.space.lg * 2 - theme.space.lg * 2;
  const positive = data && data.change >= 0;

  return (
    <View style={styles.container} testID="trends-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="trends-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Health Trends</Text>
          <View style={{ width: 26 }} />
        </View>

        {loading || !data ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : (
          <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
            <View style={styles.headRow}>
              <View>
                <Text style={styles.currentLabel}>Current health</Text>
                <Text style={styles.currentScore} testID="trend-current">{data.current}</Text>
              </View>
              <View style={[styles.changeBadge, { backgroundColor: (positive ? theme.color.brand : theme.color.error) + '22' }]}>
                <Ionicons name={positive ? 'trending-up' : 'trending-down'} size={16} color={positive ? theme.color.brand : theme.color.error} />
                <Text style={[styles.changeText, { color: positive ? theme.color.brand : theme.color.error }]}>
                  {positive ? '+' : ''}{data.change} in 8 weeks
                </Text>
              </View>
            </View>

            <View style={styles.chartCard}>
              <TrendChart points={data.points} width={chartWidth} height={180} />
              <View style={styles.xLabels}>
                {data.points.map((p: any, i: number) => (
                  (i % 2 === 0) ? <Text key={i} style={styles.xLabel}>{p.label}</Text> : <View key={i} style={{ flex: 1 }} />
                ))}
              </View>
            </View>

            <View style={styles.legend}>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: theme.color.brand }]} />
                <Text style={styles.legendText}>Week you cleaned up</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: theme.color.surface, borderWidth: 2, borderColor: theme.color.brand }]} />
                <Text style={styles.legendText}>No cleanup</Text>
              </View>
            </View>

            <View style={styles.insightCard}>
              <View style={styles.insightIcon}>
                <Ionicons name={positive ? 'sparkles' : 'alert-circle'} size={20} color={theme.color.brand} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.insightTitle}>{positive ? "You're trending up!" : 'Room to improve'}</Text>
                <Text style={styles.insightBody}>
                  {positive
                    ? 'Your consistent cleanups are paying off. Keep the weekly habit to stay in the green.'
                    : 'A regular weekly Smart Scan will steadily push your health score higher.'}
                </Text>
              </View>
            </View>

            <Pressable style={styles.cta} onPress={() => router.push('/smart-scan')} testID="trends-scan-cta">
              <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
              <Text style={styles.ctaText}>Boost my score</Text>
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
  headRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.space.lg },
  currentLabel: { color: theme.color.onSurface2, fontSize: 13 },
  currentScore: { color: theme.color.onSurface, fontSize: 44, fontWeight: '800', letterSpacing: -1.5 },
  changeBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: theme.radius.pill },
  changeText: { fontSize: 13, fontWeight: '700' },
  chartCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.lg, borderWidth: 1, borderColor: theme.color.border },
  xLabels: { flexDirection: 'row', marginTop: 8 },
  xLabel: { color: theme.color.onSurface3, fontSize: 10, flex: 2, textAlign: 'left' },
  legend: { flexDirection: 'row', gap: theme.space.lg, marginTop: theme.space.md, justifyContent: 'center' },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { color: theme.color.onSurface2, fontSize: 12 },
  insightCard: { flexDirection: 'row', gap: 12, alignItems: 'center', backgroundColor: theme.color.brand3, borderRadius: theme.radius.md, padding: theme.space.md, marginTop: theme.space.lg },
  insightIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: 'rgba(16,185,129,0.15)', alignItems: 'center', justifyContent: 'center' },
  insightTitle: { color: theme.color.onSurface, fontSize: 14, fontWeight: '700' },
  insightBody: { color: theme.color.onSurface2, fontSize: 13, marginTop: 2, lineHeight: 18 },
  cta: { height: 54, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden', marginTop: theme.space.xl },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
});
