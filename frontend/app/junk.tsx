import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator, Modal } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import Animated, { FadeIn } from 'react-native-reanimated';
import { api } from '@/src/api';
import { getDeviceId } from '@/src/device';
import { theme } from '@/src/theme';

export default function Junk() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    (async () => {
      const id = await getDeviceId();
      try {
        const d = await api.cacheBreakdown();
        setData(d);
        const s: Record<string, boolean> = {};
        d.apps.forEach((a: any) => (s[a.id] = true));
        setSelected(s);
      } catch (e) { console.log(e); }
      finally { setLoading(false); }
    })();
  }, []);

  const totalMb = data ? data.apps.filter((a: any) => selected[a.id]).reduce((sum: number, a: any) => sum + a.cache_mb, 0) : 0;
  const toggle = (id: string) => { Haptics.selectionAsync(); setSelected(s => ({ ...s, [id]: !s[id] })); };

  const doClear = async () => {
    setCleaning(true);
    try {
      const id = await getDeviceId();
      await api.runClean({ categories: ['App cache'], reclaimable_mb: totalMb });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setConfirmOpen(false);
      setDone(true);
    } catch (e) { console.log(e); }
    finally { setCleaning(false); }
  };

  const maxCache = data ? Math.max(...data.apps.map((a: any) => a.cache_mb)) : 1;

  return (
    <View style={styles.container} testID="junk-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="junk-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Junk by App</Text>
          <View style={{ width: 26 }} />
        </View>

        {loading || !data ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : done ? (
          <Animated.View entering={FadeIn} style={styles.doneWrap} testID="junk-done">
            <View style={styles.doneIcon}>
              <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} />
              <Ionicons name="checkmark" size={54} color={theme.color.onBrand} />
            </View>
            <Text style={styles.doneTitle}>Cache cleared</Text>
            <Text style={styles.doneBody}>Freed {(totalMb / 1024).toFixed(2)} GB from app caches.</Text>
            <Pressable style={styles.cta} onPress={() => router.back()} testID="junk-done-button">
              <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
              <Text style={styles.ctaText}>Done</Text>
            </Pressable>
          </Animated.View>
        ) : (
          <>
            <View style={styles.summary}>
              <Text style={styles.summaryValue}>{totalMb.toFixed(0)} MB</Text>
              <Text style={styles.summaryLabel}>selected of {data.total_mb.toFixed(0)} MB total cache</Text>
            </View>
            <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 100 }}>
              {data.apps.map((a: any) => (
                <Pressable key={a.id} style={[styles.row, selected[a.id] && styles.rowActive]} onPress={() => toggle(a.id)} testID={`junk-app-${a.id}`}>
                  <Text style={styles.emoji}>{a.icon}</Text>
                  <View style={{ flex: 1 }}>
                    <View style={styles.rowTop}>
                      <Text style={styles.appName}>{a.app}</Text>
                      <Text style={styles.appSize}>{a.cache_mb.toFixed(0)} MB</Text>
                    </View>
                    <View style={styles.bar}>
                      <View style={[styles.barFill, { width: `${(a.cache_mb / maxCache) * 100}%` }]} />
                    </View>
                    <Text style={styles.appCat}>{a.category}</Text>
                  </View>
                  <View style={[styles.checkbox, selected[a.id] && styles.checkboxActive]}>
                    {selected[a.id] && <Ionicons name="checkmark" size={14} color={theme.color.onBrand} />}
                  </View>
                </Pressable>
              ))}
              <View style={styles.assurance}>
                <Ionicons name="shield-checkmark" size={16} color={theme.color.brand} />
                <Text style={styles.assuranceText}>Clearing cache never deletes your accounts, photos or messages.</Text>
              </View>
            </ScrollView>
            <View style={styles.bottomBar}>
              <Pressable style={[styles.cta, totalMb === 0 && { opacity: 0.4 }]} disabled={totalMb === 0} onPress={() => setConfirmOpen(true)} testID="junk-clear-button">
                <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
                <Text style={styles.ctaText}>Clear {totalMb.toFixed(0)} MB</Text>
              </Pressable>
            </View>
          </>
        )}
      </SafeAreaView>

      <Modal visible={confirmOpen} transparent animationType="fade" onRequestClose={() => setConfirmOpen(false)}>
        <View style={styles.modalBg}>
          <Animated.View entering={FadeIn} style={styles.modalCard}>
            <View style={styles.modalIcon}><Ionicons name="trash" size={30} color={theme.color.brand} /></View>
            <Text style={styles.modalTitle}>Clear app cache?</Text>
            <Text style={styles.modalBody}>We&apos;ll free {(totalMb / 1024).toFixed(2)} GB. Apps may take a moment to reload content next time.</Text>
            <View style={styles.modalButtons}>
              <Pressable style={[styles.modalBtn, styles.modalBtnGhost]} onPress={() => setConfirmOpen(false)} testID="junk-cancel">
                <Text style={styles.modalBtnGhostText}>Cancel</Text>
              </Pressable>
              <Pressable style={[styles.modalBtn, styles.modalBtnPrimary]} onPress={doClear} testID="junk-confirm">
                {cleaning ? <ActivityIndicator color={theme.color.onBrand} /> : <Text style={styles.modalBtnPrimaryText}>Clear now</Text>}
              </Pressable>
            </View>
          </Animated.View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  summary: { paddingHorizontal: theme.space.lg, paddingBottom: theme.space.md },
  summaryValue: { color: theme.color.brand, fontSize: 32, fontWeight: '800', letterSpacing: -1 },
  summaryLabel: { color: theme.color.onSurface2, fontSize: 13 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: theme.color.surface2, padding: theme.space.md, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.sm },
  rowActive: { borderColor: theme.color.brand },
  emoji: { fontSize: 26 },
  rowTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  appName: { color: theme.color.onSurface, fontSize: 15, fontWeight: '600' },
  appSize: { color: theme.color.onSurface, fontSize: 13, fontWeight: '700' },
  bar: { height: 6, borderRadius: 3, backgroundColor: theme.color.surface3, marginTop: 6, overflow: 'hidden' },
  barFill: { height: '100%', backgroundColor: theme.color.warning, borderRadius: 3 },
  appCat: { color: theme.color.onSurface3, fontSize: 11, marginTop: 4 },
  checkbox: { width: 22, height: 22, borderRadius: 6, borderWidth: 1.5, borderColor: theme.color.border, alignItems: 'center', justifyContent: 'center' },
  checkboxActive: { backgroundColor: theme.color.brand, borderColor: theme.color.brand },
  assurance: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: theme.color.brand3, borderRadius: theme.radius.md, padding: theme.space.md, marginTop: theme.space.sm },
  assuranceText: { color: theme.color.onSurface, fontSize: 12, flex: 1, lineHeight: 17 },
  bottomBar: { position: 'absolute', bottom: 0, left: 0, right: 0, padding: theme.space.lg, paddingBottom: 32, backgroundColor: theme.color.surface, borderTopWidth: 1, borderTopColor: theme.color.border },
  cta: { height: 54, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
  doneWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: theme.space.xl },
  doneIcon: { width: 110, height: 110, borderRadius: 55, alignItems: 'center', justifyContent: 'center', overflow: 'hidden', marginBottom: theme.space.lg },
  doneTitle: { color: theme.color.onSurface, fontSize: 26, fontWeight: '800' },
  doneBody: { color: theme.color.onSurface2, fontSize: 15, marginTop: 8, marginBottom: theme.space.xl, textAlign: 'center' },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.75)', alignItems: 'center', justifyContent: 'center', padding: theme.space.xl },
  modalCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.xl, borderWidth: 1, borderColor: theme.color.border, alignItems: 'center', width: '100%' },
  modalIcon: { width: 58, height: 58, borderRadius: 29, backgroundColor: theme.color.brand3, alignItems: 'center', justifyContent: 'center', marginBottom: theme.space.md },
  modalTitle: { color: theme.color.onSurface, fontSize: 20, fontWeight: '800' },
  modalBody: { color: theme.color.onSurface2, fontSize: 14, textAlign: 'center', marginTop: 8, lineHeight: 20 },
  modalButtons: { flexDirection: 'row', gap: 10, marginTop: theme.space.lg, width: '100%' },
  modalBtn: { flex: 1, height: 48, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center' },
  modalBtnGhost: { backgroundColor: theme.color.surface3, borderWidth: 1, borderColor: theme.color.border },
  modalBtnGhostText: { color: theme.color.onSurface, fontWeight: '600' },
  modalBtnPrimary: { backgroundColor: theme.color.brand },
  modalBtnPrimaryText: { color: theme.color.onBrand, fontWeight: '700' },
});
