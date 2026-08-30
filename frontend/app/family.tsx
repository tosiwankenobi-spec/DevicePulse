import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Modal, TextInput, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { api } from '@/src/api';
import { theme } from '@/src/theme';
import { useSubscription } from '@/src/lib/revenuecat';

const MAX = 5;

const timeAgo = (iso: string) => {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return 'just now';
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
};

export default function Family() {
  const router = useRouter();
  const [members, setMembers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [deviceType, setDeviceType] = useState<'phone' | 'tablet'>('phone');
  const [saving, setSaving] = useState(false);
  const { isSubscribed } = useSubscription();
  const proUnlocked = isSubscribed || Platform.OS === 'web';
  const [optimizing, setOptimizing] = useState<string | null>(null);

  const scoreColor = (s: number) => s >= 85 ? theme.color.brand : s >= 65 ? theme.color.warning : theme.color.error;

  const optimize = async (id: string) => {
    if (!proUnlocked) { router.push('/paywall'); return; }
    setOptimizing(id);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    try {
      const r = await api.optimizeMember(id);
      setMembers((prev) => prev.map((m) => m.id === id ? { ...m, health_score: r.health_score, last_optimized: r.last_optimized } : m));
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (e) { console.log(e); }
    finally { setOptimizing(null); }
  };

  const load = async () => {
    try { setMembers(await api.family()); } catch (e) { console.log(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const addMember = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const m = await api.addMember({ name: name.trim(), device_type: deviceType });
      setMembers((prev) => [...prev, m]);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setName('');
      setDeviceType('phone');
      setModalOpen(false);
    } catch (e) { console.log(e); }
    finally { setSaving(false); }
  };

  const remove = async (id: string) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setMembers((prev) => prev.filter((m) => m.id !== id));
    try { await api.removeMember(id); } catch (e) { console.log(e); }
  };

  const slots = MAX - members.length - 1; // -1 for owner

  return (
    <View style={styles.container} testID="family-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.topBar}>
          <Pressable onPress={() => router.back()} hitSlop={12} testID="family-back">
            <Ionicons name="chevron-back" size={26} color={theme.color.onSurface} />
          </Pressable>
          <Text style={styles.topTitle}>Family Plan</Text>
          <View style={{ width: 26 }} />
        </View>

        {loading ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
            <ActivityIndicator color={theme.color.brand} />
          </View>
        ) : (
          <ScrollView contentContainerStyle={{ paddingHorizontal: theme.space.lg, paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
            <LinearGradient colors={theme.gradients.brand} style={styles.hero} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
              <Ionicons name="people" size={36} color={theme.color.onBrand} />
              <Text style={styles.heroTitle}>One plan, up to 5 devices</Text>
              <Text style={styles.heroSub}>Share DevicePulse Pro with your family — everyone gets deep cleanup and priority support.</Text>
              <View style={styles.priceRow}>
                <Text style={styles.price}>$39.99</Text>
                <Text style={styles.pricePer}>/ year</Text>
              </View>
            </LinearGradient>

            <Text style={styles.section}>Devices ({members.length + 1}/{MAX})</Text>

            {/* Owner */}
            <View style={styles.memberCard}>
              <View style={styles.memberTop}>
                <View style={[styles.memberIcon, { backgroundColor: theme.color.brand }]}>
                  <Ionicons name="person" size={20} color={theme.color.onBrand} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.memberName}>You (Owner)</Text>
                  <Text style={styles.memberType}>This device</Text>
                </View>
                <View style={styles.ownerBadge}><Text style={styles.ownerBadgeText}>ADMIN</Text></View>
              </View>
            </View>

            {members.map((m) => (
              <View key={m.id} style={styles.memberCard} testID={`member-${m.id}`}>
                <View style={styles.memberTop}>
                  <View style={[styles.memberIcon, { backgroundColor: theme.color.surface3 }]}>
                    <Ionicons name={m.device_type === 'tablet' ? 'tablet-portrait' : 'phone-portrait'} size={20} color={theme.color.brand} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.memberName}>{m.name}</Text>
                    <Text style={styles.memberType}>
                      {m.last_optimized ? `Optimized ${timeAgo(m.last_optimized)}` : `${m.device_type === 'tablet' ? 'Tablet' : 'Phone'} · Not optimized`}
                    </Text>
                  </View>
                  <View style={styles.scoreBadge}>
                    <Text style={[styles.scoreNum, { color: scoreColor(m.health_score ?? 72) }]}>{m.health_score ?? 72}</Text>
                    <Text style={styles.scoreLbl}>health</Text>
                  </View>
                  <Pressable onPress={() => remove(m.id)} hitSlop={10} testID={`remove-${m.id}`} style={{ marginLeft: 10 }}>
                    <Ionicons name="close-circle" size={22} color={theme.color.onSurface3} />
                  </Pressable>
                </View>
                <Pressable
                  style={[styles.optimizeBtn, (m.health_score ?? 72) >= 90 && styles.optimizeBtnDone]}
                  onPress={() => optimize(m.id)}
                  disabled={optimizing === m.id || (m.health_score ?? 72) >= 90}
                  testID={`optimize-${m.id}`}
                >
                  {optimizing === m.id ? (
                    <ActivityIndicator color={theme.color.brand} size="small" />
                  ) : (
                    <>
                      <Ionicons
                        name={(m.health_score ?? 72) >= 90 ? 'checkmark-circle' : proUnlocked ? 'sparkles' : 'lock-closed'}
                        size={15}
                        color={theme.color.brand}
                      />
                      <Text style={styles.optimizeText}>
                        {(m.health_score ?? 72) >= 90 ? 'Optimized' : proUnlocked ? 'Optimize remotely' : 'Optimize (Pro)'}
                      </Text>
                    </>
                  )}
                </Pressable>
              </View>
            ))}

            {/* Empty slots */}
            {slots > 0 && Array.from({ length: slots }).map((_, i) => (
              <Pressable key={i} style={styles.emptySlot} onPress={() => setModalOpen(true)} testID={`empty-slot-${i}`}>
                <Ionicons name="add" size={22} color={theme.color.brand} />
                <Text style={styles.emptySlotText}>Add a device</Text>
              </Pressable>
            ))}

            {slots <= 0 && (
              <Text style={styles.fullNote}>Your family plan is full (5 devices).</Text>
            )}
          </ScrollView>
        )}
      </SafeAreaView>

      {/* Add member modal */}
      <Modal visible={modalOpen} transparent animationType="slide" onRequestClose={() => setModalOpen(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.modalBg}>
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setModalOpen(false)} />
          <View style={styles.sheet}>
            <View style={styles.grabber} />
            <Text style={styles.sheetTitle}>Add a device</Text>
            <Text style={styles.inputLabel}>Name</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Mom's iPhone"
              placeholderTextColor={theme.color.onSurface3}
              value={name}
              onChangeText={setName}
              testID="member-name-input"
              autoFocus
            />
            <Text style={styles.inputLabel}>Device type</Text>
            <View style={styles.typeRow}>
              {(['phone', 'tablet'] as const).map((t) => (
                <Pressable key={t} style={[styles.typeBtn, deviceType === t && styles.typeBtnActive]} onPress={() => setDeviceType(t)} testID={`type-${t}`}>
                  <Ionicons name={t === 'tablet' ? 'tablet-portrait-outline' : 'phone-portrait-outline'} size={18} color={deviceType === t ? theme.color.onBrand : theme.color.onSurface2} />
                  <Text style={[styles.typeText, deviceType === t && styles.typeTextActive]}>{t === 'tablet' ? 'Tablet' : 'Phone'}</Text>
                </Pressable>
              ))}
            </View>
            <Pressable style={[styles.saveBtn, !name.trim() && { opacity: 0.5 }]} disabled={!name.trim() || saving} onPress={addMember} testID="save-member-button">
              <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
              {saving ? <ActivityIndicator color={theme.color.onBrand} /> : <Text style={styles.saveText}>Add device</Text>}
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: theme.space.lg, paddingTop: theme.space.sm, paddingBottom: theme.space.md },
  topTitle: { color: theme.color.onSurface, fontSize: 16, fontWeight: '700' },
  hero: { borderRadius: theme.radius.lg, padding: theme.space.xl, alignItems: 'center' },
  heroTitle: { color: theme.color.onBrand, fontSize: 20, fontWeight: '800', marginTop: 10, textAlign: 'center' },
  heroSub: { color: 'rgba(2,44,34,0.85)', fontSize: 13, textAlign: 'center', marginTop: 6, lineHeight: 18 },
  priceRow: { flexDirection: 'row', alignItems: 'baseline', marginTop: theme.space.md },
  price: { color: theme.color.onBrand, fontSize: 30, fontWeight: '800' },
  pricePer: { color: 'rgba(2,44,34,0.8)', fontSize: 14, fontWeight: '600', marginLeft: 4 },
  section: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '700', letterSpacing: 1.1, textTransform: 'uppercase', marginTop: theme.space.xl, marginBottom: theme.space.md },
  memberCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, padding: theme.space.md, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.sm },
  memberTop: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  memberIcon: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  memberName: { color: theme.color.onSurface, fontSize: 15, fontWeight: '600' },
  memberType: { color: theme.color.onSurface2, fontSize: 12, marginTop: 2 },
  scoreBadge: { alignItems: 'center', minWidth: 44 },
  scoreNum: { fontSize: 20, fontWeight: '800', letterSpacing: -0.5 },
  scoreLbl: { color: theme.color.onSurface3, fontSize: 9, textTransform: 'uppercase', letterSpacing: 0.5 },
  optimizeBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: theme.space.md, height: 40, borderRadius: theme.radius.md, backgroundColor: theme.color.brand3, borderWidth: 1, borderColor: theme.color.border },
  optimizeBtnDone: { opacity: 0.6 },
  optimizeText: { color: theme.color.brand, fontSize: 13, fontWeight: '700' },
  ownerBadge: { backgroundColor: theme.color.brand3, paddingHorizontal: 8, paddingVertical: 3, borderRadius: theme.radius.pill },
  ownerBadgeText: { color: theme.color.brand, fontSize: 10, fontWeight: '800' },
  emptySlot: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: theme.radius.md, borderWidth: 1.5, borderColor: theme.color.border, borderStyle: 'dashed', paddingVertical: theme.space.md, marginBottom: theme.space.sm },
  emptySlotText: { color: theme.color.brand, fontSize: 14, fontWeight: '600' },
  fullNote: { color: theme.color.onSurface3, fontSize: 13, textAlign: 'center', marginTop: theme.space.md },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: theme.color.surface2, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: theme.space.xl, paddingBottom: 36, borderWidth: 1, borderColor: theme.color.border },
  grabber: { width: 40, height: 4, borderRadius: 2, backgroundColor: theme.color.border, alignSelf: 'center', marginBottom: theme.space.lg },
  sheetTitle: { color: theme.color.onSurface, fontSize: 20, fontWeight: '800', marginBottom: theme.space.lg },
  inputLabel: { color: theme.color.onSurface2, fontSize: 13, fontWeight: '600', marginBottom: 8 },
  input: { backgroundColor: theme.color.surface3, borderRadius: theme.radius.md, paddingHorizontal: theme.space.md, height: 50, color: theme.color.onSurface, fontSize: 15, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.lg },
  typeRow: { flexDirection: 'row', gap: 10, marginBottom: theme.space.xl },
  typeBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, height: 48, borderRadius: theme.radius.md, backgroundColor: theme.color.surface3, borderWidth: 1, borderColor: theme.color.border },
  typeBtnActive: { backgroundColor: theme.color.brand, borderColor: theme.color.brand },
  typeText: { color: theme.color.onSurface2, fontSize: 14, fontWeight: '600' },
  typeTextActive: { color: theme.color.onBrand, fontWeight: '700' },
  saveBtn: { height: 54, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  saveText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
});
