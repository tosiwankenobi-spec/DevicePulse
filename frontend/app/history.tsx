import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { api } from '@/src/api';
import { getDeviceId } from '@/src/device';
import { theme } from '@/src/theme';

const CAT_ICON: Record<string, keyof typeof Ionicons.glyphMap> = {
  'Junk files': 'trash-outline',
  'Duplicates': 'copy-outline',
  'Large files': 'folder-open-outline',
  'App cache': 'server-outline',
};

function timeAgo(iso: string) {
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export default function History() {
  const router = useRouter();
  const [items, setItems] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const id = await getDeviceId();
      try {
        const [h, s] = await Promise.all([api.history(), api.historySummary()]);
        setItems(h);
        setSummary(s);
      } catch (e) { console.log(e); }
      finally { setLoading(false); }
    })();
  }, []);

  return (
    <View style={styles.container} testID="history-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="history-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Scan History</Text>
          <View style={{ width: 26 }} />
        </View>

        {loading ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : (
          <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
            {/* Summary */}
            <LinearGradient colors={theme.gradients.brand} style={styles.summaryCard} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
              <Text style={styles.summaryLabel}>TOTAL RECLAIMED</Text>
              <Text style={styles.summaryValue}>{summary?.total_reclaimed_gb?.toFixed(2) ?? '0.00'} GB</Text>
              <Text style={styles.summarySub}>across {summary?.total_cleanups ?? 0} cleanups</Text>
            </LinearGradient>

            {items.length === 0 ? (
              <View style={styles.empty} testID="history-empty">
                <Ionicons name="time-outline" size={54} color={theme.color.onSurface3} />
                <Text style={styles.emptyTitle}>No cleanups yet</Text>
                <Text style={styles.emptyBody}>Run a Smart Scan to start tracking the space you reclaim.</Text>
                <Pressable style={styles.emptyCta} onPress={() => router.push('/smart-scan')} testID="history-start-scan">
                  <Text style={styles.emptyCtaText}>Run Smart Scan</Text>
                </Pressable>
              </View>
            ) : (
              <>
                <Text style={styles.section}>Timeline</Text>
                {items.map((it, i) => (
                  <View key={it.id} style={styles.entry} testID={`history-entry-${i}`}>
                    <View style={styles.timelineCol}>
                      <View style={styles.dot} />
                      {i < items.length - 1 && <View style={styles.line} />}
                    </View>
                    <View style={styles.entryCard}>
                      <View style={styles.entryHeader}>
                        <Text style={styles.entryReclaimed}>{(it.reclaimed_mb / 1024).toFixed(2)} GB freed</Text>
                        <Text style={styles.entryTime}>{timeAgo(it.completed_at)}</Text>
                      </View>
                      <View style={styles.chips}>
                        {it.categories.map((c: string) => (
                          <View key={c} style={styles.chip}>
                            <Ionicons name={CAT_ICON[c] || 'checkmark'} size={12} color={theme.color.brand} />
                            <Text style={styles.chipText}>{c}</Text>
                          </View>
                        ))}
                      </View>
                    </View>
                  </View>
                ))}
              </>
            )}
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
  summaryCard: { borderRadius: theme.radius.lg, padding: theme.space.xl, alignItems: 'center', marginBottom: theme.space.lg },
  summaryLabel: { color: theme.color.onBrand, fontSize: 11, fontWeight: '800', letterSpacing: 1.2 },
  summaryValue: { color: theme.color.onBrand, fontSize: 40, fontWeight: '800', letterSpacing: -1, marginTop: 4 },
  summarySub: { color: 'rgba(2,44,34,0.8)', fontSize: 13, marginTop: 2 },
  section: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '700', letterSpacing: 1.1, textTransform: 'uppercase', marginBottom: theme.space.md },
  entry: { flexDirection: 'row', gap: 12 },
  timelineCol: { alignItems: 'center', width: 16 },
  dot: { width: 12, height: 12, borderRadius: 6, backgroundColor: theme.color.brand, marginTop: 6, borderWidth: 3, borderColor: theme.color.brand3 },
  line: { flex: 1, width: 2, backgroundColor: theme.color.border, marginVertical: 2 },
  entryCard: { flex: 1, backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, padding: theme.space.md, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.md },
  entryHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  entryReclaimed: { color: theme.color.onSurface, fontSize: 15, fontWeight: '700' },
  entryTime: { color: theme.color.onSurface3, fontSize: 12 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: theme.color.brand3, paddingHorizontal: 8, paddingVertical: 4, borderRadius: theme.radius.pill },
  chipText: { color: theme.color.brand, fontSize: 11, fontWeight: '600' },
  empty: { alignItems: 'center', paddingVertical: 40, gap: 8 },
  emptyTitle: { color: theme.color.onSurface, fontSize: 18, fontWeight: '700', marginTop: 8 },
  emptyBody: { color: theme.color.onSurface2, fontSize: 14, textAlign: 'center', lineHeight: 20, maxWidth: 280 },
  emptyCta: { marginTop: theme.space.lg, backgroundColor: theme.color.brand, paddingHorizontal: 24, paddingVertical: 12, borderRadius: theme.radius.pill },
  emptyCtaText: { color: theme.color.onBrand, fontWeight: '700' },
});
