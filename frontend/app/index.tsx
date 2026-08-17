import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Animated, { FadeIn, useSharedValue, useAnimatedStyle, withTiming, Easing } from 'react-native-reanimated';
import { VLogo } from '@/src/components/VLogo';
import { theme } from '@/src/theme';

export default function SplashRoute() {
  const router = useRouter();
  const scale = useSharedValue(0.7);
  const opacity = useSharedValue(0);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    scale.value = withTiming(1, { duration: 900, easing: Easing.out(Easing.cubic) });
    opacity.value = withTiming(1, { duration: 800 });
    const t = setTimeout(async () => {
      const done = await AsyncStorage.getItem('dp:onboarded');
      if (done === '1') router.replace('/(tabs)');
      else router.replace('/onboarding');
    }, 1900);
    return () => clearTimeout(t);
  }, []);

  const logoStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
    opacity: opacity.value,
  }));

  return (
    <View style={styles.container} testID="splash-screen">
      <LinearGradient
        colors={theme.gradients.hero2}
        style={StyleSheet.absoluteFill}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
      />
      <Animated.View style={[styles.logo, logoStyle]}>
        <VLogo size={140} />
      </Animated.View>
      <Animated.View entering={FadeIn.delay(400).duration(700)}>
        <Text style={styles.brand}>DevicePulse</Text>
        <Text style={styles.tagline}>by Verolane Digital Solutions</Text>
      </Animated.View>
      <View style={styles.spinner}>
        <ActivityIndicator color={theme.color.brand} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.color.surface },
  logo: { marginBottom: theme.space.xl },
  brand: { color: theme.color.onSurface, fontSize: 32, fontWeight: '800', letterSpacing: -0.5, textAlign: 'center' },
  tagline: { color: theme.color.onSurface2, fontSize: 13, marginTop: 6, textAlign: 'center', letterSpacing: 0.5 },
  spinner: { position: 'absolute', bottom: 80 },
});
