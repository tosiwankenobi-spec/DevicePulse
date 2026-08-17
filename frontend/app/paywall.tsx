import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/src/theme';

const FEATURES = [
  { icon: 'scan', label: 'Auto Smart Scan', pro: true },
  { icon: 'infinite', label: 'Unlimited duplicate cleanup', pro: true },
  { icon: 'shield-checkmark', label: 'Advanced security scan', pro: true },
  { icon: 'battery-charging', label: 'Battery optimizer', pro: true },
  { icon: 'time', label: 'Scheduled cleanups', pro: true },
  { icon: 'headset', label: 'Priority support', pro: true },
] as const;

export default function Paywall() {
  const router = useRouter();
  const [plan, setPlan] = useState<'monthly' | 'yearly'>('yearly');

  return (
    <View style={styles.container} testID="paywall-screen">
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.hero}>
          <Image
            source="https://images.unsplash.com/photo-1774385439710-6cb1d8a9141d?w=800"
            style={StyleSheet.absoluteFill}
            contentFit="cover"
          />
          <LinearGradient
            colors={['transparent', 'rgba(5,15,20,0.85)', theme.color.surface]}
            style={StyleSheet.absoluteFill}
          />
          <Pressable style={styles.close} onPress={() => router.back()} hitSlop={12} testID="paywall-close">
            <Ionicons name="close" size={22} color={theme.color.onSurface} />
          </Pressable>
          <View style={styles.heroContent}>
            <View style={styles.proBadge}>
              <Ionicons name="sparkles" size={12} color={theme.color.onBrand} />
              <Text style={styles.proBadgeText}>DEVICEPULSE PRO</Text>
            </View>
            <Text style={styles.heroTitle}>Deeper cleanup.{'\n'}Faster device.</Text>
            <Text style={styles.heroSub}>Unlock the tools that keep your device running like new.</Text>
          </View>
        </View>

        <ScrollView contentContainerStyle={{ paddingBottom: 32 }}>
          <View style={styles.featureList}>
            {FEATURES.map((f, i) => (
              <View key={i} style={styles.featureRow}>
                <View style={styles.featureIcon}>
                  <Ionicons name={f.icon as any} size={18} color={theme.color.brand} />
                </View>
                <Text style={styles.featureText}>{f.label}</Text>
                <Ionicons name="checkmark-circle" size={20} color={theme.color.brand} />
              </View>
            ))}
          </View>

          {/* Plans */}
          <View style={styles.plans}>
            <Pressable
              style={[styles.plan, plan === 'monthly' && styles.planActive]}
              onPress={() => setPlan('monthly')}
              testID="plan-monthly"
            >
              <Text style={styles.planLabel}>Monthly</Text>
              <Text style={styles.planPrice}>$4.99</Text>
              <Text style={styles.planPer}>per month</Text>
            </Pressable>
            <Pressable
              style={[styles.plan, plan === 'yearly' && styles.planActive]}
              onPress={() => setPlan('yearly')}
              testID="plan-yearly"
            >
              <View style={styles.saveTag}>
                <Text style={styles.saveTagText}>SAVE 58%</Text>
              </View>
              <Text style={styles.planLabel}>Yearly</Text>
              <Text style={styles.planPrice}>$24.99</Text>
              <Text style={styles.planPer}>$2.08 / month</Text>
            </Pressable>
          </View>

          <Pressable style={styles.cta} onPress={() => router.back()} testID="paywall-cta">
            <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
            <Text style={styles.ctaText}>Start 7-day free trial</Text>
          </Pressable>
          <Text style={styles.disclaimer}>Cancel anytime. Auto-renews unless canceled 24h before period ends.</Text>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  hero: { height: 320, overflow: 'hidden' },
  close: { position: 'absolute', top: 12, right: 16, width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(0,0,0,0.5)', alignItems: 'center', justifyContent: 'center', zIndex: 2 },
  heroContent: { position: 'absolute', bottom: 20, left: 0, right: 0, paddingHorizontal: theme.space.lg },
  proBadge: { flexDirection: 'row', alignSelf: 'flex-start', alignItems: 'center', gap: 4, backgroundColor: theme.color.brand, paddingHorizontal: 10, paddingVertical: 5, borderRadius: theme.radius.pill },
  proBadgeText: { color: theme.color.onBrand, fontSize: 10, fontWeight: '800', letterSpacing: 0.8 },
  heroTitle: { color: theme.color.onSurface, fontSize: 30, fontWeight: '800', letterSpacing: -0.8, marginTop: 12, lineHeight: 34 },
  heroSub: { color: theme.color.onSurface2, fontSize: 14, marginTop: 8, lineHeight: 20 },
  featureList: { paddingHorizontal: theme.space.lg, gap: 12, marginTop: theme.space.md },
  featureRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.border },
  featureIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: theme.color.brand3, alignItems: 'center', justifyContent: 'center' },
  featureText: { color: theme.color.onSurface, fontSize: 14, fontWeight: '600', flex: 1 },
  plans: { flexDirection: 'row', gap: 10, paddingHorizontal: theme.space.lg, marginTop: theme.space.xl },
  plan: { flex: 1, padding: theme.space.md, borderRadius: theme.radius.lg, borderWidth: 2, borderColor: theme.color.border, backgroundColor: theme.color.surface2 },
  planActive: { borderColor: theme.color.brand, backgroundColor: theme.color.brand3 },
  planLabel: { color: theme.color.onSurface, fontSize: 13, fontWeight: '700' },
  planPrice: { color: theme.color.onSurface, fontSize: 24, fontWeight: '800', marginTop: 4, letterSpacing: -0.5 },
  planPer: { color: theme.color.onSurface2, fontSize: 11, marginTop: 2 },
  saveTag: { position: 'absolute', top: -10, right: 10, backgroundColor: theme.color.brand, paddingHorizontal: 8, paddingVertical: 3, borderRadius: theme.radius.pill },
  saveTagText: { color: theme.color.onBrand, fontSize: 9, fontWeight: '800' },
  cta: { marginHorizontal: theme.space.lg, marginTop: theme.space.xl, height: 56, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
  disclaimer: { color: theme.color.onSurface3, fontSize: 11, textAlign: 'center', marginTop: 12, paddingHorizontal: theme.space.xl, lineHeight: 15 },
});
