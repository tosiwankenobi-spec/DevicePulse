import React, { useMemo, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Modal, ActivityIndicator } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import Animated, { FadeIn, FadeInDown } from 'react-native-reanimated';
import { HealthRing } from '@/src/components/HealthRing';
import { api } from '@/src/api';
import { getDeviceId } from '@/src/device';
import { theme } from '@/src/theme';

const CATS = [
  { key: 'junk_mb', label: 'Junk files', icon: 'trash-outline', color: theme.color.warning },
  { key: 'duplicates_mb', label: 'Duplicates', icon: 'copy-outline', color: theme.color.info },
  { key: 'large_files_mb', label: 'Large files', icon: 'folder-open-outline', color: '#8B5CF6' },
  { key: 'cache_mb', label: 'App cache', icon: 'server-outline', color: theme.color.brand },
] as const;

export default function Results() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const data = useMemo(() => {
    try { return JSON.parse(params.data as string); } catch { return null; }
  }, [params.data]);
  const [selected, setSelected] = useState<Record<string, boolean>>({ junk_mb: true, duplicates_mb: true, large_files_mb: false, cache_mb: true });
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [cleanedResult, setCleanedResult] = useState<any>(null);

  if (!data) return (
    <View style={styles.container}><Text style={styles.emptyText}>No scan data</Text></View>
  );

  const total = CATS.filter(c => selected[c.key]).reduce((a, c) => a + (data[c.key] || 0), 0);

  const toggle = (k: string) => {
    setSelected(s => ({ ...s, [k]: !s[k] }));
    Haptics.selectionAsync();
  };

  const doClean = async () => {
    setCleaning(true);
    try {
      const cats = CATS.filter(c => selected[c.key]).map(c => c.label);
      const id = await getDeviceId();
      const res = await api.runClean({ categories: cats, reclaimable_mb: total, device_id: id });
      setCleanedResult(res);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (e) {
      console.log(e);
    } finally {
      setCleaning(false);
    }
  };

  if (cleanedResult) {
    return <SuccessView data={cleanedResult} onDone={() => router.replace('/(tabs)')} />;
  }

  return (
    <View style={styles.container} testID="results-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="results-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Scan Results</Text>
          <View style={{ width: 26 }} />
        </View>
        <ScrollView contentContainerStyle={{ paddingBottom: 140, paddingHorizontal: theme.space.lg }}>
          <View style={styles.totalCard}>
            <Text style={styles.totalLabel}>Selected to clean</Text>
            <Text style={styles.totalValue}>{(total / 1024).toFixed(2)} GB</Text>
            <Text style={styles.totalSub}>Health after cleanup: {data.health_after}/100</Text>
          </View>

          <Text style={styles.section}>Choose what to remove</Text>
          {CATS.map((c, i) => (
            <Animated.View key={c.key} entering={FadeInDown.delay(i * 80)}>
              <Pressable style={[styles.catRow, selected[c.key] && styles.catRowActive]} onPress={() => toggle(c.key)} testID={`cat-${c.key}`}>
                <View style={[styles.catIcon, { backgroundColor: c.color + '22' }]}>
                  <Ionicons name={c.icon as any} size={20} color={c.color} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.catTitle}>{c.label}</Text>
                  <Text style={styles.catSize}>{(data[c.key] || 0).toFixed(0)} MB</Text>
                </View>
                <View style={[styles.checkbox, selected[c.key] && styles.checkboxActive]}>
                  {selected[c.key] && <Ionicons name="checkmark" size={16} color={theme.color.onBrand} />}
                </View>
              </Pressable>
            </Animated.View>
          ))}

          <View style={styles.assurance}>
            <Ionicons name="shield-checkmark" size={18} color={theme.color.brand} />
            <Text style={styles.assuranceText}>
              We only remove files you approve. Nothing personal is touched.
            </Text>
          </View>
        </ScrollView>

        <View style={styles.bottomBar}>
          <Pressable
            style={[styles.cta, total === 0 && { opacity: 0.4 }]}
            onPress={() => total > 0 && setConfirmOpen(true)}
            disabled={total === 0}
            testID="clean-now-button"
          >
            <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
            <Text style={styles.ctaText}>Clean {(total / 1024).toFixed(2)} GB</Text>
          </Pressable>
        </View>
      </SafeAreaView>

      {/* Confirm modal */}
      <Modal visible={confirmOpen} transparent animationType="fade" onRequestClose={() => setConfirmOpen(false)}>
        <View style={styles.modalBg}>
          <Animated.View entering={FadeIn} style={styles.modalCard}>
            <View style={styles.modalIcon}>
              <Ionicons name="alert-circle" size={32} color={theme.color.brand} />
            </View>
            <Text style={styles.modalTitle}>Confirm cleanup</Text>
            <Text style={styles.modalBody}>
              We&apos;ll free up {(total / 1024).toFixed(2)} GB by removing the items you selected. This can&apos;t be undone.
            </Text>
            <View style={styles.modalButtons}>
              <Pressable style={[styles.modalBtn, styles.modalBtnGhost]} onPress={() => setConfirmOpen(false)} testID="confirm-cancel">
                <Text style={styles.modalBtnGhostText}>Cancel</Text>
              </Pressable>
              <Pressable
                style={[styles.modalBtn, styles.modalBtnPrimary]}
                onPress={() => { setConfirmOpen(false); doClean(); }}
                testID="confirm-clean"
              >
                {cleaning ? <ActivityIndicator color={theme.color.onBrand} /> : <Text style={styles.modalBtnPrimaryText}>Clean now</Text>}
              </Pressable>
            </View>
          </Animated.View>
        </View>
      </Modal>
    </View>
  );
}

const SuccessView = ({ data, onDone }: { data: any; onDone: () => void }) => (
  <View style={styles.container} testID="results-success-screen">
    <LinearGradient colors={theme.gradients.hero2} style={StyleSheet.absoluteFill} />
    <SafeAreaView style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: theme.space.xl }}>
      <Animated.View entering={FadeIn.duration(500)} style={styles.successIcon}>
        <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} />
        <Ionicons name="checkmark" size={64} color={theme.color.onBrand} />
      </Animated.View>
      <Text style={styles.successTitle}>All clean!</Text>
      <Text style={styles.successBody}>You reclaimed <Text style={{ color: theme.color.brand, fontWeight: '800' }}>{(data.reclaimed_mb / 1024).toFixed(2)} GB</Text> of storage.</Text>

      <View style={styles.compareRow}>
        <View style={styles.compareCol}>
          <Text style={styles.compareLabel}>Before</Text>
          <HealthRing score={data.health_before} size={130} label=" " />
        </View>
        <Ionicons name="arrow-forward" size={22} color={theme.color.onSurface2} />
        <View style={styles.compareCol}>
          <Text style={styles.compareLabel}>After</Text>
          <HealthRing score={data.health_after} size={130} label=" " />
        </View>
      </View>

      <Pressable style={styles.cta} onPress={onDone} testID="done-button">
        <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
        <Text style={styles.ctaText}>Back to dashboard</Text>
      </Pressable>
    </SafeAreaView>
  </View>
);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  emptyText: { color: theme.color.onSurface2, textAlign: 'center', marginTop: 40 },
  totalCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.xl, borderWidth: 1, borderColor: theme.color.brand3, alignItems: 'center' },
  totalLabel: { color: theme.color.brand, fontSize: 12, fontWeight: '700', letterSpacing: 1, textTransform: 'uppercase' },
  totalValue: { color: theme.color.onSurface, fontSize: 44, fontWeight: '800', marginTop: 4, letterSpacing: -1.5 },
  totalSub: { color: theme.color.onSurface2, fontSize: 13, marginTop: 4 },
  section: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '700', letterSpacing: 1.1, textTransform: 'uppercase', marginTop: theme.space.lg, marginBottom: theme.space.sm },
  catRow: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: theme.color.surface2, padding: theme.space.md, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.sm },
  catRowActive: { borderColor: theme.color.brand },
  catIcon: { width: 40, height: 40, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  catTitle: { color: theme.color.onSurface, fontSize: 15, fontWeight: '600' },
  catSize: { color: theme.color.onSurface3, fontSize: 12, marginTop: 2 },
  checkbox: { width: 24, height: 24, borderRadius: 6, borderWidth: 1.5, borderColor: theme.color.border, alignItems: 'center', justifyContent: 'center' },
  checkboxActive: { backgroundColor: theme.color.brand, borderColor: theme.color.brand },
  assurance: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: theme.space.lg, padding: theme.space.md, backgroundColor: theme.color.brand3, borderRadius: theme.radius.md },
  assuranceText: { color: theme.color.onSurface, fontSize: 12, flex: 1, lineHeight: 17 },
  bottomBar: { position: 'absolute', bottom: 0, left: 0, right: 0, padding: theme.space.lg, paddingBottom: 32, backgroundColor: theme.color.surface, borderTopWidth: 1, borderTopColor: theme.color.border },
  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', height: 54, borderRadius: theme.radius.pill, overflow: 'hidden' },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.75)', alignItems: 'center', justifyContent: 'center', padding: theme.space.xl },
  modalCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.xl, borderWidth: 1, borderColor: theme.color.border, alignItems: 'center', width: '100%' },
  modalIcon: { width: 60, height: 60, borderRadius: 30, backgroundColor: theme.color.brand3, alignItems: 'center', justifyContent: 'center', marginBottom: theme.space.md },
  modalTitle: { color: theme.color.onSurface, fontSize: 20, fontWeight: '800' },
  modalBody: { color: theme.color.onSurface2, fontSize: 14, textAlign: 'center', marginTop: 8, lineHeight: 20 },
  modalButtons: { flexDirection: 'row', gap: 10, marginTop: theme.space.lg, width: '100%' },
  modalBtn: { flex: 1, height: 48, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center' },
  modalBtnGhost: { backgroundColor: theme.color.surface3, borderWidth: 1, borderColor: theme.color.border },
  modalBtnGhostText: { color: theme.color.onSurface, fontWeight: '600' },
  modalBtnPrimary: { backgroundColor: theme.color.brand },
  modalBtnPrimaryText: { color: theme.color.onBrand, fontWeight: '700' },
  successIcon: { width: 120, height: 120, borderRadius: 60, alignItems: 'center', justifyContent: 'center', overflow: 'hidden', marginBottom: theme.space.xl },
  successTitle: { color: theme.color.onSurface, fontSize: 30, fontWeight: '800', letterSpacing: -0.5 },
  successBody: { color: theme.color.onSurface2, fontSize: 15, marginTop: 8, textAlign: 'center' },
  compareRow: { flexDirection: 'row', alignItems: 'center', gap: theme.space.md, marginTop: theme.space.xl, marginBottom: theme.space.xl },
  compareCol: { alignItems: 'center' },
  compareLabel: { color: theme.color.onSurface2, fontSize: 12, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 },
});
