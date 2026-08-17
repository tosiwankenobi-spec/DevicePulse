import React, { useRef, useState } from 'react';
import { View, Text, StyleSheet, Pressable, useWindowDimensions, FlatList } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { theme } from '@/src/theme';

const SLIDES = [
  {
    icon: 'pulse' as const,
    title: 'Understand your device',
    body: 'Get a clear health score across storage, memory, battery and security in seconds.',
    color: theme.color.brand,
  },
  {
    icon: 'sparkles' as const,
    title: 'One-tap Smart Scan',
    body: 'Find duplicate photos, junk files and large media—review everything before we clean.',
    color: theme.color.info,
  },
  {
    icon: 'shield-checkmark' as const,
    title: 'Privacy-first optimization',
    body: 'On iOS we stay App Store compliant. On Android we go deeper—always with your consent.',
    color: '#8B5CF6',
  },
];

export default function Onboarding() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const [index, setIndex] = useState(0);
  const listRef = useRef<FlatList>(null);

  const onNext = async () => {
    if (index < SLIDES.length - 1) {
      const next = index + 1;
      setIndex(next);
      listRef.current?.scrollToOffset({ offset: next * width, animated: true });
    } else {
      await AsyncStorage.setItem('dp:onboarded', '1');
      router.replace('/(tabs)');
    }
  };

  const onSkip = async () => {
    await AsyncStorage.setItem('dp:onboarded', '1');
    router.replace('/(tabs)');
  };

  const onMomentumEnd = (e: any) => {
    const idx = Math.round(e.nativeEvent.contentOffset.x / width);
    if (idx !== index) setIndex(idx);
  };

  return (
    <View style={styles.container} testID="onboarding-screen">
      <LinearGradient colors={theme.gradients.hero2} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={onSkip} testID="onboarding-skip-button" hitSlop={10}>
            <Text style={styles.skip}>Skip</Text>
          </Pressable>
        </View>

        <FlatList
          ref={listRef}
          data={SLIDES}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          onMomentumScrollEnd={onMomentumEnd}
          keyExtractor={(_, i) => String(i)}
          renderItem={({ item }) => (
            <View style={[styles.slide, { width }]}>
              <View style={[styles.iconWrap, { borderColor: item.color }]}>
                <Ionicons name={item.icon} size={68} color={item.color} />
              </View>
              <Text style={styles.title}>{item.title}</Text>
              <Text style={styles.body}>{item.body}</Text>
            </View>
          )}
        />

        <View style={styles.dots}>
          {SLIDES.map((_, i) => (
            <View key={i} style={[styles.dot, i === index && styles.dotActive]} />
          ))}
        </View>

        <View style={styles.bottom}>
          <Pressable style={styles.cta} onPress={onNext} testID="onboarding-next-button">
            <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
            <Text style={styles.ctaText}>{index < SLIDES.length - 1 ? 'Continue' : 'Get Started'}</Text>
            <Ionicons name="arrow-forward" size={20} color={theme.color.onBrand} />
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { alignItems: 'flex-end', paddingHorizontal: theme.space.xl, paddingTop: theme.space.md },
  skip: { color: theme.color.onSurface2, fontSize: 15, fontWeight: '600' },
  slide: { alignItems: 'center', justifyContent: 'center', paddingHorizontal: theme.space.xl },
  iconWrap: {
    width: 140, height: 140, borderRadius: 70, alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, marginBottom: theme.space.xxl, backgroundColor: 'rgba(16,185,129,0.08)',
  },
  title: { color: theme.color.onSurface, fontSize: 26, fontWeight: '800', textAlign: 'center', letterSpacing: -0.5 },
  body: { color: theme.color.onSurface2, fontSize: 15, textAlign: 'center', marginTop: theme.space.md, lineHeight: 22, maxWidth: 320 },
  dots: { flexDirection: 'row', alignSelf: 'center', gap: 6, marginBottom: theme.space.xl },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: theme.color.border },
  dotActive: { width: 22, backgroundColor: theme.color.brand },
  bottom: { paddingHorizontal: theme.space.xl, paddingBottom: theme.space.lg },
  cta: {
    height: 56, borderRadius: theme.radius.pill, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 10, overflow: 'hidden',
  },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
});
