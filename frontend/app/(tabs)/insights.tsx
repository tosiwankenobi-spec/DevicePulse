import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Battery from 'expo-battery';
import { openApplicationSettings, openBatterySettings, openDeviceStorageManager, openSecuritySettings, scanLocalDevice, type LocalDeviceScan } from '@/src/deviceStorage';
import { theme } from '@/src/theme';

type Tab = 'storage' | 'battery' | 'memory' | 'security';

type BatterySnapshot = {
  level: number;
  state: Battery.BatteryState;
  lowPowerMode: boolean;
  appOptimizationEnabled: boolean;
};

function formatMb(mb: number): string {
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(1)} MB`;
}

function batteryStateLabel(state: Battery.BatteryState): string {
  if (state === Battery.BatteryState.CHARGING) return 'Charging';
  if (state === Battery.BatteryState.FULL) return 'Full';
  if (state === Battery.BatteryState.UNPLUGGED) return 'On battery';
  return 'Status unavailable';
}

export default function Insights() {
  const [tab, setTab] = useState<Tab>('storage');
  const [storage, setStorage] = useState<LocalDeviceScan | null>(null);
  const [battery, setBattery] = useState<BatterySnapshot | null>(null);

  const load = async () => {
    setStorage(scanLocalDevice());
    try {
      const power = await Battery.getPowerStateAsync();
      const appOptimizationEnabled = await Battery.isBatteryOptimizationEnabledAsync();
      setBattery({
        level: power.batteryLevel,
        state: power.batteryState,
        lowPowerMode: power.lowPowerMode,
        appOptimizationEnabled,
      });
    } catch {
      setBattery(null);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <View style={styles.container} testID="insights-screen">
      <LinearGradient colors={['#050F14', '#0B1B24']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <View style={styles.header}>
          <Text style={styles.title}>Device Insights</Text>
          <Text style={styles.sub}>Real readings and Android-approved controls</Text>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
          {(['storage', 'battery', 'memory', 'security'] as Tab[]).map((item) => (
            <Pressable key={item} onPress={() => setTab(item)} style={[styles.chip, tab === item && styles.chipActive]} testID={`insight-tab-${item}`}>
              <Text style={[styles.chipText, tab === item && styles.chipTextActive]}>{item[0].toUpperCase() + item.slice(1)}</Text>
            </Pressable>
          ))}
        </ScrollView>

        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {!storage ? <Loader /> : (
            <>
              {tab === 'storage' && <StorageView data={storage} />}
              {tab === 'battery' && <BatteryView data={battery} />}
              {tab === 'memory' && <MemoryView />}
              {tab === 'security' && <SecurityView />}
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const Loader = () => <View style={styles.loader}><ActivityIndicator color={theme.color.brand} /></View>;

function StorageView({ data }: { data: LocalDeviceScan }) {
  const usedPct = data.storage_total_mb > 0 ? Math.round((data.storage_used_mb / data.storage_total_mb) * 100) : 0;
  return (
    <View>
      <View style={styles.card}>
        <Text style={styles.cardLabel}>App-accessible storage used</Text>
        <Text style={styles.cardValue}>{usedPct}%</Text>
        <View style={styles.progressTrack}><View style={[styles.progressFill, { width: `${usedPct}%` }]} /></View>
        <Text style={styles.helperText}>{formatMb(data.storage_free_mb)} available to apps of {formatMb(data.storage_total_mb)}. Android may show a larger physical total that includes reserved system capacity.</Text>
      </View>
      <View style={styles.card}>
        <Text style={styles.cardLabel}>DevicePulse temporary cache</Text>
        <Text style={styles.miniValue}>{formatMb(data.cache_mb)}</Text>
        <Text style={styles.helperText}>Measured locally. DevicePulse does not inspect personal files without Android approval.</Text>
      </View>
      <ActionButton icon="folder-open-outline" label="Open Android Storage" onPress={openDeviceStorageManager} />
    </View>
  );
}

function BatteryView({ data }: { data: BatterySnapshot | null }) {
  if (!data || data.level < 0) {
    return <InfoCard icon="battery-half-outline" title="Battery reading unavailable" body="Open Android Battery settings for current usage details." action="Open Battery Settings" onPress={openBatterySettings} />;
  }
  const pct = Math.round(data.level * 100);
  return (
    <View>
      <View style={styles.card}>
        <Text style={styles.cardLabel}>Battery level</Text>
        <Text style={styles.cardValue}>{pct}%</Text>
        <View style={styles.progressTrack}><View style={[styles.progressFill, { width: `${pct}%`, backgroundColor: theme.color.warning }]} /></View>
        <Text style={styles.helperText}>{batteryStateLabel(data.state)} • Power saver {data.lowPowerMode ? 'on' : 'off'}</Text>
      </View>
      <View style={styles.card}>
        <Text style={styles.cardLabel}>DevicePulse background optimization</Text>
        <Text style={styles.miniValue}>{data.appOptimizationEnabled ? 'Enabled' : 'Not enabled'}</Text>
        <Text style={styles.helperText}>Android controls background limits. DevicePulse never claims to stop other apps.</Text>
      </View>
      <ActionButton icon="battery-charging-outline" label="Open Battery Settings" onPress={openBatterySettings} />
    </View>
  );
}

function MemoryView() {
  return <InfoCard icon="hardware-chip-outline" title="Android manages memory" body="Apps cannot safely close other apps or promise to free system RAM. Use Android's app controls if one app is unresponsive or consuming too many resources." action="Open DevicePulse App Settings" onPress={openApplicationSettings} />;
}

function SecurityView() {
  return <InfoCard icon="shield-checkmark-outline" title="Use Android's protected security checks" body="DevicePulse cannot certify that a phone is malware-free. Android Security settings and Google Play Protect can review installed apps, updates and permissions with system-level access." action="Open Security Settings" onPress={openSecuritySettings} />;
}

function InfoCard({ icon, title, body, action, onPress }: { icon: keyof typeof Ionicons.glyphMap; title: string; body: string; action: string; onPress: () => void | Promise<void> }) {
  return (
    <View style={styles.infoCard}>
      <View style={styles.infoIcon}><Ionicons name={icon} size={34} color={theme.color.brand} /></View>
      <Text style={styles.infoTitle}>{title}</Text>
      <Text style={styles.infoBody}>{body}</Text>
      <ActionButton icon="open-outline" label={action} onPress={onPress} />
    </View>
  );
}

function ActionButton({ icon, label, onPress }: { icon: keyof typeof Ionicons.glyphMap; label: string; onPress: () => void | Promise<void> }) {
  return (
    <Pressable style={styles.actionButton} onPress={onPress}>
      <Ionicons name={icon} size={18} color={theme.color.onBrand} />
      <Text style={styles.actionButtonText}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  header: { paddingHorizontal: theme.space.lg, paddingTop: theme.space.md, paddingBottom: theme.space.md },
  title: { color: theme.color.onSurface, fontSize: 28, fontWeight: '800', letterSpacing: -0.5 },
  sub: { color: theme.color.onSurface2, fontSize: 13, marginTop: 2 },
  chipRow: { paddingHorizontal: theme.space.lg, gap: 8, paddingBottom: theme.space.md },
  chip: { paddingHorizontal: 16, paddingVertical: 9, borderRadius: theme.radius.pill, backgroundColor: theme.color.surface2, borderWidth: 1, borderColor: theme.color.border },
  chipActive: { backgroundColor: theme.color.brand3, borderColor: theme.color.brand },
  chipText: { color: theme.color.onSurface2, fontSize: 13, fontWeight: '600' },
  chipTextActive: { color: theme.color.brand },
  content: { paddingHorizontal: theme.space.lg, paddingBottom: 140 },
  loader: { paddingVertical: 60, alignItems: 'center' },
  card: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.lg, borderWidth: 1, borderColor: theme.color.border, marginBottom: theme.space.md },
  cardLabel: { color: theme.color.onSurface2, fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, fontWeight: '700' },
  cardValue: { color: theme.color.onSurface, fontSize: 40, fontWeight: '800', marginTop: 6 },
  miniValue: { color: theme.color.onSurface, fontSize: 23, fontWeight: '800', marginTop: 8 },
  helperText: { color: theme.color.onSurface2, fontSize: 13, lineHeight: 19, marginTop: 8 },
  progressTrack: { height: 9, borderRadius: 5, backgroundColor: theme.color.surface3, overflow: 'hidden', marginTop: 12 },
  progressFill: { height: '100%', backgroundColor: theme.color.brand, borderRadius: 5 },
  actionButton: { minHeight: 50, borderRadius: theme.radius.pill, backgroundColor: theme.color.brand, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingHorizontal: 22, marginTop: theme.space.sm },
  actionButtonText: { color: theme.color.onBrand, fontSize: 15, fontWeight: '700' },
  infoCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.xl, borderWidth: 1, borderColor: theme.color.border, alignItems: 'center' },
  infoIcon: { width: 72, height: 72, borderRadius: 36, backgroundColor: theme.color.brand3, alignItems: 'center', justifyContent: 'center', marginBottom: theme.space.md },
  infoTitle: { color: theme.color.onSurface, fontSize: 20, fontWeight: '800', textAlign: 'center' },
  infoBody: { color: theme.color.onSurface2, fontSize: 14, lineHeight: 21, textAlign: 'center', marginTop: 8, marginBottom: theme.space.md },
});
