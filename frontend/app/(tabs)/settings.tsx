import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Switch } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { VLogo } from '@/src/components/VLogo';
import { theme } from '@/src/theme';

export default function Settings() {
  const router = useRouter();
  const [autoScan, setAutoScan] = React.useState(true);
  const [notifs, setNotifs] = React.useState(true);
  const [haptics, setHaptics] = React.useState(true);

  return (
    <View style={styles.container} testID="settings-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <View style={styles.header}>
          <Text style={styles.title}>Settings</Text>
        </View>
        <ScrollView contentContainerStyle={{ paddingBottom: 140, paddingHorizontal: theme.space.lg }} showsVerticalScrollIndicator={false}>
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

          <Text style={styles.section}>Preferences</Text>
          <View style={styles.card}>
            <Row icon="scan-outline" label="Auto smart scan" desc="Weekly on Sunday">
              <Switch value={autoScan} onValueChange={setAutoScan} trackColor={{ true: theme.color.brand, false: theme.color.border }} thumbColor="#fff" testID="toggle-auto-scan" />
            </Row>
            <Divider />
            <Row icon="notifications-outline" label="Notifications" desc="Get cleanup reminders">
              <Switch value={notifs} onValueChange={setNotifs} trackColor={{ true: theme.color.brand, false: theme.color.border }} thumbColor="#fff" testID="toggle-notifications" />
            </Row>
            <Divider />
            <Row icon="phone-portrait-outline" label="Haptic feedback" desc="Feel every tap">
              <Switch value={haptics} onValueChange={setHaptics} trackColor={{ true: theme.color.brand, false: theme.color.border }} thumbColor="#fff" testID="toggle-haptics" />
            </Row>
          </View>

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

          <View style={styles.footer}>
            <VLogo size={40} />
            <Text style={styles.footerBrand}>DevicePulse v1.0.0</Text>
            <Text style={styles.footerCorp}>© Verolane Digital Solutions</Text>
          </View>
        </ScrollView>
      </SafeAreaView>
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

const NavRow = ({ icon, label, testID }: any) => (
  <Pressable style={styles.row} testID={testID}>
    <View style={styles.rowIcon}>
      <Ionicons name={icon} size={20} color={theme.color.brand} />
    </View>
    <Text style={[styles.rowLabel, { flex: 1 }]}>{label}</Text>
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
  footer: { alignItems: 'center', marginTop: theme.space.xxl, gap: 6 },
  footerBrand: { color: theme.color.onSurface2, fontSize: 12, fontWeight: '600' },
  footerCorp: { color: theme.color.onSurface3, fontSize: 11 },
});
