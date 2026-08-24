import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  Pressable,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import Animated, { FadeInUp } from 'react-native-reanimated';
import { GlassCard } from '@/src/components/GlassCard';
import { api } from '@/src/api';
import { theme } from '@/src/theme';
import { useSubscription } from '@/src/lib/revenuecat';

type Msg = { role: 'user' | 'assistant'; content: string; created_at: string };
type Daily = {
  greeting: string;
  tip_title: string;
  tip_body: string;
  focus: string;
  action_label: string;
  action_route: string;
};

const focusIcon: Record<string, keyof typeof Ionicons.glyphMap> = {
  storage: 'server-outline',
  battery: 'battery-charging-outline',
  security: 'shield-checkmark-outline',
  photos: 'images-outline',
  general: 'sparkles-outline',
};

export default function Coach() {
  const router = useRouter();
  const { isSubscribed } = useSubscription();
  // Chat is a Pro feature. `__DEV__` is stripped to `false` in production
  // builds (including a production web build), so this only unlocks chat
  // for local/preview testing on web — never for real production users —
  // unlike a blanket `Platform.OS === 'web'` check, which would leave the
  // paywall bypassed for every real visitor on a live web deployment.
  const chatUnlocked = isSubscribed || (__DEV__ && Platform.OS === 'web');

  const [daily, setDaily] = useState<Daily | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<any>(null);
  const scrollRef = useRef<ScrollView>(null);

  const load = useCallback(async () => {
    try {
      const [d, h, hist] = await Promise.all([
        api.coachDaily().catch(() => null),
        api.health().catch(() => null),
        api.coachHistory().catch(() => []),
      ]);
      if (d) setDaily(d);
      if (h) setHealth(h);
      setMessages(hist || []);
    } catch (e) {
      console.log(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  useEffect(() => {
    const t = setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 120);
    return () => clearTimeout(t);
  }, [messages.length, sending]);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    if (!chatUnlocked) { router.push('/paywall'); return; }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    setInput('');
    const now = new Date().toISOString();
    setMessages((m) => [...m, { role: 'user', content: text, created_at: now }]);
    setSending(true);
    try {
      const reply = await api.coachChat({
        message: text,
        health_score: health?.score,
        storage_used_pct: health ? (health.storage_used_gb / health.storage_total_gb) * 100 : undefined,
        battery_health_pct: health?.battery_health_pct,
      });
      setMessages((m) => [...m, reply]);
    } catch (e) {
      setMessages((m) => [...m, {
        role: 'assistant',
        content: "I couldn't reach the coach right now. Please try again in a moment.",
        created_at: new Date().toISOString(),
      }]);
    } finally {
      setSending(false);
    }
  };

  const quickPrompts = [
    'Why is my phone slow?',
    'How do I free up space?',
    'Tips to save battery',
  ];

  return (
    <View style={styles.container}>
      <LinearGradient colors={theme.gradients.hero} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <View style={styles.header}>
          <View style={styles.headerIcon}>
            <Ionicons name="sparkles" size={20} color={theme.color.brand} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.headerTitle}>AI Health Coach</Text>
            <Text style={styles.headerSub}>Your personal device assistant</Text>
          </View>
          {messages.length > 0 && (
            <Pressable
              hitSlop={10}
              testID="coach-clear"
              onPress={async () => { await api.clearCoach().catch(() => {}); setMessages([]); }}
            >
              <Ionicons name="trash-outline" size={18} color={theme.color.onSurface3} />
            </Pressable>
          )}
        </View>

        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 8 : 0}
        >
          <ScrollView
            ref={scrollRef}
            style={{ flex: 1 }}
            contentContainerStyle={styles.scroll}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {loading ? (
              <ActivityIndicator color={theme.color.brand} style={{ marginTop: 40 }} />
            ) : (
              <>
                {daily && (
                  <Animated.View entering={FadeInUp.duration(400)}>
                    <GlassCard style={styles.dailyCard} testID="coach-daily-card">
                      <View style={styles.dailyTop}>
                        <View style={styles.dailyBadge}>
                          <Ionicons name={focusIcon[daily.focus] || 'sparkles-outline'} size={16} color={theme.color.onBrand} />
                        </View>
                        <Text style={styles.dailyGreeting}>{daily.greeting}</Text>
                      </View>
                      <Text style={styles.dailyTitle}>{daily.tip_title}</Text>
                      <Text style={styles.dailyBody}>{daily.tip_body}</Text>
                      <Pressable
                        style={styles.dailyAction}
                        testID="coach-daily-action"
                        onPress={() => { Haptics.selectionAsync().catch(() => {}); router.push(daily.action_route as any); }}
                      >
                        <Text style={styles.dailyActionText}>{daily.action_label}</Text>
                        <Ionicons name="arrow-forward" size={16} color={theme.color.onBrand} />
                      </Pressable>
                    </GlassCard>
                  </Animated.View>
                )}

                {messages.length === 0 && (
                  <View style={styles.emptyWrap}>
                    <Text style={styles.emptyTitle}>Ask me anything about your device</Text>
                    <View style={styles.chips}>
                      {quickPrompts.map((q) => (
                        <Pressable
                          key={q}
                          style={styles.chip}
                          testID={`coach-chip-${q}`}
                          onPress={() => { if (!chatUnlocked) { router.push('/paywall'); return; } setInput(q); }}
                      >
                        <Text style={styles.chipText}>{q}</Text>
                      </Pressable>
                    ))}
                  </View>
                </View>
              )}

                {messages.map((m, i) => (
                  <View
                    key={`${m.created_at}-${i}`}
                    style={[styles.bubbleRow, m.role === 'user' ? styles.rowRight : styles.rowLeft]}
                  >
                    {m.role === 'assistant' && (
                      <View style={styles.avatar}>
                        <Ionicons name="sparkles" size={14} color={theme.color.brand} />
                      </View>
                    )}
                    <View style={[styles.bubble, m.role === 'user' ? styles.userBubble : styles.aiBubble]}>
                      <Text style={m.role === 'user' ? styles.userText : styles.aiText}>{m.content}</Text>
                    </View>
                  </View>
                ))}

                {sending && (
                  <View style={[styles.bubbleRow, styles.rowLeft]}>
                    <View style={styles.avatar}>
                      <Ionicons name="sparkles" size={14} color={theme.color.brand} />
                    </View>
                    <View style={[styles.bubble, styles.aiBubble]}>
                      <ActivityIndicator color={theme.color.brand} size="small" />
                    </View>
                  </View>
                )}
              </>
            )}
          </ScrollView>

          {!chatUnlocked && !loading && (
            <Pressable style={styles.proLock} testID="coach-pro-lock" onPress={() => router.push('/paywall')}>
              <Ionicons name="lock-closed" size={16} color={theme.color.brand} />
              <Text style={styles.proLockText}>Chat with your Coach is a Pro feature</Text>
              <Text style={styles.proLockCta}>Upgrade</Text>
            </Pressable>
          )}

          <View style={styles.inputBar}>
            <TextInput
              style={styles.input}
              value={input}
              onChangeText={setInput}
              placeholder={chatUnlocked ? 'Ask your coach…' : 'Upgrade to Pro to chat'}
              placeholderTextColor={theme.color.onSurface3}
              editable={chatUnlocked && !sending}
              onSubmitEditing={send}
              returnKeyType="send"
              multiline
              maxLength={1000}
              testID="coach-input"
            />
            <Pressable
              style={[styles.sendBtn, (!input.trim() || sending) && styles.sendBtnDisabled]}
              onPress={send}
              disabled={!input.trim() || sending}
              testID="coach-send"
            >
              <Ionicons name="arrow-up" size={20} color={theme.color.onBrand} />
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.space.md,
    paddingHorizontal: theme.space.lg,
    paddingVertical: theme.space.md,
  },
  headerIcon: {
    width: 40, height: 40, borderRadius: 12,
    backgroundColor: 'rgba(16,185,129,0.12)',
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: theme.color.border,
  },
  headerTitle: { color: theme.color.onSurface, fontSize: 18, fontWeight: '800' },
  headerSub: { color: theme.color.onSurface3, fontSize: 12, marginTop: 1 },
  scroll: { paddingHorizontal: theme.space.lg, paddingBottom: theme.space.xl, gap: theme.space.md },
  dailyCard: { marginBottom: theme.space.sm },
  dailyTop: { flexDirection: 'row', alignItems: 'center', gap: theme.space.sm, marginBottom: theme.space.sm },
  dailyBadge: {
    width: 28, height: 28, borderRadius: 8,
    backgroundColor: theme.color.brand,
    alignItems: 'center', justifyContent: 'center',
  },
  dailyGreeting: { color: theme.color.onSurface2, fontSize: 13, fontWeight: '600', flex: 1 },
  dailyTitle: { color: theme.color.onSurface, fontSize: 18, fontWeight: '800', marginBottom: 6 },
  dailyBody: { color: theme.color.onSurface2, fontSize: 14, lineHeight: 20 },
  dailyAction: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: theme.color.brand,
    borderRadius: theme.radius.md,
    paddingVertical: 12,
    marginTop: theme.space.md,
  },
  dailyActionText: { color: theme.color.onBrand, fontSize: 14, fontWeight: '800' },
  emptyWrap: { marginTop: theme.space.md, gap: theme.space.md },
  emptyTitle: { color: theme.color.onSurface2, fontSize: 14, fontWeight: '600', textAlign: 'center' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: theme.space.sm, justifyContent: 'center' },
  chip: {
    backgroundColor: theme.color.surface3,
    borderWidth: 1, borderColor: theme.color.border,
    borderRadius: theme.radius.pill,
    paddingVertical: 8, paddingHorizontal: 14,
  },
  chipText: { color: theme.color.onSurface2, fontSize: 13, fontWeight: '500' },
  bubbleRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, maxWidth: '100%' },
  rowRight: { justifyContent: 'flex-end' },
  rowLeft: { justifyContent: 'flex-start' },
  avatar: {
    width: 26, height: 26, borderRadius: 13,
    backgroundColor: 'rgba(16,185,129,0.12)',
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: theme.color.border,
  },
  bubble: { maxWidth: '80%', borderRadius: 16, paddingVertical: 10, paddingHorizontal: 14 },
  userBubble: { backgroundColor: theme.color.brand, borderBottomRightRadius: 4 },
  aiBubble: {
    backgroundColor: theme.color.surface3,
    borderWidth: 1, borderColor: theme.color.border,
    borderBottomLeftRadius: 4,
  },
  userText: { color: theme.color.onBrand, fontSize: 14, lineHeight: 20, fontWeight: '500' },
  aiText: { color: theme.color.onSurface, fontSize: 14, lineHeight: 20 },
  proLock: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginHorizontal: theme.space.lg,
    marginBottom: theme.space.sm,
    paddingVertical: 10, paddingHorizontal: 14,
    borderRadius: theme.radius.md,
    backgroundColor: 'rgba(16,185,129,0.10)',
    borderWidth: 1, borderColor: theme.color.border,
  },
  proLockText: { color: theme.color.onSurface2, fontSize: 12, flex: 1 },
  proLockCta: { color: theme.color.brand, fontSize: 13, fontWeight: '800' },
  inputBar: {
    flexDirection: 'row', alignItems: 'flex-end', gap: theme.space.sm,
    paddingHorizontal: theme.space.lg,
    paddingTop: theme.space.sm,
    paddingBottom: Platform.OS === 'ios' ? theme.space.md : theme.space.lg,
    borderTopWidth: 0.5, borderTopColor: theme.color.border,
    backgroundColor: 'rgba(5,15,20,0.6)',
  },
  input: {
    flex: 1,
    maxHeight: 120,
    minHeight: 44,
    backgroundColor: theme.color.surface3,
    borderRadius: theme.radius.lg,
    borderWidth: 1, borderColor: theme.color.border,
    paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12,
    color: theme.color.onSurface,
    fontSize: 14,
  },
  sendBtn: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: theme.color.brand,
    alignItems: 'center', justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.4 },
});
