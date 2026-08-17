import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/api';
import { theme } from '@/src/theme';

type Tab = 'storage' | 'battery' | 'security';

export default function Insights() {
  const [tab, setTab] = useState<Tab>('storage');
  const [storage, setStorage] = useState<any>(null);
  const [battery, setBattery] = useState<any>(null);
  const [security, setSecurity] = useState<any>(null);

  useEffect(() => {
    api.storage().then(setStorage).catch(() => {});
    api.battery().then(setBattery).catch(() => {});
    api.security().then(setSecurity).catch(() => {});
  }, []);

  return (
    <View style={styles.container} testID="insights-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <View style={styles.header}>
          <Text style={styles.title}>Insights</Text>
          <Text style={styles.sub}>Deep-dive analytics for your device</Text>
        </View>

        {/* Segmented control (chip row) */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
        >
          {(['storage', 'battery', 'security'] as Tab[]).map((t) => (
            <Pressable
              key={t}
              onPress={() => setTab(t)}
              style={[styles.chip, tab === t && styles.chipActive]}
              testID={`insight-tab-${t}`}
            >
              <Text style={[styles.chipText, tab === t && styles.chipTextActive]}>
                {t[0].toUpperCase() + t.slice(1)}
              </Text>
            </Pressable>
          ))}
        </ScrollView>

        <ScrollView contentContainerStyle={{ paddingBottom: 140, paddingHorizontal: theme.space.lg }} showsVerticalScrollIndicator={false}>
          {tab === 'storage' && (
            storage ? <StorageView data={storage} /> : <Loader />
          )}
          {tab === 'battery' && (
            battery ? <BatteryView data={battery} /> : <Loader />
          )}
          {tab === 'security' && (
            security ? <SecurityView data={security} /> : <Loader />
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const Loader = () => (
  <View style={{ paddingVertical: 60, alignItems: 'center' }}>
    <ActivityIndicator color={theme.color.brand} />
  </View>
);

const StorageView = ({ data }: { data: any }) => {
  const usedPct = Math.round((data.used_gb / data.total_gb) * 100);
  const router = useRouter();
  return (
    <View>
      <View style={styles.card}>
        <Text style={styles.cardLabel}>Total Storage</Text>
        <Text style={styles.cardValue}>{data.used_gb.toFixed(1)} <Text style={styles.cardUnit}>/ {data.total_gb} GB</Text></Text>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${usedPct}%` }]} />
        </View>
        <Text style={styles.helperText}>{data.free_gb.toFixed(1)} GB free</Text>
      </View>

      <Pressable style={styles.forecastLink} onPress={() => router.push('/forecast')} testID="storage-forecast-link">
        <Ionicons name="trending-up" size={18} color={theme.color.info} />
        <Text style={styles.forecastLinkText}>See storage forecast</Text>
        <Ionicons name="chevron-forward" size={16} color={theme.color.onSurface3} />
      </Pressable>

      {/* Stacked horizontal bar */}
      <Text style={styles.sectionTitle}>Breakdown</Text>
      <View style={[styles.card, { paddingVertical: theme.space.md }]}>
        <View style={styles.stackedBar}>
          {data.breakdown.map((b: any, i: number) => (
            <View key={i} style={{ width: `${b.pct * 3}%`, height: '100%', backgroundColor: b.color }} />
          ))}
        </View>
        <View style={{ marginTop: theme.space.md, gap: 10 }}>
          {data.breakdown.map((b: any) => (
            <View key={b.category} style={styles.breakdownRow}>
              <View style={[styles.dot, { backgroundColor: b.color }]} />
              <Text style={styles.breakdownLabel}>{b.category}</Text>
              <Text style={styles.breakdownValue}>{b.size_gb.toFixed(1)} GB</Text>
            </View>
          ))}
        </View>
      </View>
    </View>
  );
};

const BatteryView = ({ data }: { data: any }) => (
  <View>
    <View style={styles.card}>
      <Text style={styles.cardLabel}>Battery Level</Text>
      <Text style={styles.cardValue}>{data.level}%</Text>
      <View style={styles.progressTrack}>
        <View style={[styles.progressFill, { width: `${data.level}%`, backgroundColor: theme.color.warning }]} />
      </View>
      <Text style={styles.helperText}>{data.time_to_empty_hours}h remaining • {data.temperature_c}°C</Text>
    </View>

    <View style={styles.gridRow}>
      <View style={[styles.card, styles.halfCard]}>
        <Text style={styles.miniLabel}>Health</Text>
        <Text style={styles.miniValue}>{data.health_pct}%</Text>
      </View>
      <View style={[styles.card, styles.halfCard]}>
        <Text style={styles.miniLabel}>Cycles</Text>
        <Text style={styles.miniValue}>{data.cycle_count}</Text>
      </View>
    </View>

    <Text style={styles.sectionTitle}>Top Drain Apps</Text>
    <View style={styles.card}>
      {data.drain_apps.map((app: any, i: number) => (
        <View key={i} style={styles.appRow}>
          <Text style={{ fontSize: 20 }}>{app.icon}</Text>
          <Text style={styles.appName}>{app.name}</Text>
          <View style={styles.appPctBar}>
            <View style={[styles.appPctFill, { width: `${app.pct * 4}%` }]} />
          </View>
          <Text style={styles.appPct}>{app.pct}%</Text>
        </View>
      ))}
    </View>
  </View>
);

const SecurityView = ({ data }: { data: any }) => (
  <View>
    <LinearGradient
      colors={data.status === 'safe' ? theme.gradients.brand : theme.gradients.danger}
      style={styles.securityHero}
      start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
    >
      <Ionicons name={data.status === 'safe' ? 'shield-checkmark' : 'alert-circle'} size={44} color={theme.color.onBrand} />
      <Text style={styles.securityHeroTitle}>{data.status === 'safe' ? 'Your device is safe' : 'Threats detected'}</Text>
      <Text style={styles.securityHeroSub}>Scanned {data.apps_scanned} apps · {data.permissions_reviewed} permissions reviewed</Text>
    </LinearGradient>

    <Text style={styles.sectionTitle}>{data.threats.length > 0 ? 'Items to review' : 'No threats found'}</Text>
    {data.threats.map((t: any) => (
      <View key={t.id} style={styles.card}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <View style={[styles.severityBadge, {
            backgroundColor: t.severity === 'high' ? theme.color.error + '33' : t.severity === 'medium' ? theme.color.warning + '33' : theme.color.info + '33'
          }]}>
            <Text style={[styles.severityText, {
              color: t.severity === 'high' ? theme.color.error : t.severity === 'medium' ? theme.color.warning : theme.color.info
            }]}>{t.severity.toUpperCase()}</Text>
          </View>
          <Text style={styles.threatCategory}>{t.category}</Text>
        </View>
        <Text style={styles.threatTitle}>{t.title}</Text>
        <Text style={styles.threatBody}>{t.description}</Text>
      </View>
    ))}
  </View>
);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  header: { paddingHorizontal: theme.space.lg, paddingTop: theme.space.md, paddingBottom: theme.space.sm },
  title: { color: theme.color.onSurface, fontSize: 28, fontWeight: '800', letterSpacing: -0.5 },
  sub: { color: theme.color.onSurface2, fontSize: 13, marginTop: 2 },
  chipRow: { paddingHorizontal: theme.space.lg, paddingVertical: theme.space.sm, gap: 8, height: 56 },
  chip: { height: 36, paddingHorizontal: 16, borderRadius: theme.radius.pill, backgroundColor: theme.color.surface2, borderWidth: 1, borderColor: theme.color.border, alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  chipActive: { backgroundColor: theme.color.brand3, borderColor: theme.color.brand },
  chipText: { color: theme.color.onSurface2, fontSize: 13, fontWeight: '600' },
  chipTextActive: { color: theme.color.brand, fontWeight: '700' },
  card: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.lg, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.md },
  cardLabel: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.8 },
  cardValue: { color: theme.color.onSurface, fontSize: 32, fontWeight: '800', marginTop: 4, letterSpacing: -1 },
  cardUnit: { color: theme.color.onSurface3, fontSize: 15, fontWeight: '500' },
  progressTrack: { height: 8, borderRadius: 4, backgroundColor: theme.color.surface3, marginTop: theme.space.md, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: theme.color.brand, borderRadius: 4 },
  helperText: { color: theme.color.onSurface3, fontSize: 12, marginTop: 8 },
  forecastLink: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, padding: theme.space.md, borderWidth: 1, borderColor: theme.color.info + '44', marginBottom: theme.space.md },
  forecastLinkText: { color: theme.color.onSurface, fontSize: 14, fontWeight: '600', flex: 1 },
  sectionTitle: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '700', letterSpacing: 1.1, textTransform: 'uppercase', marginTop: theme.space.md, marginBottom: theme.space.sm },
  stackedBar: { height: 14, borderRadius: 7, overflow: 'hidden', flexDirection: 'row', backgroundColor: theme.color.surface3 },
  breakdownRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  breakdownLabel: { color: theme.color.onSurface, fontSize: 14, flex: 1 },
  breakdownValue: { color: theme.color.onSurface2, fontSize: 13, fontWeight: '600' },
  gridRow: { flexDirection: 'row', gap: theme.space.md },
  halfCard: { flex: 1 },
  miniLabel: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '600' },
  miniValue: { color: theme.color.onSurface, fontSize: 24, fontWeight: '800', marginTop: 4 },
  appRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 },
  appName: { color: theme.color.onSurface, fontSize: 14, width: 90 },
  appPctBar: { flex: 1, height: 6, borderRadius: 3, backgroundColor: theme.color.surface3, overflow: 'hidden' },
  appPctFill: { height: '100%', backgroundColor: theme.color.warning, borderRadius: 3 },
  appPct: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '600', width: 34, textAlign: 'right' },
  securityHero: { borderRadius: theme.radius.lg, padding: theme.space.xl, alignItems: 'center', marginBottom: theme.space.md },
  securityHeroTitle: { color: theme.color.onBrand, fontSize: 20, fontWeight: '800', marginTop: 10 },
  securityHeroSub: { color: 'rgba(2,44,34,0.8)', fontSize: 12, marginTop: 4, textAlign: 'center' },
  severityBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: theme.radius.pill },
  severityText: { fontSize: 10, fontWeight: '800' },
  threatCategory: { color: theme.color.onSurface3, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8, fontWeight: '600' },
  threatTitle: { color: theme.color.onSurface, fontSize: 15, fontWeight: '700' },
  threatBody: { color: theme.color.onSurface2, fontSize: 13, marginTop: 4, lineHeight: 19 },
});
