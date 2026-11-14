import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { api } from '@/src/api';
import { theme } from '@/src/theme';

function fmt(iso: string) {
  try { return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }); }
  catch { return iso; }
}

export default function Sessions() {
  const router = useRouter();
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try { setSessions(await api.sessions()); } catch (e) { console.log(e); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const revoke = async (sid: string) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setSessions((prev) => prev.filter((s) => s.sid !== sid));
    try { await api.revokeSession(sid); } catch (e) { console.log(e); }
  };

  return (
    <View style={styles.container} testID="sessions-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="sessions-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Active Devices</Text>
          <View style={{ width: 26 }} />
        </View>

        {loading ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : (
          <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
            <Text style={styles.lead}>These are the sessions currently signed in to your account. Revoke any you don&apos;t recognize.</Text>
            {sessions.map((s) => (
              <View key={s.sid} style={styles.card} testID={`session-${s.sid}`}>
                <View style={[styles.icon, { backgroundColor: (s.current ? theme.color.brand : theme.color.info) + '22' }]}>
                  <Ionicons name="phone-portrait-outline" size={22} color={s.current ? theme.color.brand : theme.color.info} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.name}>{s.current ? 'This device' : 'Signed-in device'}</Text>
                  <Text style={styles.meta}>Since {fmt(s.created_at)} · expires {fmt(s.expires_at)}</Text>
                </View>
                {s.current ? (
                  <View style={styles.currentBadge}><Text style={styles.currentText}>ACTIVE</Text></View>
                ) : (
                  <Pressable style={styles.revokeBtn} onPress={() => revoke(s.sid)} testID={`revoke-${s.sid}`}>
                    <Text style={styles.revokeText}>Sign out</Text>
                  </Pressable>
                )}
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
  lead: { color: theme.color.onSurface2, fontSize: 14, lineHeight: 20, marginBottom: theme.space.lg },
  card: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, padding: theme.space.md, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.sm },
  icon: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  name: { color: theme.color.onSurface, fontSize: 15, fontWeight: '600' },
  meta: { color: theme.color.onSurface3, fontSize: 12, marginTop: 2 },
  currentBadge: { backgroundColor: theme.color.brand3, paddingHorizontal: 8, paddingVertical: 4, borderRadius: theme.radius.pill },
  currentText: { color: theme.color.brand, fontSize: 10, fontWeight: '800' },
  revokeBtn: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: theme.radius.pill, borderWidth: 1, borderColor: theme.color.error + '66' },
  revokeText: { color: theme.color.error, fontSize: 13, fontWeight: '700' },
});
