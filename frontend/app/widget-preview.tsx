import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/src/theme';

type Size = 'small' | 'medium';

export default function WidgetPreview() {
  const router = useRouter();
  const [size, setSize] = useState<Size>('medium');

  return (
    <View style={styles.container} testID="widget-preview-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="widget-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Home Screen Widget</Text>
          <View style={{ width: 26 }} />
        </View>

        <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
          <Text style={styles.lead}>Keep your device health one glance away — right on your home screen.</Text>

          {/* Size toggle */}
          <View style={styles.sizeToggle}>
            {(['small', 'medium'] as Size[]).map((s) => (
              <Pressable key={s} style={[styles.sizeBtn, size === s && styles.sizeBtnActive]} onPress={() => setSize(s)} testID={`widget-size-${s}`}>
                <Text style={[styles.sizeText, size === s && styles.sizeTextActive]}>{s === 'small' ? 'Small' : 'Medium'}</Text>
              </Pressable>
            ))}
          </View>

          {/* Wallpaper mock */}
          <LinearGradient colors={['#1a2f3a', '#0d1f28', '#08161d']} style={styles.wallpaper}>
            {/* faux app icons */}
            <View style={styles.iconRow}>
              {['#F59E0B', '#0EA5E9', '#EF4444', '#8B5CF6'].map((c, i) => (
                <View key={i} style={[styles.appIcon, { backgroundColor: c }]} />
              ))}
            </View>

            {size === 'small' ? <SmallWidget /> : <MediumWidget />}

            <View style={styles.iconRow}>
              {['#10B981', '#EC4899', '#64748B', '#0EA5E9'].map((c, i) => (
                <View key={i} style={[styles.appIcon, { backgroundColor: c }]} />
              ))}
            </View>
          </LinearGradient>

          <View style={styles.infoCard}>
            <Ionicons name="information-circle-outline" size={20} color={theme.color.info} />
            <Text style={styles.infoText}>
              Widgets update automatically after each scan. Add one from your home screen once you install the built app.
            </Text>
          </View>

          <Pressable style={styles.cta} onPress={() => router.back()} testID="widget-done">
            <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
            <Text style={styles.ctaText}>Looks great</Text>
          </Pressable>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const SmallWidget = () => (
  <View style={styles.smallWidget} testID="widget-small">
    <LinearGradient colors={theme.gradients.hero2} style={StyleSheet.absoluteFill} />
    <View style={styles.miniRing}>
      <Text style={styles.miniScore}>68</Text>
    </View>
    <Text style={styles.widgetLabel}>DevicePulse</Text>
    <Text style={styles.widgetSub}>Needs attention</Text>
  </View>
);

const MediumWidget = () => (
  <View style={styles.mediumWidget} testID="widget-medium">
    <LinearGradient colors={theme.gradients.hero2} style={StyleSheet.absoluteFill} />
    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
      <View style={styles.miniRing}>
        <Text style={styles.miniScore}>68</Text>
      </View>
      <View style={{ flex: 1, marginLeft: 14 }}>
        <Text style={styles.widgetLabel}>Device Health</Text>
        <View style={styles.miniStat}>
          <Ionicons name="server-outline" size={13} color={theme.color.info} />
          <Text style={styles.miniStatText}>Storage 74%</Text>
        </View>
        <View style={styles.miniStat}>
          <Ionicons name="battery-half-outline" size={13} color={theme.color.warning} />
          <Text style={styles.miniStatText}>Battery 54%</Text>
        </View>
        <View style={styles.miniStat}>
          <Ionicons name="shield-checkmark-outline" size={13} color={theme.color.brand} />
          <Text style={styles.miniStatText}>Secure</Text>
        </View>
      </View>
    </View>
  </View>
);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  lead: { color: theme.color.onSurface2, fontSize: 14, lineHeight: 20, marginBottom: theme.space.lg },
  sizeToggle: { flexDirection: 'row', backgroundColor: theme.color.surface2, borderRadius: theme.radius.pill, padding: 4, alignSelf: 'center', borderWidth: 1, borderColor: theme.color.border },
  sizeBtn: { paddingHorizontal: 28, paddingVertical: 8, borderRadius: theme.radius.pill },
  sizeBtnActive: { backgroundColor: theme.color.brand },
  sizeText: { color: theme.color.onSurface2, fontSize: 14, fontWeight: '600' },
  sizeTextActive: { color: theme.color.onBrand, fontWeight: '700' },
  wallpaper: { borderRadius: 32, padding: theme.space.xl, marginTop: theme.space.xl, alignItems: 'center', gap: theme.space.xl, borderWidth: 1, borderColor: theme.color.border },
  iconRow: { flexDirection: 'row', gap: 18 },
  appIcon: { width: 44, height: 44, borderRadius: 12, opacity: 0.7 },
  smallWidget: { width: 150, height: 150, borderRadius: 24, overflow: 'hidden', alignItems: 'center', justifyContent: 'center', gap: 6, borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  mediumWidget: { width: 300, height: 150, borderRadius: 24, overflow: 'hidden', justifyContent: 'center', padding: theme.space.lg, borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  miniRing: { width: 66, height: 66, borderRadius: 33, borderWidth: 6, borderColor: theme.color.brand, borderRightColor: theme.color.border, borderBottomColor: theme.color.border, alignItems: 'center', justifyContent: 'center', transform: [{ rotate: '-45deg' }] },
  miniScore: { color: theme.color.onSurface, fontSize: 24, fontWeight: '800', transform: [{ rotate: '45deg' }] },
  widgetLabel: { color: theme.color.onSurface, fontSize: 15, fontWeight: '700' },
  widgetSub: { color: theme.color.onSurface2, fontSize: 12 },
  miniStat: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  miniStatText: { color: theme.color.onSurface2, fontSize: 12 },
  infoCard: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, padding: theme.space.md, marginTop: theme.space.xl, borderWidth: 1, borderColor: theme.color.border },
  infoText: { color: theme.color.onSurface2, fontSize: 13, flex: 1, lineHeight: 19 },
  cta: { height: 54, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden', marginTop: theme.space.lg },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
});
