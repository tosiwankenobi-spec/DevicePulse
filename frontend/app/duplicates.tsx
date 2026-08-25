import React, { useCallback, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { api } from '@/src/api';
import { theme } from '@/src/theme';

type DuplicateGroup = {
  id: string;
  photo_count: number;
  size_mb: number;
  thumbnail_url: string;
  taken_at: string;
  ai_label: string;
  ai_confidence: number;
};

const labelColor = (label: string) => {
  if (label === 'Exact duplicate') return theme.color.brand;
  if (label === 'Burst photo') return theme.color.info;
  return theme.color.warning;
};

export default function Duplicates() {
  const router = useRouter();
  const [groups, setGroups] = useState<DuplicateGroup[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [errMsg, setErrMsg] = useState('');
  const [okMsg, setOkMsg] = useState('');

  const load = useCallback(async () => {
    try {
      const d = await api.duplicates();
      setGroups(d);
      const s: Record<string, boolean> = {};
      d.forEach((g: DuplicateGroup) => (s[g.id] = true));
      setSelected(s);
    } catch (e) {
      console.log(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const totalMb = groups.filter((g: DuplicateGroup) => selected[g.id]).reduce((a: number, g: DuplicateGroup) => a + g.size_mb, 0);
  const selectedIds = groups.filter((g: DuplicateGroup) => selected[g.id]).map((g: DuplicateGroup) => g.id);
  const toggle = (id: string) => { Haptics.selectionAsync().catch(() => {}); setSelected((s: Record<string, boolean>) => ({ ...s, [id]: !s[id] })); };

  const onScan = async () => {
    if (scanning) return;
    setScanning(true);
    setErrMsg('');
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    try {
      const res = await api.scanDuplicates();
      setGroups(res.groups);
      setSelected((prev: Record<string, boolean>) => {
        const s: Record<string, boolean> = { ...prev };
        res.groups.forEach((g: DuplicateGroup) => { if (!(g.id in s)) s[g.id] = true; });
        return s;
      });
      setOkMsg(res.new_groups_found > 0
        ? `Found ${res.new_groups_found} new duplicate group${res.new_groups_found === 1 ? '' : 's'}`
        : 'No new duplicates found');
      setTimeout(() => setOkMsg(''), 2500);
    } catch (e) {
      console.log(e);
    } finally {
      setScanning(false);
    }
  };

  const onRemove = async () => {
    if (removing || selectedIds.length === 0) return;
    setRemoving(true);
    setErrMsg('');
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    try {
      const res = await api.removeDuplicates(selectedIds);
      setGroups(res.groups);
      const s: Record<string, boolean> = {};
      res.groups.forEach((g: DuplicateGroup) => (s[g.id] = true));
      setSelected(s);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      setOkMsg(`Removed ${res.freed_mb.toFixed(0)} MB`);
      setTimeout(() => setOkMsg(''), 2500);
    } catch (e: any) {
      const msg = String(e?.message || '');
      if (msg.includes('403')) {
        setErrMsg('Free plan allows removing 3 duplicate groups per day. Upgrade to Pro for unlimited duplicate cleanup.');
      } else {
        setErrMsg('Could not remove those duplicates. Please try again.');
      }
    } finally {
      setRemoving(false);
    }
  };

  return (
    <View style={styles.container} testID="duplicates-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="dup-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Duplicate Photo AI</Text>
          <Pressable onPress={onScan} disabled={scanning} hitSlop={12} testID="dup-scan">
            {scanning ? <ActivityIndicator size="small" color={theme.color.brand} /> : <Ionicons name="sparkles" size={22} color={theme.color.brand} />}
          </Pressable>
        </View>

        {loading ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : groups.length === 0 ? (
          <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40, flexGrow: 1, justifyContent: 'center' }}>
            <View style={styles.emptyCard}>
              <Ionicons name="checkmark-circle" size={40} color={theme.color.brand} />
              <Text style={styles.emptyTitle}>You're all caught up</Text>
              <Text style={styles.emptyBody}>No duplicate photos detected right now. Run another AI scan any time to check for new ones.</Text>
              <Pressable style={styles.scanAgainBtn} onPress={onScan} disabled={scanning} testID="dup-scan-again">
                {scanning ? <ActivityIndicator color={theme.color.onSurface} /> : <Text style={styles.scanAgainText}>Scan again</Text>}
              </Pressable>
            </View>
          </ScrollView>
        ) : (
          <>
            <View style={styles.summary}>
              <Text style={styles.summaryValue}>{totalMb.toFixed(0)} MB</Text>
              <Text style={styles.summaryLabel}>selected across {selectedIds.length} groups</Text>
              {!!okMsg && <Text style={styles.okMsg} testID="dup-ok-msg">{okMsg}</Text>}
            </View>
            <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 100 }}>
              {groups.map((g: DuplicateGroup) => (
                <Pressable key={g.id} style={[styles.card, selected[g.id] && styles.cardActive]} onPress={() => toggle(g.id)} testID={`dup-group-${g.id}`}>
                  <Image source={g.thumbnail_url} style={styles.thumb} contentFit="cover" />
                  <View style={{ flex: 1 }}>
                    <View style={styles.titleRow}>
                      <Text style={styles.groupTitle}>{g.photo_count} copies</Text>
                      <View style={[styles.aiBadge, { borderColor: labelColor(g.ai_label) }]}>
                        <Text style={[styles.aiBadgeText, { color: labelColor(g.ai_label) }]}>{g.ai_confidence}% · {g.ai_label}</Text>
                      </View>
                    </View>
                    <Text style={styles.groupSize}>{g.size_mb.toFixed(1)} MB · {g.taken_at}</Text>
                    <Text style={styles.groupKeep}>Keeping best 1, removing {g.photo_count - 1}</Text>
                  </View>
                  <View style={[styles.checkbox, selected[g.id] && styles.checkboxActive]}>
                    {selected[g.id] && <Ionicons name="checkmark" size={14} color={theme.color.onBrand} />}
                  </View>
                </Pressable>
              ))}
            </ScrollView>
            <View style={styles.bottomBar}>
              {!!errMsg && (
                <Pressable onPress={() => router.push('/paywall')} testID="dup-error">
                  <Text style={styles.errMsg}>{errMsg}</Text>
                </Pressable>
              )}
              <Pressable style={styles.cta} onPress={onRemove} disabled={removing || selectedIds.length === 0} testID="dup-remove-button">
                <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
                {removing ? <ActivityIndicator color={theme.color.onBrand} /> : <Text style={styles.ctaText}>Remove {totalMb.toFixed(0)} MB</Text>}
              </Pressable>
            </View>
          </>
        )}
      </SafeAreaView>
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
  okMsg: { color: theme.color.brand, fontSize: 12, marginTop: 4, fontWeight: '600' },
  card: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: theme.color.surface2, padding: 12, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.sm },
  cardActive: { borderColor: theme.color.brand },
  thumb: { width: 64, height: 64, borderRadius: 10, backgroundColor: theme.color.surface3 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  groupTitle: { color: theme.color.onSurface, fontSize: 15, fontWeight: '700' },
  aiBadge: { borderWidth: 1, borderRadius: theme.radius.pill, paddingHorizontal: 8, paddingVertical: 2 },
  aiBadgeText: { fontSize: 10, fontWeight: '700' },
  groupSize: { color: theme.color.onSurface2, fontSize: 12, marginTop: 2 },
  groupKeep: { color: theme.color.brand, fontSize: 11, marginTop: 4 },
  checkbox: { width: 22, height: 22, borderRadius: 6, borderWidth: 1.5, borderColor: theme.color.border, alignItems: 'center', justifyContent: 'center' },
  checkboxActive: { backgroundColor: theme.color.brand, borderColor: theme.color.brand },
  bottomBar: { padding: theme.space.lg, paddingBottom: 32, borderTopWidth: 1, borderTopColor: theme.color.border, backgroundColor: theme.color.surface },
  cta: { height: 52, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
  errMsg: { color: theme.color.error, fontSize: 12, textAlign: 'center', marginBottom: 10, lineHeight: 16 },
  emptyCard: { alignItems: 'center', backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, borderWidth: 1, borderColor: theme.color.border, padding: theme.space.xl, gap: 8 },
  emptyTitle: { color: theme.color.onSurface, fontSize: 18, fontWeight: '800', marginTop: 4 },
  emptyBody: { color: theme.color.onSurface2, fontSize: 13, textAlign: 'center', lineHeight: 18 },
  scanAgainBtn: { marginTop: theme.space.md, height: 44, paddingHorizontal: 20, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.color.surface3, borderWidth: 1, borderColor: theme.color.border },
  scanAgainText: { color: theme.color.onSurface, fontSize: 14, fontWeight: '700' },
});
