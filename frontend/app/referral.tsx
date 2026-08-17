import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Share, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import * as Clipboard from 'expo-clipboard';
import { api } from '@/src/api';
import { getDeviceId } from '@/src/device';
import { theme } from '@/src/theme';

export default function Referral() {
  const router = useRouter();
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [deviceId, setDeviceId] = useState('');

  const load = async () => {
    const id = await getDeviceId();
    setDeviceId(id);
    try { setStatus(await api.referral()); } catch (e) { console.log(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const onShare = async () => {
    if (!status) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    try {
      await Share.share({
        message: `I'm keeping my phone fast with DevicePulse! Use my code ${status.code} and we both get a free week of Pro. Download: https://devicepulse.app`,
      });
      const updated = await api.recordInvite();
      setStatus(updated);
    } catch (e) { console.log(e); }
  };

  const onCopy = async () => {
    if (!status) return;
    await Clipboard.setStringAsync(status.code);
    Haptics.selectionAsync();
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  const invited = status?.invited_count ?? 0;
  const reward = status?.reward_days ?? 0;
  const nextMilestone = Math.max(1, invited + 1);

  return (
    <View style={styles.container} testID="referral-screen">
      <LinearGradient colors={theme.gradients.hero2} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="referral-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Refer a Friend</Text>
          <View style={{ width: 26 }} />
        </View>

        {loading ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : (
          <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
            <View style={styles.heroIcon}>
              <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} />
              <Ionicons name="gift" size={54} color={theme.color.onBrand} />
            </View>
            <Text style={styles.heroTitle}>Give a week, get a week</Text>
            <Text style={styles.heroSub}>
              Invite a friend to DevicePulse. When they join with your code, you both unlock 7 days of Pro — free.
            </Text>

            {/* Reward tracker */}
            <View style={styles.rewardCard}>
              <View style={styles.rewardRow}>
                <View style={{ alignItems: 'center', flex: 1 }}>
                  <Text style={styles.rewardValue} testID="referral-invited-count">{invited}</Text>
                  <Text style={styles.rewardLabel}>Friends joined</Text>
                </View>
                <View style={styles.rewardDivider} />
                <View style={{ alignItems: 'center', flex: 1 }}>
                  <Text style={[styles.rewardValue, { color: theme.color.brand }]}>{reward}</Text>
                  <Text style={styles.rewardLabel}>Pro days earned</Text>
                </View>
              </View>
              <View style={styles.progressTrack}>
                <View style={[styles.progressFill, { width: `${((invited % 5) / 5) * 100}%` }]} />
              </View>
              <Text style={styles.milestone}>{nextMilestone} more invite{nextMilestone > 1 ? 's' : ''} toward your next reward</Text>
            </View>

            {/* Code */}
            <Text style={styles.section}>Your code</Text>
            <Pressable style={styles.codeBox} onPress={onCopy} testID="referral-copy-code">
              <Text style={styles.code}>{status?.code}</Text>
              <View style={styles.copyBtn}>
                <Ionicons name={copied ? 'checkmark' : 'copy-outline'} size={16} color={theme.color.brand} />
                <Text style={styles.copyText}>{copied ? 'Copied' : 'Copy'}</Text>
              </View>
            </Pressable>

            <Pressable style={styles.shareBtn} onPress={onShare} testID="referral-share-button">
              <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
              <Ionicons name="share-social" size={20} color={theme.color.onBrand} />
              <Text style={styles.shareText}>Share invite</Text>
            </Pressable>

            {/* How it works */}
            <Text style={styles.section}>How it works</Text>
            {[
              { icon: 'send', t: 'Share your code', d: 'Send your unique code to friends and family.' },
              { icon: 'download', t: 'They join', d: 'Your friend installs DevicePulse and enters your code.' },
              { icon: 'sparkles', t: 'You both win', d: 'Each of you gets 7 days of Pro instantly.' },
            ].map((s, i) => (
              <View key={i} style={styles.stepRow}>
                <View style={styles.stepIcon}><Ionicons name={s.icon as any} size={18} color={theme.color.brand} /></View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.stepTitle}>{s.t}</Text>
                  <Text style={styles.stepDesc}>{s.d}</Text>
                </View>
              </View>
            ))}
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
  heroIcon: { width: 100, height: 100, borderRadius: 50, alignItems: 'center', justifyContent: 'center', overflow: 'hidden', alignSelf: 'center', marginTop: theme.space.md },
  heroTitle: { color: theme.color.onSurface, fontSize: 24, fontWeight: '800', textAlign: 'center', marginTop: theme.space.lg, letterSpacing: -0.5 },
  heroSub: { color: theme.color.onSurface2, fontSize: 14, textAlign: 'center', marginTop: 8, lineHeight: 20, paddingHorizontal: theme.space.md },
  rewardCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.lg, borderWidth: 1, borderColor: theme.color.border, marginTop: theme.space.xl },
  rewardRow: { flexDirection: 'row', alignItems: 'center' },
  rewardValue: { color: theme.color.onSurface, fontSize: 32, fontWeight: '800' },
  rewardLabel: { color: theme.color.onSurface2, fontSize: 12, marginTop: 2 },
  rewardDivider: { width: 1, height: 40, backgroundColor: theme.color.border },
  progressTrack: { height: 8, borderRadius: 4, backgroundColor: theme.color.surface3, marginTop: theme.space.lg, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: theme.color.brand, borderRadius: 4 },
  milestone: { color: theme.color.onSurface3, fontSize: 12, marginTop: 8, textAlign: 'center' },
  section: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '700', letterSpacing: 1.1, textTransform: 'uppercase', marginTop: theme.space.xl, marginBottom: theme.space.sm },
  codeBox: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.brand3, borderStyle: 'dashed', paddingVertical: theme.space.md, paddingHorizontal: theme.space.lg },
  code: { color: theme.color.onSurface, fontSize: 22, fontWeight: '800', letterSpacing: 2 },
  copyBtn: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  copyText: { color: theme.color.brand, fontSize: 13, fontWeight: '700' },
  shareBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 54, borderRadius: theme.radius.pill, overflow: 'hidden', marginTop: theme.space.md },
  shareText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
  stepRow: { flexDirection: 'row', gap: 12, alignItems: 'center', marginBottom: theme.space.md },
  stepIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: theme.color.brand3, alignItems: 'center', justifyContent: 'center' },
  stepTitle: { color: theme.color.onSurface, fontSize: 15, fontWeight: '600' },
  stepDesc: { color: theme.color.onSurface2, fontSize: 13, marginTop: 2, lineHeight: 18 },
});
