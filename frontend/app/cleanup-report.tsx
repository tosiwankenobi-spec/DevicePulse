import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  ActivityIndicator,
  Share,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import * as Clipboard from 'expo-clipboard';
import { api, reportShareUrl } from '@/src/api';
import { theme } from '@/src/theme';

type Report = {
  share_code: string;
  generated_at: string;
  display_name: string;
  health_score: number;
  status: string;
  total_cleanups: number;
  total_reclaimed_mb: number;
  total_reclaimed_gb: number;
  current_streak_weeks: number;
  top_category: string | null;
  days_until_full: number;
};

const statusColor = (status: string) => {
  if (status === 'Excellent' || status === 'Good') return theme.color.brand;
  if (status === 'Needs Attention') return theme.color.warning;
  return theme.color.error;
};

export default function CleanupReport() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState<Report | null>(null);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    try {
      setReport(await api.reportMine());
    } catch (e) {
      console.log(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const onGenerate = async () => {
    if (generating) return;
    setGenerating(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    try {
      const r = await api.generateReport();
      setReport(r);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    } catch (e) {
      console.log(e);
    } finally {
      setGenerating(false);
    }
  };

  const onShare = async (r: Report) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    const url = reportShareUrl(r.share_code);
    const gb = r.total_reclaimed_gb;
    const msg = `I've freed ${gb} GB across ${r.total_cleanups} cleanups with DevicePulse 🚀 Check out my report: ${url}`;
    try {
      await Share.share({ message: msg, url });
    } catch (e) {
      console.log(e);
    }
  };

  const onCopyLink = async (r: Report) => {
    await Clipboard.setStringAsync(reportShareUrl(r.share_code));
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <View style={styles.container} testID="cleanup-report-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="report-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Cleanup Report</Text>
          <View style={{ width: 26 }} />
        </View>

        {loading ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : !report ? (
          <NoReportView generating={generating} onGenerate={onGenerate} />
        ) : (
          <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
            <LinearGradient colors={theme.gradients.brand} style={styles.hero} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
              <Ionicons name="checkmark-circle" size={32} color={theme.color.onBrand} />
              <Text style={styles.heroLabel}>Total storage freed</Text>
              <Text style={styles.heroValue}>{report.total_reclaimed_gb} GB</Text>
              <Text style={styles.heroSub}>Real, from your own cleanup history — nothing made up.</Text>
            </LinearGradient>

            <View style={styles.statsGrid}>
              <View style={styles.statCard}>
                <Text style={styles.statValue}>{report.total_cleanups}</Text>
                <Text style={styles.statLabel}>Cleanups</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={styles.statValue}>{report.current_streak_weeks}wk</Text>
                <Text style={styles.statLabel}>Streak</Text>
              </View>
              <View style={styles.statCard}>
                <View style={styles.statRow}>
                  <View style={[styles.statusDot, { backgroundColor: statusColor(report.status) }]} />
                  <Text style={styles.statValue}>{report.health_score}</Text>
                </View>
                <Text style={styles.statLabel}>{report.status}</Text>
              </View>
              <View style={styles.statCard}>
                <Text style={styles.statValue}>
                  {report.top_category ? report.top_category : `${report.days_until_full}d`}
                </Text>
                <Text style={styles.statLabel}>{report.top_category ? 'Top category' : 'Until full'}</Text>
              </View>
            </View>

            <View style={styles.linkRow}>
              <Text style={styles.linkText} numberOfLines={1} testID="report-link">
                {reportShareUrl(report.share_code)}
              </Text>
              <Pressable style={styles.linkBtn} onPress={() => onCopyLink(report)} testID="report-copy-link" hitSlop={8}>
                <Ionicons name={copied ? 'checkmark' : 'copy-outline'} size={16} color={theme.color.brand} />
              </Pressable>
            </View>
            <Text style={styles.linkHint}>Anyone with this link can view a read-only summary — no account needed.</Text>

            <Pressable style={styles.shareBtn} onPress={() => onShare(report)} testID="report-share">
              <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
              <Ionicons name="share-social" size={18} color={theme.color.onBrand} />
              <Text style={styles.shareBtnText}>Share my report</Text>
            </Pressable>

            <Pressable style={styles.regenBtn} onPress={onGenerate} disabled={generating} testID="report-regenerate">
              {generating ? (
                <ActivityIndicator size="small" color={theme.color.onSurface3} />
              ) : (
                <Text style={styles.regenBtnText}>Regenerate with latest stats</Text>
              )}
            </Pressable>
          </ScrollView>
        )}
      </SafeAreaView>
    </View>
  );
}

function NoReportView({ generating, onGenerate }: { generating: boolean; onGenerate: () => void }) {
  return (
    <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40, flexGrow: 1 }} showsVerticalScrollIndicator={false}>
      <LinearGradient colors={theme.gradients.brand} style={styles.hero} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
        <Ionicons name="share-social" size={36} color={theme.color.onBrand} />
        <Text style={styles.heroTitle}>Share your progress</Text>
        <Text style={styles.heroSub}>
          Generate a real recap of your cleanup history — total GB freed, streak, and more — with a link anyone can open, even without the app.
        </Text>
      </LinearGradient>

      <Pressable style={styles.createBtn} onPress={onGenerate} disabled={generating} testID="report-generate">
        <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
        {generating ? <ActivityIndicator color={theme.color.onBrand} /> : <Text style={styles.createBtnText}>Generate my report</Text>}
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  hero: { borderRadius: theme.radius.lg, padding: theme.space.xl, alignItems: 'center' },
  heroTitle: { color: theme.color.onBrand, fontSize: 20, fontWeight: '800', marginTop: 10, textAlign: 'center' },
  heroLabel: { color: 'rgba(2,44,34,0.75)', fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 1, marginTop: 10 },
  heroValue: { color: theme.color.onBrand, fontSize: 42, fontWeight: '800', letterSpacing: -1, marginTop: 2 },
  heroSub: { color: 'rgba(2,44,34,0.85)', fontSize: 13, textAlign: 'center', marginTop: 8, lineHeight: 18 },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: theme.space.sm, marginTop: theme.space.lg },
  statCard: { flexBasis: '47%', flexGrow: 1, backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, padding: theme.space.md, borderWidth: 1, borderColor: theme.color.border },
  statRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  statValue: { color: theme.color.onSurface, fontSize: 18, fontWeight: '800' },
  statLabel: { color: theme.color.onSurface2, fontSize: 11, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.6, marginTop: 4 },
  linkRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.border, paddingVertical: 10, paddingHorizontal: 14, marginTop: theme.space.lg },
  linkText: { flex: 1, color: theme.color.onSurface2, fontSize: 12 },
  linkBtn: { width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  linkHint: { color: theme.color.onSurface3, fontSize: 11, marginTop: 6, lineHeight: 15 },
  shareBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 54, borderRadius: theme.radius.pill, overflow: 'hidden', marginTop: theme.space.lg },
  shareBtnText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
  regenBtn: { alignItems: 'center', justifyContent: 'center', paddingVertical: theme.space.md, marginTop: theme.space.sm },
  regenBtnText: { color: theme.color.onSurface3, fontSize: 13, fontWeight: '600' },
  createBtn: { height: 54, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden', marginTop: theme.space.xl },
  createBtnText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
});
