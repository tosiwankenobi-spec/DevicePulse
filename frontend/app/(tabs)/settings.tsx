import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Switch, Modal, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { VLogo } from '@/src/components/VLogo';
import { useAuth } from '@/src/AuthContext';
import { api } from '@/src/api';
import { theme } from '@/src/theme';

export default function Settings() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const [autoScan, setAutoScan] = React.useState(true);
  const [haptics, setHaptics] = React.useState(true);
  const [deleteOpen, setDeleteOpen] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [pushMsg, setPushMsg] = React.useState('');

  const onLogout = async () => {
    await logout();
    router.replace('/login');
  };

  const onDeleteAccount = async () => {
    setDeleting(true);
    try {
      await api.deleteAccount();
    } catch (e) { console.log(e); }
    await logout();
    router.replace('/login');
  };

  const onTestPush = async () => {
    try {
      const res = await api.testPush();
      setPushMsg(res?.sent ? 'Test notification sent!' : 'Push delivers on a real device after publishing a build.');
    } catch (e) {
      setPushMsg('Push delivers on a real device after publishing a build.');
    }
    setTimeout(() => setPushMsg(''), 4000);
  };

  return (
    <View style={styles.container} testID="settings-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <View style={styles.header}>
          <Text style={styles.title}>Settings</Text>
        </View>
        <ScrollView contentContainerStyle={{ paddingBottom: 140, paddingHorizontal: theme.space.lg }} showsVerticalScrollIndicator={false}>
          {/* Profile */}
          {user && (
            <View style={styles.profileCard} testID="settings-profile">
              <View style={styles.avatar}>
                {user.picture ? (
                  <Image source={user.picture} style={styles.avatarImg} contentFit="cover" />
                ) : (
                  <Text style={styles.avatarInitial}>{(user.name || user.email || '?')[0].toUpperCase()}</Text>
                )}
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.profileName} numberOfLines={1}>{user.name}</Text>
                <Text style={styles.profileEmail} numberOfLines={1}>{user.email}</Text>
              </View>
            </View>
          )}
          {/* Pro banner */}
          <Pressable onPress={() => router.push('/paywall')} testID="settings-pro-banner">
            <LinearGradient colors={theme.gradients.brand} style={styles.proBanner} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
              <View style={{ flex: 1 }}>
                <View style={styles.proTag}>
                  <Ionicons name="sparkles" size={11} color={theme.color.onBrand} />
                  <Text style={styles.proTagText}>DEVICEPULSE PRO</Text>
                </View>
                <Text style={styles.proTitle}>Unlock deep cleanup</Text>
                <Text style={styles.proBody}>Auto-scan, scheduled cleanups, priority support.</Text>
              </View>
              <Ionicons name="arrow-forward-circle" size={36} color={theme.color.onBrand} />
            </LinearGradient>
          </Pressable>

          <Pressable style={styles.familyRow} onPress={() => router.push('/family')} testID="settings-family">
            <View style={styles.rowIcon}>
              <Ionicons name="people-outline" size={20} color={theme.color.brand} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowLabel}>Family plan</Text>
              <Text style={styles.rowDesc}>Cover up to 5 devices</Text>
            </View>
            <View style={styles.navBadge}><Text style={styles.navBadgeText}>Best value</Text></View>
            <Ionicons name="chevron-forward" size={18} color={theme.color.onSurface3} />
          </Pressable>

          <Text style={styles.section}>Your Progress</Text>
          <View style={styles.card}>
            <NavRow icon="flame-outline" label="Cleanup streak" onPress={() => router.push('/streak')} testID="settings-streak" />
            <Divider />
            <NavRow icon="pulse-outline" label="Health trends" onPress={() => router.push('/trends')} testID="settings-trends" />
            <Divider />
            <NavRow icon="time-outline" label="Scan history" onPress={() => router.push('/history')} testID="settings-history" />
            <Divider />
            <NavRow icon="trending-up-outline" label="Storage forecast" onPress={() => router.push('/forecast')} testID="settings-forecast" />
            <Divider />
            <NavRow icon="gift-outline" label="Refer a friend" badge="Free Pro" onPress={() => router.push('/referral')} testID="settings-referral" />
            <Divider />
            <NavRow icon="grid-outline" label="Home screen widget" onPress={() => router.push('/widget-preview')} testID="settings-widget" />
            <Divider />
            <NavRow icon="share-social-outline" label="Cleanup report" onPress={() => router.push('/cleanup-report')} testID="settings-cleanup-report" />
          </View>

          <Text style={styles.section}>Preferences</Text>
          <View style={styles.card}>
            <Row icon="scan-outline" label="Auto smart scan" desc="Weekly on Sunday">
              <Switch value={autoScan} onValueChange={setAutoScan} trackColor={{ true: theme.color.brand, false: theme.color.border }} thumbColor="#fff" testID="toggle-auto-scan" />
            </Row>
            <Divider />
            <NavRow icon="notifications-outline" label="Smart reminders" onPress={() => router.push('/reminders')} testID="settings-reminders" />
            <Divider />
            <NavRow icon="paper-plane-outline" label="Send test notification" onPress={onTestPush} testID="settings-test-push" />
            <Divider />
            <Row icon="phone-portrait-outline" label="Haptic feedback" desc="Feel every tap">
              <Switch value={haptics} onValueChange={setHaptics} trackColor={{ true: theme.color.brand, false: theme.color.border }} thumbColor="#fff" testID="toggle-haptics" />
            </Row>
          </View>
          {!!pushMsg && <Text style={styles.pushMsg} testID="push-msg">{pushMsg}</Text>}

          <Text style={styles.section}>Support</Text>
          <View style={styles.card}>
            <NavRow icon="help-circle-outline" label="Help center" testID="settings-help" />
            <Divider />
            <NavRow icon="mail-outline" label="Contact support" testID="settings-contact" />
            <Divider />
            <NavRow icon="star-outline" label="Rate DevicePulse" testID="settings-rate" />
          </View>

          <Text style={styles.section}>About</Text>
          <View style={styles.card}>
            <NavRow icon="document-text-outline" label="Privacy policy" testID="settings-privacy" />
            <Divider />
            <NavRow icon="shield-checkmark-outline" label="Terms of service" testID="settings-terms" />
          </View>

          <Text style={styles.section}>Account</Text>
          <View style={styles.card}>
            <NavRow icon="phone-portrait-outline" label="Active devices" onPress={() => router.push('/sessions')} testID="settings-sessions" />
            <Divider />
            <NavRow icon="trash-outline" label="Delete account" onPress={() => setDeleteOpen(true)} testID="settings-delete-account" />
          </View>

          <Pressable style={styles.logoutBtn} onPress={onLogout} testID="logout-button">
            <Ionicons name="log-out-outline" size={20} color={theme.color.error} />
            <Text style={styles.logoutText}>Sign out</Text>
          </Pressable>

          <View style={styles.footer}>
            <VLogo size={40} />
            <Text style={styles.footerBrand}>DevicePulse v1.0.0</Text>
            <Text style={styles.footerCorp}>© Verolane Digital Solutions</Text>
          </View>
        </ScrollView>
      </SafeAreaView>

      <Modal visible={deleteOpen} transparent animationType="fade" onRequestClose={() => setDeleteOpen(false)}>
        <View style={styles.modalBg}>
          <View style={styles.modalCard}>
            <View style={styles.modalIcon}>
              <Ionicons name="warning" size={30} color={theme.color.error} />
            </View>
            <Text style={styles.modalTitle}>Delete account?</Text>
            <Text style={styles.modalBody}>This permanently erases your account and all data — history, streaks, referrals, reminders and family devices. This can&apos;t be undone.</Text>
            <View style={styles.modalButtons}>
              <Pressable style={[styles.modalBtn, styles.modalBtnGhost]} onPress={() => setDeleteOpen(false)} testID="delete-cancel">
                <Text style={styles.modalBtnGhostText}>Cancel</Text>
              </Pressable>
              <Pressable style={[styles.modalBtn, styles.modalBtnDanger]} onPress={onDeleteAccount} disabled={deleting} testID="delete-confirm">
                {deleting ? <ActivityIndicator color="#fff" /> : <Text style={styles.modalBtnDangerText}>Delete</Text>}
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const Row = ({ icon, label, desc, children }: any) => (
  <View style={styles.row}>
    <View style={styles.rowIcon}>
      <Ionicons name={icon} size={20} color={theme.color.brand} />
    </View>
    <View style={{ flex: 1 }}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowDesc}>{desc}</Text>
    </View>
    {children}
  </View>
);

const NavRow = ({ icon, label, testID, onPress, badge }: any) => (
  <Pressable style={styles.row} testID={testID} onPress={onPress}>
    <View style={styles.rowIcon}>
      <Ionicons name={icon} size={20} color={theme.color.brand} />
    </View>
    <Text style={[styles.rowLabel, { flex: 1 }]}>{label}</Text>
    {badge && (
      <View style={styles.navBadge}>
        <Text style={styles.navBadgeText}>{badge}</Text>
      </View>
    )}
    <Ionicons name="chevron-forward" size={18} color={theme.color.onSurface3} />
  </Pressable>
);

const Divider = () => <View style={{ height: 1, backgroundColor: theme.color.border, marginLeft: 46 }} />;

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  header: { paddingHorizontal: theme.space.lg, paddingTop: theme.space.md, paddingBottom: theme.space.md },
  title: { color: theme.color.onSurface, fontSize: 28, fontWeight: '800', letterSpacing: -0.5 },
  proBanner: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: theme.space.lg, borderRadius: theme.radius.lg, marginBottom: theme.space.md },
  proTag: { flexDirection: 'row', alignSelf: 'flex-start', alignItems: 'center', gap: 4, backgroundColor: 'rgba(2,44,34,0.35)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: theme.radius.pill },
  proTagText: { color: theme.color.onBrand, fontSize: 10, fontWeight: '800', letterSpacing: 0.6 },
  proTitle: { color: theme.color.onBrand, fontSize: 18, fontWeight: '800', marginTop: 6 },
  proBody: { color: 'rgba(2,44,34,0.8)', fontSize: 12, marginTop: 2 },
  section: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '700', letterSpacing: 1.1, textTransform: 'uppercase', marginTop: theme.space.md, marginBottom: theme.space.sm },
  card: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, borderWidth: 1, borderColor: theme.color.border, overflow: 'hidden' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: theme.space.md, paddingVertical: theme.space.md },
  rowIcon: { width: 34, height: 34, borderRadius: 10, backgroundColor: theme.color.brand3, alignItems: 'center', justifyContent: 'center' },
  rowLabel: { color: theme.color.onSurface, fontSize: 15, fontWeight: '600' },
  rowDesc: { color: theme.color.onSurface3, fontSize: 12, marginTop: 2 },
  navBadge: { backgroundColor: theme.color.brand3, paddingHorizontal: 8, paddingVertical: 3, borderRadius: theme.radius.pill, marginRight: 6 },
  navBadgeText: { color: theme.color.brand, fontSize: 10, fontWeight: '700' },
  familyRow: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, borderWidth: 1, borderColor: theme.color.border, padding: theme.space.md, marginBottom: theme.space.md },
  footer: { alignItems: 'center', marginTop: theme.space.xxl, gap: 6 },
  profileCard: { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.md, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.md },
  avatar: { width: 52, height: 52, borderRadius: 26, backgroundColor: theme.color.brand3, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  avatarImg: { width: 52, height: 52 },
  avatarInitial: { color: theme.color.brand, fontSize: 22, fontWeight: '800' },
  profileName: { color: theme.color.onSurface, fontSize: 17, fontWeight: '700' },
  profileEmail: { color: theme.color.onSurface2, fontSize: 13, marginTop: 2 },
  logoutBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 52, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.error + '55', backgroundColor: theme.color.surface2, marginTop: theme.space.lg },
  logoutText: { color: theme.color.error, fontSize: 15, fontWeight: '700' },
  pushMsg: { color: theme.color.brand, fontSize: 13, marginTop: 8, textAlign: 'center' },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.75)', alignItems: 'center', justifyContent: 'center', padding: theme.space.xl },
  modalCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.xl, borderWidth: 1, borderColor: theme.color.border, alignItems: 'center', width: '100%' },
  modalIcon: { width: 58, height: 58, borderRadius: 29, backgroundColor: theme.color.error + '22', alignItems: 'center', justifyContent: 'center', marginBottom: theme.space.md },
  modalTitle: { color: theme.color.onSurface, fontSize: 20, fontWeight: '800' },
  modalBody: { color: theme.color.onSurface2, fontSize: 14, textAlign: 'center', marginTop: 8, lineHeight: 20 },
  modalButtons: { flexDirection: 'row', gap: 10, marginTop: theme.space.lg, width: '100%' },
  modalBtn: { flex: 1, height: 48, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center' },
  modalBtnGhost: { backgroundColor: theme.color.surface3, borderWidth: 1, borderColor: theme.color.border },
  modalBtnGhostText: { color: theme.color.onSurface, fontWeight: '600' },
  modalBtnDanger: { backgroundColor: theme.color.error },
  modalBtnDangerText: { color: '#fff', fontWeight: '700' },
  footerBrand: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '600' },
  footerCorp: { color: theme.color.onSurface3, fontSize: 11 },
});
