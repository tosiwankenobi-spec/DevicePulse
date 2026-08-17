import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import Animated, { useSharedValue, useAnimatedStyle, withRepeat, withTiming, Easing, FadeIn } from 'react-native-reanimated';
import { HealthRing } from '@/src/components/HealthRing';
import { api } from '@/src/api';
import { theme } from '@/src/theme';

const STEPS = ['Scanning junk files', 'Finding duplicates', 'Analyzing large files', 'Checking cache', 'Optimizing performance'];

export default function SmartScan() {
  const router = useRouter();
  const [progress, setProgress] = useState(0);
  const [stepIdx, setStepIdx] = useState(0);
  const [done, setDone] = useState(false);
  const [result, setResult] = useState<any>(null);
  const rot = useSharedValue(0);

  useEffect(() => {
    rot.value = withRepeat(withTiming(360, { duration: 3000, easing: Easing.linear }), -1);

    const total = 5000;
    const startedAt = Date.now();
    const iv = setInterval(() => {
      const p = Math.min(100, ((Date.now() - startedAt) / total) * 100);
      setProgress(p);
      setStepIdx(Math.min(STEPS.length - 1, Math.floor((p / 100) * STEPS.length)));
      if (p >= 100) {
        clearInterval(iv);
        api.runScan().then((r) => {
          setResult(r);
          setDone(true);
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        }).catch(() => setDone(true));
      }
    }, 80);
    return () => clearInterval(iv);
  }, []);

  const ringStyle = useAnimatedStyle(() => ({ transform: [{ rotate: `${rot.value}deg` }] }));

  const onSeeResults = () => {
    if (result) router.replace({ pathname: '/results', params: { data: JSON.stringify(result) } });
  };

  return (
    <View style={styles.container} testID="smart-scan-screen">
      <LinearGradient colors={theme.gradients.hero2} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="scan-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Smart Scan</Text>
          <View style={{ width: 26 }} />
        </View>

        <View style={styles.center}>
          <Animated.View style={[styles.ringOuter, ringStyle]}>
            <View style={styles.ringSegment} />
            <View style={[styles.ringSegment, { transform: [{ rotate: '120deg' }] }]} />
            <View style={[styles.ringSegment, { transform: [{ rotate: '240deg' }] }]} />
          </Animated.View>
          <View style={styles.ringInner}>
            <HealthRing score={progress} size={200} label={done ? 'Complete' : 'Scanning'} />
          </View>
        </View>

        <View style={styles.bottom}>
          <Text style={styles.status} testID="scan-status">
            {done ? 'Scan complete' : STEPS[stepIdx]}
          </Text>
          {!done && (
            <Text style={styles.substatus}>Reviewing your device — nothing changed yet</Text>
          )}
          {done && result && (
            <Animated.View entering={FadeIn.duration(400)} style={styles.foundBox}>
              <Text style={styles.foundLabel}>Reclaimable</Text>
              <Text style={styles.foundValue}>{(result.total_reclaimable_mb / 1024).toFixed(2)} GB</Text>
            </Animated.View>
          )}
          {done && (
            <Pressable style={styles.cta} onPress={onSeeResults} testID="review-clean-button">
              <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
              <Text style={styles.ctaText}>Review & Clean</Text>
              <Ionicons name="arrow-forward" size={18} color={theme.color.onBrand} />
            </Pressable>
          )}
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  ringOuter: { position: 'absolute', width: 290, height: 290, alignItems: 'center', justifyContent: 'center' },
  ringSegment: { position: 'absolute', width: 290, height: 290, borderRadius: 145, borderWidth: 1.5, borderColor: 'transparent', borderTopColor: theme.color.brand },
  ringInner: {},
  bottom: { padding: theme.space.xl, alignItems: 'center' },
  status: { color: theme.color.onSurface, fontSize: 18, fontWeight: '700' },
  substatus: { color: theme.color.onSurface2, fontSize: 13, marginTop: 6, textAlign: 'center' },
  foundBox: { alignItems: 'center', marginTop: theme.space.md, paddingHorizontal: 20, paddingVertical: 10, backgroundColor: theme.color.brand3, borderRadius: theme.radius.lg },
  foundLabel: { color: theme.color.brand, fontSize: 11, fontWeight: '700', letterSpacing: 1, textTransform: 'uppercase' },
  foundValue: { color: theme.color.onSurface, fontSize: 30, fontWeight: '800', letterSpacing: -0.5 },
  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 54, paddingHorizontal: 32, borderRadius: theme.radius.pill, marginTop: theme.space.lg, overflow: 'hidden', minWidth: 220 },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
});
