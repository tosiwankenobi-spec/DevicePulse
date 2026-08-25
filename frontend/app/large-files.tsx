import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { api } from '@/src/api';
import { theme } from '@/src/theme';

type LargeFileItem = {
  id: string;
  name: string;
  size_mb: number;
  type: string;
  modified_at: string;
};

const ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  video: 'videocam',
  audio: 'musical-notes',
  doc: 'document',
  photo: 'image',
};

const COLORS: Record<string, string> = {
  video: '#8B5CF6',
  audio: theme.color.info,
  doc: theme.color.warning,
  photo: theme.color.brand,
};

export default function LargeFiles() {
  const router = useRouter();
  const [files, setFiles] = useState<LargeFileItem[]>([]);
  const [sortDesc, setSortDesc] = useState(true);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    api.largeFiles().then(setFiles).finally(() => setLoading(false));
  }, []);

  const sorted = [...files].sort((a: LargeFileItem, b: LargeFileItem) => sortDesc ? b.size_mb - a.size_mb : a.size_mb - b.size_mb);
  const totalMb = files.filter((f: LargeFileItem) => selected[f.id]).reduce((a: number, f: LargeFileItem) => a + f.size_mb, 0);
  const toggle = (id: string) => { Haptics.selectionAsync(); setSelected((s: Record<string, boolean>) => ({ ...s, [id]: !s[id] })); };

  const onScan = async () => {
    setScanning(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    try {
      const res = await api.scanLargeFiles();
      setFiles(res.files);
    } catch (e) {
      console.log(e);
    } finally {
      setScanning(false);
    }
  };

  const onDelete = async () => {
    const ids = Object.keys(selected).filter((id) => selected[id]);
    if (ids.length === 0) return;
    setDeleting(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    try {
      const res = await api.deleteLargeFiles(ids);
      setFiles(res.files);
      setSelected({});
      router.back();
    } catch (e) {
      console.log(e);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <View style={styles.container} testID="large-files-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="lf-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Large Files</Text>
          <View style={{ flexDirection: 'row', gap: 16, alignItems: 'center' }}>
            <Pressable onPress={onScan} disabled={scanning} hitSlop={8} testID="lf-scan-again">
              {scanning
                ? <ActivityIndicator size="small" color={theme.color.brand} />
                : <Ionicons name="sparkles-outline" size={20} color={theme.color.brand} />}
            </Pressable>
            <Pressable onPress={() => setSortDesc((s: boolean) => !s)} testID="lf-sort">
              <Ionicons name={sortDesc ? 'arrow-down' : 'arrow-up'} size={22} color={theme.color.brand} />
            </Pressable>
          </View>
        </View>

        {loading ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : files.length === 0 ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: theme.space.xl, gap: 12 }}>
            <Ionicons name="checkmark-circle" size={48} color={theme.color.brand} />
            <Text style={{ color: theme.color.onSurface, fontSize: 16, fontWeight: '700' }}>No large files right now</Text>
            <Pressable style={styles.scanAgainCta} onPress={onScan} disabled={scanning} testID="lf-scan-again-empty">
              {scanning
                ? <ActivityIndicator size="small" color={theme.color.onBrand} />
                : <Text style={styles.scanAgainCtaText}>Scan again</Text>}
            </Pressable>
          </View>
        ) : (
          <>
            <View style={styles.summary}>
              <Text style={styles.summaryValue}>{(totalMb / 1024).toFixed(2)} GB</Text>
              <Text style={styles.summaryLabel}>selected · {files.filter((f: LargeFileItem) => selected[f.id]).length} files</Text>
            </View>
            <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 100 }}>
              {sorted.map((f: LargeFileItem) => (
                <Pressable key={f.id} style={[styles.row, selected[f.id] && styles.rowActive]} onPress={() => toggle(f.id)} testID={`lf-row-${f.id}`}>
                  <View style={[styles.icon, { backgroundColor: (COLORS[f.type] || theme.color.brand) + '22' }]}>
                    <Ionicons name={ICONS[f.type] || 'document'} size={22} color={COLORS[f.type] || theme.color.brand} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.fileName} numberOfLines={1}>{f.name}</Text>
                    <Text style={styles.fileMeta}>{f.size_mb >= 1024 ? `${(f.size_mb / 1024).toFixed(2)} GB` : `${f.size_mb.toFixed(1)} MB`} · {f.type}</Text>
                  </View>
                  <View style={[styles.checkbox, selected[f.id] && styles.checkboxActive]}>
                    {selected[f.id] && <Ionicons name="checkmark" size={14} color={theme.color.onBrand} />}
                  </View>
                </Pressable>
              ))}
            </ScrollView>
            <View style={styles.bottomBar}>
              <Pressable
                style={[styles.cta, (totalMb === 0 || deleting) && { opacity: 0.4 }]}
                disabled={totalMb === 0 || deleting}
                onPress={onDelete}
                testID="lf-delete-button"
              >
                <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
                {deleting
                  ? <ActivityIndicator color={theme.color.onBrand} />
                  : <Text style={styles.ctaText}>Delete {(totalMb / 1024).toFixed(2)} GB</Text>}
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
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: theme.color.surface2, padding: 12, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.sm },
  rowActive: { borderColor: theme.color.brand },
  icon: { width: 44, height: 44, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  fileName: { color: theme.color.onSurface, fontSize: 14, fontWeight: '600' },
  fileMeta: { color: theme.color.onSurface2, fontSize: 12, marginTop: 2 },
  checkbox: { width: 22, height: 22, borderRadius: 6, borderWidth: 1.5, borderColor: theme.color.border, alignItems: 'center', justifyContent: 'center' },
  checkboxActive: { backgroundColor: theme.color.brand, borderColor: theme.color.brand },
  bottomBar: { padding: theme.space.lg, paddingBottom: 32, borderTopWidth: 1, borderTopColor: theme.color.border, backgroundColor: theme.color.surface },
  cta: { height: 52, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
  scanAgainCta: { height: 44, paddingHorizontal: 22, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.color.brand },
  scanAgainCtaText: { color: theme.color.onBrand, fontSize: 14, fontWeight: '700' },
});
