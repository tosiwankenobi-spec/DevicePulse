import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { api } from '@/src/api';
import { theme } from '@/src/theme';

export default function Duplicates() {
  const router = useRouter();
  const [groups, setGroups] = useState<any[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.duplicates().then((d) => {
      setGroups(d);
      const s: Record<string, boolean> = {};
      d.forEach((g: any) => (s[g.id] = true));
      setSelected(s);
    }).finally(() => setLoading(false));
  }, []);

  const totalMb = groups.filter(g => selected[g.id]).reduce((a, g) => a + g.size_mb, 0);
  const toggle = (id: string) => { Haptics.selectionAsync(); setSelected(s => ({ ...s, [id]: !s[id] })); };

  return (
    <View style={styles.container} testID="duplicates-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="dup-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Duplicate Photos</Text>
          <View style={{ width: 26 }} />
        </View>

        {loading ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : (
          <>
            <View style={styles.summary}>
              <Text style={styles.summaryValue}>{totalMb.toFixed(0)} MB</Text>
              <Text style={styles.summaryLabel}>selected across {groups.filter(g => selected[g.id]).length} groups</Text>
            </View>
            <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 100 }}>
              {groups.map((g) => (
                <Pressable key={g.id} style={[styles.card, selected[g.id] && styles.cardActive]} onPress={() => toggle(g.id)} testID={`dup-group-${g.id}`}>
                  <Image source={g.thumbnail_url} style={styles.thumb} contentFit="cover" />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.groupTitle}>{g.count} copies</Text>
                    <Text style={styles.groupSize}>{g.size_mb.toFixed(1)} MB · {g.taken_at}</Text>
                    <Text style={styles.groupKeep}>Keeping best 1, removing {g.count - 1}</Text>
                  </View>
                  <View style={[styles.checkbox, selected[g.id] && styles.checkboxActive]}>
                    {selected[g.id] && <Ionicons name="checkmark" size={14} color={theme.color.onBrand} />}
                  </View>
                </Pressable>
              ))}
            </ScrollView>
            <View style={styles.bottomBar}>
              <Pressable style={styles.cta} onPress={() => router.back()} testID="dup-remove-button">
                <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
                <Text style={styles.ctaText}>Remove {totalMb.toFixed(0)} MB</Text>
              </Pressable>
            </View>
          </>
        )}
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  summary: { paddingHorizontal: theme.space.lg, paddingBottom: theme.space.md },
  summaryValue: { color: theme.color.brand, fontSize: 32, fontWeight: '800', letterSpacing: -1 },
  summaryLabel: { color: theme.color.onSurface2, fontSize: 13 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: theme.color.surface2, padding: 12, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.sm },
  cardActive: { borderColor: theme.color.brand },
  thumb: { width: 64, height: 64, borderRadius: 10, backgroundColor: theme.color.surface3 },
  groupTitle: { color: theme.color.onSurface, fontSize: 15, fontWeight: '700' },
  groupSize: { color: theme.color.onSurface2, fontSize: 12, marginTop: 2 },
  groupKeep: { color: theme.color.brand, fontSize: 11, marginTop: 4 },
  checkbox: { width: 22, height: 22, borderRadius: 6, borderWidth: 1.5, borderColor: theme.color.border, alignItems: 'center', justifyContent: 'center' },
  checkboxActive: { backgroundColor: theme.color.brand, borderColor: theme.color.brand },
  bottomBar: { padding: theme.space.lg, paddingBottom: 32, borderTopWidth: 1, borderTopColor: theme.color.border, backgroundColor: theme.color.surface },
  cta: { height: 52, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
});
