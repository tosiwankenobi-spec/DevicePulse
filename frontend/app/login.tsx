import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { VLogo } from '@/src/components/VLogo';
import { useAuth } from '@/src/AuthContext';
import { theme } from '@/src/theme';

const PERKS = [
  { icon: 'sync', text: 'Sync your streak, history & trends across devices' },
  { icon: 'people', text: 'Manage your family plan devices' },
  { icon: 'lock-closed', text: 'Your data stays private to your account' },
] as const;

export default function Login() {
  const router = useRouter();
  const { user, login, loading } = useAuth();
  const [signingIn, setSigningIn] = useState(false);

  useEffect(() => {
    if (user) router.replace('/(tabs)');
  }, [user]);

  const onLogin = async () => {
    setSigningIn(true);
    try { await login(); } catch (e) { console.log(e); }
    finally { setSigningIn(false); }
  };

  return (
    <View style={styles.container} testID="login-screen">
      <LinearGradient colors={theme.gradients.hero2} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.top}>
          <VLogo size={96} />
          <Text style={styles.brand}>DevicePulse</Text>
          <Text style={styles.tagline}>Sign in to keep your device optimized</Text>
        </View>

        <View style={styles.perks}>
          {PERKS.map((p, i) => (
            <Animated.View key={i} entering={FadeInDown.delay(i * 90)} style={styles.perkRow}>
              <View style={styles.perkIcon}>
                <Ionicons name={p.icon as any} size={18} color={theme.color.brand} />
              </View>
              <Text style={styles.perkText}>{p.text}</Text>
            </Animated.View>
          ))}
        </View>

        <View style={styles.bottom}>
          <Pressable style={styles.googleBtn} onPress={onLogin} disabled={signingIn || loading} testID="google-login-button">
            {signingIn ? (
              <ActivityIndicator color={theme.color.onSurface} />
            ) : (
              <>
                <Ionicons name="logo-google" size={20} color="#EA4335" />
                <Text style={styles.googleText}>Continue with Google</Text>
              </>
            )}
          </Pressable>
          <Text style={styles.legal}>By continuing you agree to our Terms & Privacy Policy.</Text>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  top: { alignItems: 'center', marginTop: theme.space.xxxl, gap: 6 },
  brand: { color: theme.color.onSurface, fontSize: 30, fontWeight: '800', letterSpacing: -0.5, marginTop: theme.space.md },
  tagline: { color: theme.color.onSurface2, fontSize: 14, textAlign: 'center' },
  perks: { flex: 1, justifyContent: 'center', paddingHorizontal: theme.space.xl, gap: theme.space.md },
  perkRow: { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, padding: theme.space.md, borderWidth: 1, borderColor: theme.color.border },
  perkIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: theme.color.brand3, alignItems: 'center', justifyContent: 'center' },
  perkText: { color: theme.color.onSurface, fontSize: 14, flex: 1, lineHeight: 19 },
  bottom: { paddingHorizontal: theme.space.xl, paddingBottom: theme.space.lg, gap: theme.space.md },
  googleBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, height: 56, borderRadius: theme.radius.pill, backgroundColor: '#FFFFFF' },
  googleText: { color: '#1F1F1F', fontSize: 16, fontWeight: '700' },
  legal: { color: theme.color.onSurface3, fontSize: 11, textAlign: 'center', lineHeight: 15 },
});
