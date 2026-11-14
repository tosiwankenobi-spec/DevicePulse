import React, { useState } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, Linking, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSubscription } from '@/src/lib/revenuecat';
import { useAuth } from '@/src/AuthContext';
import { api } from '@/src/api';
import { PRO_TOOLS, PRO_ROUTINES } from '@/src/pro-content';
import { theme } from '@/src/theme';

export default function Pro() {
  const router = useRouter();
  const { user } = useAuth();
  const { isSubscribed, isLoading, retryVerification, verificationError } = useSubscription();
  const client = useQueryClient();
  const key = ['pro-routines', user?.user_id];
  const progress = useQuery({ queryKey: key, queryFn: () => api.proRoutines(), enabled: isSubscribed });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function toggle(routine: string, step: string, checked: boolean) {
    if (busy) return;
    setBusy(true); setError('');
    try { await api.updateProRoutine(routine, step, !checked); await client.invalidateQueries({ queryKey: key }); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not save progress.'); }
    finally { setBusy(false); }
  }
  return <SafeAreaView style={styles.page}>
    <View style={styles.header}>
      <Pressable accessibilityLabel="Back" onPress={() => router.back()}><Ionicons name="arrow-back" size={24} color={theme.color.onSurface} /></Pressable>
      <Text style={styles.title}>DevicePulse Pro</Text>
      <Ionicons name="sparkles" size={24} color={theme.color.brand} />
    </View>
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.subtitle}>{isSubscribed ? 'Your personal phone-care toolkit' : 'Guidance, continuity and real progress'}</Text>
      {isLoading && <ActivityIndicator color={theme.color.brand} />}
      {!isSubscribed && <Pressable style={styles.action} onPress={() => router.push('/paywall')}><Text style={styles.actionText}>View monthly & yearly plans</Text></Pressable>}
      {verificationError && <><Text style={styles.error}>{verificationError}</Text><Pressable onPress={() => retryVerification().catch(e => setError(String(e)))}><Text style={styles.link}>Retry verification</Text></Pressable></>}
      {PRO_TOOLS.map(tool => <Pressable key={tool.id} style={styles.tool} onPress={() => router.push(isSubscribed ? tool.route : '/paywall')}>
        <Ionicons name={tool.icon} size={24} color={theme.color.brand} />
        <View style={styles.grow}><Text style={styles.heading}>{tool.title}</Text><Text style={styles.body}>{tool.detail}</Text></View>
        <Ionicons name={isSubscribed ? 'chevron-forward' : 'lock-closed-outline'} size={18} color={theme.color.onSurface3} />
      </Pressable>)}
      <Text style={styles.section}>Guided care routines</Text>
      <Text style={styles.body}>Your checkmarks record your own review, not an automatic scan.</Text>
      {isSubscribed ? <>
        {progress.isLoading && <ActivityIndicator color={theme.color.brand} />}
        {progress.isError && <Pressable onPress={() => progress.refetch()}><Text style={styles.error}>Routine progress could not load. Tap to retry.</Text></Pressable>}
        {PRO_ROUTINES.map(routine => <View key={routine.id} style={styles.routine}>
          <Text style={styles.heading}>{routine.title}</Text><Text style={styles.body}>{routine.detail}</Text>
          {routine.steps.map(step => {
            const checked = progress.data?.some(row => row.routine_id === routine.id && row.step_id === step.id && row.completed) ?? false;
            return <View key={step.id} style={styles.step}>
              <Pressable accessibilityRole="checkbox" accessibilityState={{ checked }} accessibilityLabel={step.title} disabled={busy || !progress.isSuccess} onPress={() => toggle(routine.id, step.id, checked)}>
                <Ionicons name={checked ? 'checkbox' : 'square-outline'} size={24} color={theme.color.brand} />
              </Pressable>
              <View style={styles.grow}><Text style={styles.heading}>{step.title}</Text><Text style={styles.body}>{step.body}</Text>
                {'route' in step && <Pressable onPress={() => router.push(step.route)}><Text style={styles.link}>Open <Ionicons name="arrow-forward" /></Text></Pressable>}
              </View>
            </View>;
          })}
        </View>)}
      </> : PRO_ROUTINES.map(routine => <Pressable key={routine.id} style={styles.tool} onPress={() => router.push('/paywall')}><View style={styles.grow}><Text style={styles.heading}>{routine.title}</Text><Text style={styles.body}>{routine.detail}</Text></View><Ionicons name="lock-closed-outline" size={18} color={theme.color.brand} /></Pressable>)}
      {!!error && <Text style={styles.error}>{error}</Text>}
      <Pressable onPress={() => Linking.openURL('https://play.google.com/store/account/subscriptions?package=ca.verolane.devicepulse')}><Text style={styles.link}>Manage Google Play subscription</Text></Pressable>
      <Text style={styles.body}>No personal files are deleted by Pro routines. Coach needs an available AI service. Family members must each have Pro and choose to share.</Text>
    </ScrollView>
  </SafeAreaView>;
}
const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: theme.color.surface },
  header: { flexDirection: 'row', alignItems: 'center', gap: theme.space.md, padding: theme.space.lg },
  title: { flex: 1, color: theme.color.onSurface, fontSize: 24, fontWeight: '800' },
  content: { padding: theme.space.lg, paddingBottom: theme.space.xxxl, gap: theme.space.lg },
  subtitle: { color: theme.color.onSurface2, fontSize: 16 },
  tool: { flexDirection: 'row', alignItems: 'center', gap: theme.space.md, borderBottomWidth: 1, borderColor: theme.color.border, paddingVertical: theme.space.md },
  grow: { flex: 1 },
  heading: { color: theme.color.onSurface, fontSize: 15, fontWeight: '700' },
  body: { color: theme.color.onSurface2, fontSize: 13, lineHeight: 20, marginTop: theme.space.xs },
  section: { color: theme.color.onSurface, fontSize: 20, fontWeight: '800', marginTop: theme.space.md },
  routine: { gap: theme.space.sm, paddingVertical: theme.space.md, borderBottomWidth: 1, borderColor: theme.color.border },
  step: { flexDirection: 'row', gap: theme.space.md, paddingVertical: theme.space.md },
  link: { color: theme.color.brand, fontSize: 14, fontWeight: '700', paddingVertical: theme.space.sm },
  action: { backgroundColor: theme.color.brand, padding: theme.space.lg, borderRadius: theme.radius.sm, alignItems: 'center' },
  actionText: { color: theme.color.onBrand, fontWeight: '700' },
  error: { color: theme.color.error, fontSize: 13, lineHeight: 20 },
});
