import React, { useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Modal, Pressable, ScrollView, Share, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { api } from '@/src/api';
import { clearDevicePulseCache, openDeviceStorageManager, scanLocalDevice, type LocalDeviceScan } from '@/src/deviceStorage';
import { theme } from '@/src/theme';

function formatMb(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
  if (mb >= 1) return `${mb.toFixed(1)} MB`;
  return `${Math.round(mb * 1024)} KB`;
}

export default function Results() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const data = useMemo<LocalDeviceScan | null>(() => {
    try { return JSON.parse(params.data as string); } catch { return null; }
  }, [params.data]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [cleanedMb, setCleanedMb] = useState<number | null>(null);

  if (!data) {
    return <View style={styles.container}><Text style={styles.emptyText}>No device storage data is available.</Text></View>;
  }

  const doClearCache = async () => {
    setConfirmOpen(false);
    setCleaning(true);
    try {
      const removedMb = clearDevicePulseCache();
      const after = scanLocalDevice();
      if (removedMb > 0) {
        try {
          await api.runClean({ categories: ['DevicePulse temporary cache'], reclaimable_mb: removedMb });
        } catch {
          // Local cleanup succeeded; history sync can fail independently.
        }
      }
      setCleanedMb(removedMb);
      data.health_after = after.health_before;
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch {
      Alert.alert('Cache not cleared', 'Android kept the active cache files in use. You can clear them from Android Storage settings.');
    } finally {
      setCleaning(false);
    }
  };

  if (cleanedMb !== null) {
    return <CleanupComplete removedMb={cleanedMb} onDone={() => router.replace('/(tabs)')} />;
  }

  return (
    <View style={styles.container} testID="results-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="results-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Storage Results</Text>
          <View style={{ width: 26 }} />
        </View>

        <ScrollView contentContainerStyle={styles.content}>
          <View style={styles.totalCard}>
            <Text style={styles.totalLabel}>Device storage used</Text>
            <Text style={styles.totalValue}>{formatMb(data.storage_used_mb)}</Text>
            <Text style={styles.totalSub}>{formatMb(data.storage_free_mb)} free of {formatMb(data.storage_total_mb)}</Text>
          </View>

          <Text style={styles.section}>Safe cleanup available</Text>
          <View style={styles.actionCard}>
            <View style={[styles.actionIcon, { backgroundColor: theme.color.brand3 }]}>
              <Ionicons name="flash-outline" size={22} color={theme.color.brand} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.actionTitle}>DevicePulse temporary cache</Text>
              <Text style={styles.actionBody}>{formatMb(data.cache_mb)} measured on this device</Text>
            </View>
          </View>

          <View style={styles.assurance}>
            <Ionicons name="shield-checkmark" size={20} color={theme.color.brand} />
            <Text style={styles.assuranceText}>DevicePulse can clear only its own temporary files. Your photos, downloads, messages and other apps stay untouched.</Text>
          </View>

          <Text style={styles.section}>Review personal files safely</Text>
          <View style={styles.actionCard}>
            <View style={[styles.actionIcon, { backgroundColor: '#0EA5E922' }]}>
              <Ionicons name="folder-open-outline" size={22} color={theme.color.info} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.actionTitle}>Android Storage Manager</Text>
              <Text style={styles.actionBody}>Review large files, downloads, photos and app storage using Android&apos;s protected controls.</Text>
            </View>
          </View>
          <Pressable style={styles.secondaryButton} onPress={openDeviceStorageManager} testID="open-storage-manager">
            <Ionicons name="open-outline" size={18} color={theme.color.brand} />
            <Text style={styles.secondaryButtonText}>Open Android Storage</Text>
          </Pressable>
        </ScrollView>

        <View style={styles.bottomBar}>
          <Pressable style={[styles.cta, data.cache_mb <= 0 && styles.ctaDisabled]} onPress={() => data.cache_mb > 0 && setConfirmOpen(true)} disabled={data.cache_mb <= 0 || cleaning} testID="clear-cache-button">
            <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
            {cleaning ? <ActivityIndicator color={theme.color.onBrand} /> : <Text style={styles.ctaText}>{data.cache_mb > 0 ? `Clear ${formatMb(data.cache_mb)} cache` : 'Cache is already clear'}</Text>}
          </Pressable>
        </View>
      </SafeAreaView>

      <Modal visible={confirmOpen} transparent animationType="fade" onRequestClose={() => setConfirmOpen(false)}>
        <View style={styles.modalBg}>
          <View style={styles.modalCard}>
            <View style={styles.modalIcon}><Ionicons name="shield-checkmark" size={32} color={theme.color.brand} /></View>
            <Text style={styles.modalTitle}>Clear DevicePulse cache?</Text>
            <Text style={styles.modalBody}>This removes {formatMb(data.cache_mb)} of DevicePulse temporary files only. Personal files and other apps are not touched.</Text>
            <View style={styles.modalButtons}>
              <Pressable style={[styles.modalBtn, styles.modalBtnGhost]} onPress={() => setConfirmOpen(false)}><Text style={styles.modalBtnGhostText}>Cancel</Text></Pressable>
              <Pressable style={[styles.modalBtn, styles.modalBtnPrimary]} onPress={doClearCache} testID="confirm-clear-cache"><Text style={styles.modalBtnPrimaryText}>Clear cache</Text></Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

function CleanupComplete({ removedMb, onDone }: { removedMb: number; onDone: () => void }) {
  const shareResult = () => Share.share({ message: `DevicePulse safely cleared ${formatMb(removedMb)} of its temporary cache. My personal files stayed untouched.` });
  return (
    <View style={styles.container} testID="results-success-screen">
      <LinearGradient colors={theme.gradients.hero2} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={styles.successWrap}>
        <View style={styles.successIcon}><Ionicons name="checkmark" size={54} color={theme.color.onBrand} /></View>
        <Text style={styles.successTitle}>Cache cleared</Text>
        <Text style={styles.successBody}>{removedMb > 0 ? `${formatMb(removedMb)} of DevicePulse temporary files removed.` : 'The temporary cache was already empty.'}</Text>
        <Text style={styles.successNote}>No personal files or other apps were changed.</Text>
        <Pressable style={styles.secondaryButton} onPress={shareResult}><Ionicons name="share-social" size={18} color={theme.color.brand} /><Text style={styles.secondaryButtonText}>Share result</Text></Pressable>
        <Pressable style={[styles.cta, styles.doneButton]} onPress={onDone} testID="done-button"><LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} /><Text style={styles.ctaText}>Back to dashboard</Text></Pressable>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  content: { paddingHorizontal: theme.space.lg, paddingBottom: 150 },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  emptyText: { color: theme.color.onSurface2, textAlign: 'center', marginTop: 40 },
  totalCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.xl, borderWidth: 1, borderColor: theme.color.brand3, alignItems: 'center' },
  totalLabel: { color: theme.color.brand, fontSize: 12, fontWeight: '700', letterSpacing: 1, textTransform: 'uppercase' },
  totalValue: { color: theme.color.onSurface, fontSize: 42, fontWeight: '800', marginTop: 6, letterSpacing: -1.2 },
  totalSub: { color: theme.color.onSurface2, fontSize: 13, marginTop: 6 },
  section: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '700', letterSpacing: 1.1, textTransform: 'uppercase', marginTop: theme.space.lg, marginBottom: theme.space.sm },
  actionCard: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: theme.color.surface2, padding: theme.space.md, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.border },
  actionIcon: { width: 44, height: 44, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
  actionTitle: { color: theme.color.onSurface, fontSize: 15, fontWeight: '700' },
  actionBody: { color: theme.color.onSurface2, fontSize: 12, lineHeight: 17, marginTop: 3 },
  assurance: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: theme.space.md, padding: theme.space.md, backgroundColor: theme.color.brand3, borderRadius: theme.radius.md },
  assuranceText: { color: theme.color.onSurface, fontSize: 12, flex: 1, lineHeight: 17 },
  secondaryButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, minHeight: 48, paddingHorizontal: 22, borderRadius: theme.radius.pill, borderWidth: 1.5, borderColor: theme.color.brand, marginTop: theme.space.md },
  secondaryButtonText: { color: theme.color.brand, fontSize: 15, fontWeight: '700' },
  bottomBar: { position: 'absolute', bottom: 0, left: 0, right: 0, padding: theme.space.lg, paddingBottom: 32, backgroundColor: theme.color.surface, borderTopWidth: 1, borderTopColor: theme.color.border },
  cta: { height: 54, borderRadius: theme.radius.pill, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  ctaDisabled: { opacity: 0.45 },
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
  successWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: theme.space.xl },
  successIcon: { width: 120, height: 120, borderRadius: 60, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.color.brand, marginBottom: theme.space.xl },
  successTitle: { color: theme.color.onSurface, fontSize: 30, fontWeight: '800' },
  successBody: { color: theme.color.onSurface, fontSize: 16, marginTop: 10, textAlign: 'center' },
  successNote: { color: theme.color.onSurface2, fontSize: 13, marginTop: 8, textAlign: 'center' },
  doneButton: { marginTop: theme.space.md, width: '100%', maxWidth: 360 },
});
