import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  TextInput,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Share,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import * as Clipboard from 'expo-clipboard';
import { api } from '@/src/api';
import { theme } from '@/src/theme';

type Member = {
  user_id: string;
  name: string;
  is_owner: boolean;
  joined_at: string;
  score: number;
  status: string;
  streak_weeks: number;
  days_until_full: number;
};

type Group = {
  id: string;
  invite_code: string;
  is_owner: boolean;
  members: Member[];
};

const statusColor = (status: string) => {
  if (status === 'Excellent' || status === 'Good') return theme.color.brand;
  if (status === 'Needs Attention') return theme.color.warning;
  return theme.color.error;
};

export default function Family() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [group, setGroup] = useState<Group | null>(null);
  const [creating, setCreating] = useState(false);
  const [joining, setJoining] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [joinCode, setJoinCode] = useState('');
  const [joinError, setJoinError] = useState<string | null>(null);
  const [cleaningId, setCleaningId] = useState<string | null>(null);
  const [justCleanedId, setJustCleanedId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    try {
      setGroup(await api.familyGroup());
    } catch (e) {
      console.log(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const onCreate = async () => {
    if (creating) return;
    setCreating(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    try {
      const g = await api.createFamily();
      setGroup(g);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    } catch (e) {
      console.log(e);
    } finally {
      setCreating(false);
    }
  };

  const onLeave = async () => {
    if (leaving) return;
    setLeaving(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    try {
      await api.leaveFamily();
      setGroup(null);
    } catch (e) {
      console.log(e);
    } finally {
      setLeaving(false);
    }
  };

  const onJoin = async () => {
    const code = joinCode.trim();
    if (!code || joining) return;
    setJoining(true);
    setJoinError(null);
    try {
      const g = await api.joinFamily(code);
      setGroup(g);
      setJoinCode('');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    } catch (e: any) {
      setJoinError("Couldn't join — check the invite code and try again.");
    } finally {
      setJoining(false);
    }
  };

  const onShareCode = async (code: string) => {
    try {
      await Share.share({ message: `Join my DevicePulse family plan! Use invite code ${code} in the app.` });
    } catch (e) { console.log(e); }
  };

  const onCopyCode = async (code: string) => {
    await Clipboard.setStringAsync(code);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const onRemoteClean = async (memberId: string) => {
    if (cleaningId) return;
    setCleaningId(memberId);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    try {
      const result = await api.familyRemoteClean(memberId);
      setGroup((cur) => {
        if (!cur) return cur;
        return {
          ...cur,
          members: cur.members.map((m) => (m.user_id === memberId && result.member ? result.member : m)),
        };
      });
      setJustCleanedId(memberId);
      setTimeout(() => setJustCleanedId(null), 2500);
    } catch (e) {
      console.log(e);
    } finally {
      setCleaningId(null);
    }
  };

  return (
    <View style={styles.container} testID="family-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="family-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Family Dashboard</Text>
          <View style={{ width: 26 }} />
        </View>

        {loading ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : !group ? (
          <NoGroupView
            creating={creating}
            joining={joining}
            joinCode={joinCode}
            joinError={joinError}
            setJoinCode={setJoinCode}
            onCreate={onCreate}
            onJoin={onJoin}
          />
        ) : (
          <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
            <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
              <LinearGradient colors={theme.gradients.brand} style={styles.hero} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
                <Ionicons name="people" size={32} color={theme.color.onBrand} />
                <Text style={styles.heroTitle}>{group.members.length} of 5 devices linked</Text>
                <Text style={styles.heroSub}>Real accounts, real live data — not just names on a list.</Text>
                <View style={styles.codeRow}>
                  <Text style={styles.codeText} testID="family-invite-code">{group.invite_code}</Text>
                  <Pressable style={styles.codeBtn} onPress={() => onCopyCode(group.invite_code)} testID="family-copy-code" hitSlop={8}>
                    <Ionicons name={copied ? 'checkmark' : 'copy-outline'} size={16} color={theme.color.onBrand} />
                  </Pressable>
                  <Pressable style={styles.codeBtn} onPress={() => onShareCode(group.invite_code)} testID="family-share-code" hitSlop={8}>
                    <Ionicons name="share-outline" size={16} color={theme.color.onBrand} />
                  </Pressable>
                </View>
              </LinearGradient>

              <Text style={styles.section}>Members ({group.members.length}/5)</Text>

              {group.members.map((m) => (
                <View key={m.user_id} style={styles.memberCard} testID={`member-${m.user_id}`}>
                  <View style={styles.memberTop}>
                    <View style={[styles.memberIcon, { backgroundColor: m.is_owner ? theme.color.brand : theme.color.surface3 }]}>
                      <Ionicons name="person" size={18} color={m.is_owner ? theme.color.onBrand : theme.color.brand} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.memberName}>{m.name}</Text>
                      <View style={styles.statRow}>
                        <View style={[styles.statusDot, { backgroundColor: statusColor(m.status) }]} />
                        <Text style={styles.memberMeta}>{m.status} · {m.score}/100</Text>
                      </View>
                    </View>
                    {m.is_owner && <View style={styles.ownerBadge}><Text style={styles.ownerBadgeText}>OWNER</Text></View>}
                  </View>

                  <View style={styles.metricsRow}>
                    <View style={styles.metric}>
                      <Ionicons name="flame" size={14} color={theme.color.warning} />
                      <Text style={styles.metricText}>{m.streak_weeks}wk streak</Text>
                    </View>
                    <View style={styles.metric}>
                      <Ionicons name="trending-up" size={14} color={theme.color.info} />
                      <Text style={styles.metricText}>{m.days_until_full}d until full</Text>
                    </View>
                  </View>

                  {group.is_owner && !m.is_owner && (
                    <Pressable
                      style={[styles.remoteBtn, cleaningId === m.user_id && styles.remoteBtnDisabled]}
                      onPress={() => onRemoteClean(m.user_id)}
                      disabled={cleaningId === m.user_id}
                      testID={`remote-clean-${m.user_id}`}
                    >
                      {cleaningId === m.user_id ? (
                        <ActivityIndicator size="small" color={theme.color.brand} />
                      ) : justCleanedId === m.user_id ? (
                        <>
                          <Ionicons name="checkmark-circle" size={16} color={theme.color.brand} />
                          <Text style={styles.remoteBtnText}>Cleaned remotely</Text>
                        </>
                      ) : (
                        <>
                          <Ionicons name="cloud-download-outline" size={16} color={theme.color.brand} />
                          <Text style={styles.remoteBtnText}>Clean their device remotely</Text>
                        </>
                      )}
                    </Pressable>
                  )}
                </View>
              ))}

              <Pressable style={styles.leaveBtn} onPress={onLeave} disabled={leaving} testID="family-leave">
                {leaving ? (
                  <ActivityIndicator size="small" color={theme.color.onSurface3} />
                ) : (
                  <Text style={styles.leaveBtnText}>
                    {group.is_owner && group.members.length > 1 ? 'Leave (transfers ownership)' : 'Leave family plan'}
                  </Text>
                )}
              </Pressable>
            </ScrollView>
          </KeyboardAvoidingView>
        )}
      </SafeAreaView>
    </View>
  );
}

function NoGroupView({
  creating,
  joining,
  joinCode,
  joinError,
  setJoinCode,
  onCreate,
  onJoin,
}: {
  creating: boolean;
  joining: boolean;
  joinCode: string;
  joinError: string | null;
  setJoinCode: (v: string) => void;
  onCreate: () => void;
  onJoin: () => void;
}) {
  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
        <LinearGradient colors={theme.gradients.brand} style={styles.hero} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
          <Ionicons name="people" size={36} color={theme.color.onBrand} />
          <Text style={styles.heroTitle}>Manage your family's devices</Text>
          <Text style={styles.heroSub}>See everyone's real storage, streak, and forecast — and clean up a member's device remotely, in one tap.</Text>
        </LinearGradient>

        <Pressable style={styles.createBtn} onPress={onCreate} disabled={creating} testID="family-create">
          <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
          {creating ? <ActivityIndicator color={theme.color.onBrand} /> : <Text style={styles.createBtnText}>Start a family plan</Text>}
        </Pressable>

        <Text style={styles.orText}>or join one with an invite code</Text>

        <View style={styles.joinRow}>
          <TextInput
            style={styles.joinInput}
            placeholder="FAM-XXXXXX"
            placeholderTextColor={theme.color.onSurface3}
            value={joinCode}
            onChangeText={(t) => setJoinCode(t.toUpperCase())}
            autoCapitalize="characters"
            testID="family-join-input"
          />
          <Pressable
            style={[styles.joinBtn, (!joinCode.trim() || joining) && { opacity: 0.5 }]}
            onPress={onJoin}
            disabled={!joinCode.trim() || joining}
            testID="family-join-button"
          >
            {joining ? <ActivityIndicator color={theme.color.onBrand} size="small" /> : <Text style={styles.joinBtnText}>Join</Text>}
          </Pressable>
        </View>
        {joinError && <Text style={styles.joinErrorText}>{joinError}</Text>}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  hero: { borderRadius: theme.radius.lg, padding: theme.space.xl, alignItems: 'center' },
  heroTitle: { color: theme.color.onBrand, fontSize: 20, fontWeight: '800', marginTop: 10, textAlign: 'center' },
  heroSub: { color: 'rgba(2,44,34,0.85)', fontSize: 13, textAlign: 'center', marginTop: 6, lineHeight: 18 },
  codeRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: theme.space.lg, backgroundColor: 'rgba(2,44,34,0.18)', borderRadius: theme.radius.pill, paddingVertical: 8, paddingHorizontal: 14 },
  codeText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '800', letterSpacing: 1 },
  codeBtn: { width: 26, height: 26, borderRadius: 13, backgroundColor: 'rgba(2,44,34,0.25)', alignItems: 'center', justifyContent: 'center' },
  section: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '700', letterSpacing: 1.1, textTransform: 'uppercase', marginTop: theme.space.xl, marginBottom: theme.space.md },
  memberCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, padding: theme.space.md, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.sm },
  memberTop: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  memberIcon: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  memberName: { color: theme.color.onSurface, fontSize: 15, fontWeight: '600' },
  statRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 3 },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  memberMeta: { color: theme.color.onSurface2, fontSize: 12 },
  ownerBadge: { backgroundColor: theme.color.brand3, paddingHorizontal: 8, paddingVertical: 3, borderRadius: theme.radius.pill },
  ownerBadgeText: { color: theme.color.brand, fontSize: 10, fontWeight: '800' },
  metricsRow: { flexDirection: 'row', gap: theme.space.lg, marginTop: theme.space.md, paddingTop: theme.space.md, borderTopWidth: 1, borderTopColor: theme.color.border },
  metric: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  metricText: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '600' },
  remoteBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    marginTop: theme.space.md, paddingVertical: 10, borderRadius: theme.radius.md,
    backgroundColor: 'rgba(16,185,129,0.10)', borderWidth: 1, borderColor: theme.color.brand,
  },
  remoteBtnDisabled: { opacity: 0.6 },
  remoteBtnText: { color: theme.color.brand, fontSize: 13, fontWeight: '700' },
  leaveBtn: { alignItems: 'center', justifyContent: 'center', paddingVertical: theme.space.md, marginTop: theme.space.md },
  leaveBtnText: { color: theme.color.onSurface3, fontSize: 13, fontWeight: '600' },
  createBtn: { height: 54, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden', marginTop: theme.space.xl },
  createBtnText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
  orText: { color: theme.color.onSurface3, fontSize: 13, textAlign: 'center', marginTop: theme.space.lg, marginBottom: theme.space.md },
  joinRow: { flexDirection: 'row', gap: theme.space.sm },
  joinInput: {
    flex: 1, backgroundColor: theme.color.surface3, borderRadius: theme.radius.md,
    paddingHorizontal: theme.space.md, height: 50, color: theme.color.onSurface, fontSize: 15,
    borderWidth: 1, borderColor: theme.color.border, letterSpacing: 1,
  },
  joinBtn: { paddingHorizontal: theme.space.xl, borderRadius: theme.radius.md, backgroundColor: theme.color.brand, alignItems: 'center', justifyContent: 'center' },
  joinBtnText: { color: theme.color.onBrand, fontSize: 15, fontWeight: '700' },
  joinErrorText: { color: theme.color.error, fontSize: 13, marginTop: theme.space.sm, textAlign: 'center' },
});
