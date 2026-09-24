import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { HealthRing } from '@/src/components/HealthRing';
import { scanLocalDevice } from '@/src/deviceStorage';
import { theme } from '@/src/theme';

export default function Guest() {
  const router = useRouter();
  const device = scanLocalDevice();
  const storagePct = device.storage_total_mb > 0 ? Math.round((device.storage_used_mb / device.storage_total_mb) * 100) : 0;
  const freeGb = (device.storage_free_mb / 1024).toFixed(1);
  const stats = [
    { label: 'Storage', value: `${storagePct}%`, icon: 'server-outline', color: theme.color.info },
    { label: 'Free space', value: `${freeGb} GB`, icon: 'folder-open-outline', color: '#8B5CF6' },
    { label: 'App cache', value: `${device.cache_mb.toFixed(1)} MB`, icon: 'flash-outline', color: theme.color.warning },
    { label: 'Security', value: 'Review', icon: 'shield-checkmark-outline', color: theme.color.brand },
  ] as const;

  return (
    <View style={styles.container} testID="guest-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.replace('/login')} hitSlop={12} testID="guest-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Preview</Text>
          <View style={{ width: 26 }} />
        </View>

        <ScrollView contentContainerStyle={{ paddingBottom: 120 }} showsVerticalScrollIndicator={false}>
          <View style={styles.hero}>
            <HealthRing score={device.health_before} />
            <Text style={styles.demoNote}>Live storage reading from this device</Text>
          </View>

          <View style={styles.grid}>
            {stats.map((s) => (
              <View key={s.label} style={styles.statCard}>
                <View style={[styles.statIcon, { backgroundColor: s.color + '22' }]}>
                  <Ionicons name={s.icon as any} size={20} color={s.color} />
                </View>
                <Text style={styles.statValue}>{s.value}</Text>
                <Text style={styles.statLabel}>{s.label}</Text>
              </View>
            ))}
          </View>

          <View style={styles.lockCard}>
            <Ionicons name="lock-closed" size={22} color={theme.color.brand} />
            <Text style={styles.lockTitle}>Unlock the full experience</Text>
            <Text style={styles.lockBody}>Sign in to save verified cleanup history, reminders, family tools and coaching across devices.</Text>
          </View>
        </ScrollView>

        <View style={styles.bottom}>
          <Pressable style={styles.cta} onPress={() => router.replace('/login')} testID="guest-signin-cta">
            <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
            <Text style={styles.ctaText}>Sign in to get started</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  hero: { alignItems: 'center', marginTop: theme.space.md },
  demoNote: { color: theme.color.onSurface2, fontSize: 13, marginTop: theme.space.md },
  grid: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: theme.space.md, marginTop: theme.space.lg, gap: theme.space.sm },
  statCard: { width: '48%', backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.lg, borderWidth: 1, borderColor: theme.color.border },
  statIcon: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  statValue: { color: theme.color.onSurface, fontSize: 22, fontWeight: '800' },
  statLabel: { color: theme.color.onSurface2, fontSize: 13, marginTop: 2 },
  lockCard: { alignItems: 'center', backgroundColor: theme.color.brand3, borderRadius: theme.radius.lg, padding: theme.space.xl, marginHorizontal: theme.space.lg, marginTop: theme.space.lg, gap: 6 },
  lockTitle: { color: theme.color.onSurface, fontSize: 17, fontWeight: '700', marginTop: 6 },
  lockBody: { color: theme.color.onSurface2, fontSize: 13, textAlign: 'center', lineHeight: 19 },
  bottom: { position: 'absolute', bottom: 0, left: 0, right: 0, padding: theme.space.lg, paddingBottom: 32, backgroundColor: theme.color.surface, borderTopWidth: 1, borderTopColor: theme.color.border },
  cta: { height: 54, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
});
