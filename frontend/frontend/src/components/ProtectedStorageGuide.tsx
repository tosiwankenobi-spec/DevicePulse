import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { openDeviceStorageManager } from '@/src/deviceStorage';
import { theme } from '@/src/theme';

type Props = {
  title: string;
  icon: keyof typeof Ionicons.glyphMap;
  description: string;
  guidance: string;
};

export function ProtectedStorageGuide({ title, icon, description, guidance }: Props) {
  const router = useRouter();
  return (
    <View style={styles.container}>
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12}>
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>{title}</Text>
          <View style={{ width: 26 }} />
        </View>
        <View style={styles.content}>
          <View style={styles.icon}><Ionicons name={icon} size={42} color={theme.color.brand} /></View>
          <Text style={styles.title}>{description}</Text>
          <Text style={styles.body}>{guidance}</Text>
          <View style={styles.notice}>
            <Ionicons name="shield-checkmark" size={20} color={theme.color.brand} />
            <Text style={styles.noticeText}>Android keeps personal files protected. You review and approve every deletion in the system interface.</Text>
          </View>
          <Pressable style={styles.button} onPress={openDeviceStorageManager}>
            <Ionicons name="open-outline" size={18} color={theme.color.onBrand} />
            <Text style={styles.buttonText}>Open Android Storage</Text>
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
  content: { flex: 1, justifyContent: 'center', padding: theme.space.xl },
  icon: { width: 88, height: 88, borderRadius: 44, backgroundColor: theme.color.brand3, alignItems: 'center', justifyContent: 'center', alignSelf: 'center' },
  title: { color: theme.color.onSurface, fontSize: 23, fontWeight: '800', textAlign: 'center', marginTop: theme.space.lg },
  body: { color: theme.color.onSurface2, fontSize: 14, lineHeight: 21, textAlign: 'center', marginTop: theme.space.sm },
  notice: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: theme.color.brand3, borderRadius: theme.radius.md, padding: theme.space.md, marginTop: theme.space.xl },
  noticeText: { color: theme.color.onSurface, fontSize: 12, lineHeight: 17, flex: 1 },
  button: { minHeight: 54, borderRadius: theme.radius.pill, backgroundColor: theme.color.brand, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: theme.space.lg },
  buttonText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
});
