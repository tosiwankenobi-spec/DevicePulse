import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/src/theme';

type Tool = {
  key: string;
  title: string;
  desc: string;
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
  route: any;
  section: string;
};

const TOOLS: Tool[] = [
  { key: 'duplicates', title: 'Duplicate Photos', desc: 'Find & remove copies safely', icon: 'copy-outline', color: theme.color.brand, route: '/duplicates', section: 'Storage' },
  { key: 'large', title: 'Large Files', desc: 'Videos, archives, downloads', icon: 'folder-open-outline', color: theme.color.info, route: '/large-files', section: 'Storage' },
  { key: 'cache', title: 'App Cache', desc: 'Clear temp files by app', icon: 'trash-outline', color: theme.color.warning, route: '/junk', section: 'Storage' },
  { key: 'battery', title: 'Battery Boost', desc: 'Stop high-drain apps', icon: 'battery-charging-outline', color: '#F59E0B', route: '/(tabs)/insights', section: 'Performance' },
  { key: 'memory', title: 'Memory Cleanup', desc: 'Free up RAM instantly', icon: 'hardware-chip-outline', color: '#8B5CF6', route: '/smart-scan', section: 'Performance' },
  { key: 'security', title: 'Security Scan', desc: 'Malware & permissions', icon: 'shield-checkmark-outline', color: theme.color.brand, route: '/(tabs)/insights', section: 'Protection' },
];

export default function ScanHub() {
  const router = useRouter();
  const sections = Array.from(new Set(TOOLS.map(t => t.section)));

  return (
    <View style={styles.container} testID="scan-hub-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Optimize</Text>
          <Text style={styles.headerSub}>Choose a targeted cleanup</Text>
        </View>

        <ScrollView contentContainerStyle={{ paddingBottom: 140 }} showsVerticalScrollIndicator={false}>
          {/* Featured card */}
          <Pressable style={styles.featured} onPress={() => router.push('/smart-scan')} testID="featured-smart-scan">
            <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} />
            <View style={styles.featuredContent}>
              <View style={{ flex: 1 }}>
                <View style={styles.featuredTag}>
                  <Ionicons name="flash" size={10} color={theme.color.onBrand} />
                  <Text style={styles.featuredTagText}>Recommended</Text>
                </View>
                <Text style={styles.featuredTitle}>One-Tap Smart Scan</Text>
                <Text style={styles.featuredBody}>Analyze junk, duplicates, cache and large files in one sweep.</Text>
              </View>
              <View style={styles.featuredIcon}>
                <Ionicons name="sparkles" size={40} color={theme.color.onBrand} />
              </View>
            </View>
          </Pressable>

          {sections.map((sec) => (
            <View key={sec}>
              <Text style={styles.sectionTitle}>{sec}</Text>
              {TOOLS.filter(t => t.section === sec).map((t) => (
                <Pressable key={t.key} style={styles.toolRow} onPress={() => router.push(t.route)} testID={`tool-${t.key}`}>
                  <View style={[styles.toolIcon, { backgroundColor: t.color + '22' }]}>
                    <Ionicons name={t.icon} size={22} color={t.color} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.toolTitle}>{t.title}</Text>
                    <Text style={styles.toolDesc}>{t.desc}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color={theme.color.onSurface3} />
                </Pressable>
              ))}
            </View>
          ))}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  header: { paddingHorizontal: theme.space.lg, paddingTop: theme.space.md, paddingBottom: theme.space.md },
  headerTitle: { color: theme.color.onSurface, fontSize: 28, fontWeight: '800', letterSpacing: -0.5 },
  headerSub: { color: theme.color.onSurface2, fontSize: 13, marginTop: 2 },
  featured: { marginHorizontal: theme.space.lg, borderRadius: theme.radius.lg, overflow: 'hidden', marginBottom: theme.space.lg },
  featuredContent: { flexDirection: 'row', alignItems: 'center', padding: theme.space.lg },
  featuredTag: { flexDirection: 'row', alignSelf: 'flex-start', alignItems: 'center', gap: 4, backgroundColor: 'rgba(2,44,34,0.35)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: theme.radius.pill },
  featuredTagText: { color: theme.color.onBrand, fontSize: 10, fontWeight: '700' },
  featuredTitle: { color: theme.color.onBrand, fontSize: 20, fontWeight: '800', marginTop: 8, letterSpacing: -0.3 },
  featuredBody: { color: 'rgba(2,44,34,0.85)', fontSize: 13, marginTop: 4, lineHeight: 18 },
  featuredIcon: { width: 68, height: 68, borderRadius: 34, backgroundColor: 'rgba(2,44,34,0.15)', alignItems: 'center', justifyContent: 'center' },
  sectionTitle: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '700', letterSpacing: 1.1, textTransform: 'uppercase', paddingHorizontal: theme.space.lg, marginTop: theme.space.md, marginBottom: theme.space.sm },
  toolRow: { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: theme.color.surface2, marginHorizontal: theme.space.lg, marginBottom: theme.space.sm, padding: theme.space.md, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.border },
  toolIcon: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  toolTitle: { color: theme.color.onSurface, fontSize: 15, fontWeight: '600' },
  toolDesc: { color: theme.color.onSurface2, fontSize: 12, marginTop: 2 },
});
