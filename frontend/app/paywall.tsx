import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Modal, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { PRO_TOOLS, PRO_ROUTINES } from '@/src/pro-content';
import { Ionicons } from '@expo/vector-icons';
import { useSubscription } from '@/src/lib/revenuecat';
import { theme } from '@/src/theme';

const FEATURES = [...PRO_TOOLS.map(tool => ({ icon: tool.icon, label: tool.title })), ...PRO_ROUTINES.map(routine => ({ icon: 'checkmark-done-outline' as const, label: routine.title }))];

export default function Paywall() {
  const router = useRouter();
  const { offerings, isSubscribed, identityReady, identityError, isLoading, purchase, restore, isPurchasing, isRestoring, verificationError, retryVerification } = useSubscription();
  const packages = (offerings?.current?.availablePackages ?? []).filter(p => p.packageType === 'MONTHLY' || p.packageType === 'ANNUAL');
  const [selected, setSelected] = useState(0);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [errMsg, setErrMsg] = useState('');

  const pkg = packages[selected];

  const trialLabel = (p: any): string | null => {
    const intro = p?.product?.introPrice;
    if (!intro) return null;
    const isFree = intro.price === 0 || intro.priceString === '$0.00';
    if (!isFree) return null;
    const n = intro.periodNumberOfUnits ?? 7;
    const unit = (intro.periodUnit ?? 'DAY').toString().toLowerCase().replace(/s$/, '');
    return `${n}-${unit} free trial`;
  };
  const selectedTrial = trialLabel(pkg);

  const onBuy = async () => {
    if (!pkg || !identityReady) { setErrMsg('Sign in required before purchasing.'); return; }
    setConfirmOpen(false);
    setErrMsg('');
    try {
      await purchase(pkg);
    } catch (e: any) {
      if (e?.userCancelled || String(e).includes('userCancelled')) return;
      setErrMsg(e instanceof Error ? e.message : 'Purchase could not be completed. Please try again.');
    }
  };

  const onRestore = async () => {
    setErrMsg('');
    try { await restore(); } catch (e) { setErrMsg(e instanceof Error ? e.message : 'Restore could not be verified.'); }
  };

  return (
    <View style={styles.container} testID="paywall-screen">
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={styles.hero}>
          <Pressable style={styles.close} onPress={() => router.back()} hitSlop={12} testID="paywall-close">
            <Ionicons name="close" size={22} color={theme.color.onSurface} />
          </Pressable>
          <View style={styles.heroContent}>
            <View style={styles.proBadge}>
              <Ionicons name="sparkles" size={12} color={theme.color.onBrand} />
              <Text style={styles.proBadgeText}>DEVICEPULSE PRO</Text>
            </View>
            <Text style={styles.heroTitle}>DevicePulse Pro</Text>
            <Text style={styles.heroSub}>Personal Coach, guided care routines, cleanup history and shareable reports.</Text>
          </View>
        </View>

        <ScrollView contentContainerStyle={{ paddingBottom: 32 }}>
          <View style={styles.featureList}>
            {FEATURES.map((f, i) => (
              <View key={i} style={styles.featureRow}>
                <View style={styles.featureIcon}>
                  <Ionicons name={f.icon as any} size={18} color={theme.color.brand} />
                </View>
                <Text style={styles.featureText}>{f.label}</Text>
                <Ionicons name="checkmark-circle" size={20} color={theme.color.brand} />
              </View>
            ))}
          </View>

          {isSubscribed ? (
            <View style={styles.activeCard} testID="paywall-active">
              <Ionicons name="checkmark-circle" size={40} color={theme.color.brand} />
              <Text style={styles.activeTitle}>You&apos;re on Pro 🎉</Text>
              <Text style={styles.activeBody}>Your purchase has been verified. Your Pro toolkit is ready.</Text>
              <Pressable onPress={() => router.replace('/pro')}><Text style={styles.restoreText}>Open Pro toolkit →</Text></Pressable>
            </View>
          ) : isLoading ? (
            <View style={{ paddingVertical: 30 }}><ActivityIndicator color={theme.color.brand} /></View>
          ) : packages.length === 0 ? (
            <Text style={styles.unavailable} testID="paywall-unavailable">Subscription options are unavailable right now. Please try again later.</Text>
          ) : (
            <>
              <View style={styles.plans}>
                {packages.map((p, i) => {
                  const t = trialLabel(p);
                  return (
                  <Pressable
                    key={p.identifier}
                    style={[styles.plan, selected === i && styles.planActive]}
                    onPress={() => setSelected(i)}
                    testID={`plan-${p.packageType?.toLowerCase?.() || i}`}
                  >
                    {!!t && (
                      <View style={styles.trialTag}>
                        <Text style={styles.trialTagText}>{t.toUpperCase()}</Text>
                      </View>
                    )}
                    <Text style={styles.planLabel}>{p.packageType === 'ANNUAL' ? 'Yearly' : p.packageType === 'MONTHLY' ? 'Monthly' : p.identifier}</Text>
                    <Text style={styles.planPrice}>{p.product.priceString}</Text>
                    <Text style={styles.planPer}>{p.product.title}</Text>
                  </Pressable>
                  );
                })}
              </View>

              {!identityReady && (
                <Text style={styles.errMsg} testID="paywall-identity-status">
                  {identityError
                    ? 'Subscription sign-in could not be completed. Sign out, sign back in, and try again.'
                    : 'Finishing secure subscription sign-in…'}
                </Text>
              )}

              <Pressable
                style={[styles.cta, isPurchasing && { opacity: 0.5 }]}
                onPress={() => {
                  if (!identityReady) {
                    setErrMsg(identityError
                      ? 'Subscription sign-in failed. Sign out, sign back in, and try again.'
                      : 'Subscription sign-in is still finishing. Please try again in a moment.');
                    return;
                  }
                  setConfirmOpen(true);
                }}
                disabled={isPurchasing || isRestoring}
                testID="paywall-cta"
              >
                <LinearGradient colors={theme.gradients.brand} style={StyleSheet.absoluteFill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} />
                {isPurchasing ? <ActivityIndicator color={theme.color.onBrand} /> : <Text style={styles.ctaText}>{selectedTrial ? `Start ${selectedTrial}` : `Subscribe ${pkg?.product.priceString} / ${pkg?.packageType === 'ANNUAL' ? 'year' : 'month'}`}</Text>}
              </Pressable>

            </>
          )}
          {!!verificationError && <Text style={styles.errMsg}>{verificationError}</Text>}
          {!!errMsg && <Text style={styles.errMsg}>{errMsg}</Text>}
          <Pressable style={styles.restoreBtn} onPress={() => retryVerification().then(state => setErrMsg(state.is_pro ? '' : 'No active Pro purchase verified yet.')).catch(e => setErrMsg(e instanceof Error ? e.message : 'Verification unavailable.'))}><Text style={styles.restoreText}>Retry purchase verification</Text></Pressable>
          <Pressable style={styles.restoreBtn} onPress={onRestore} disabled={isRestoring || isPurchasing || !identityReady} testID="paywall-restore"><Text style={styles.restoreText}>{isRestoring ? 'Restoring…' : 'Restore purchases'}</Text></Pressable>
          <Text style={styles.disclaimer}>Renews automatically at the displayed price per billing period until canceled. Manage or cancel in Google Play. Family members each need Pro. Personal files are never deleted automatically.</Text>
        </ScrollView>
      </SafeAreaView>

      <Modal visible={confirmOpen} transparent animationType="fade" onRequestClose={() => setConfirmOpen(false)}>
        <View style={styles.modalBg}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Confirm subscription</Text>
            <Text style={styles.modalBody}>{selectedTrial
              ? `Start your ${selectedTrial}, then ${pkg?.product.priceString} per ${pkg?.packageType === 'ANNUAL' ? 'year' : 'month'}. Cancel anytime before it ends.`
              : `Subscribe to DevicePulse Pro for ${pkg?.product.priceString} per ${pkg?.packageType === 'ANNUAL' ? 'year' : 'month'}?`}</Text>
            <View style={styles.modalButtons}>
              <Pressable style={[styles.modalBtn, styles.modalGhost]} onPress={() => setConfirmOpen(false)} testID="confirm-cancel">
                <Text style={styles.modalGhostText}>Cancel</Text>
              </Pressable>
              <Pressable style={[styles.modalBtn, styles.modalPrimary]} onPress={onBuy} testID="confirm-subscribe">
                <Text style={styles.modalPrimaryText}>Subscribe</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.color.surface },
  hero: { height: 210, overflow: 'hidden' },
  close: { position: 'absolute', top: 12, right: 16, width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(0,0,0,0.5)', alignItems: 'center', justifyContent: 'center', zIndex: 2 },
  heroContent: { position: 'absolute', bottom: 20, left: 0, right: 0, paddingHorizontal: theme.space.lg },
  proBadge: { flexDirection: 'row', alignSelf: 'flex-start', alignItems: 'center', gap: 4, backgroundColor: theme.color.brand, paddingHorizontal: 10, paddingVertical: 5, borderRadius: theme.radius.pill },
  proBadgeText: { color: theme.color.onBrand, fontSize: 10, fontWeight: '800', letterSpacing: 0.8 },
  heroTitle: { color: theme.color.onSurface, fontSize: 30, fontWeight: '800', marginTop: 12, lineHeight: 34 },
  heroSub: { color: theme.color.onSurface2, fontSize: 14, marginTop: 8, lineHeight: 20 },
  featureList: { paddingHorizontal: theme.space.lg, gap: 12, marginTop: theme.space.md },
  featureRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, backgroundColor: theme.color.surface2, borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.border },
  featureIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: theme.color.brand3, alignItems: 'center', justifyContent: 'center' },
  featureText: { color: theme.color.onSurface, fontSize: 14, fontWeight: '600', flex: 1 },
  plans: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, paddingHorizontal: theme.space.lg, marginTop: theme.space.xl },
  plan: { flexGrow: 1, flexBasis: 150, padding: theme.space.md, borderRadius: theme.radius.lg, borderWidth: 2, borderColor: theme.color.border, backgroundColor: theme.color.surface2 },
  planActive: { borderColor: theme.color.brand, backgroundColor: theme.color.brand3 },
  planLabel: { color: theme.color.onSurface, fontSize: 13, fontWeight: '700' },
  planPrice: { color: theme.color.onSurface, fontSize: 24, fontWeight: '800', marginTop: 4, letterSpacing: -0.5 },
  planPer: { color: theme.color.onSurface2, fontSize: 11, marginTop: 2 },
  saveTag: { position: 'absolute', top: -10, right: 10, backgroundColor: theme.color.brand, paddingHorizontal: 8, paddingVertical: 3, borderRadius: theme.radius.pill },
  saveTagText: { color: theme.color.onBrand, fontSize: 9, fontWeight: '800' },
  cta: { marginHorizontal: theme.space.lg, marginTop: theme.space.xl, height: 56, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  ctaText: { color: theme.color.onBrand, fontSize: 16, fontWeight: '700' },
  disclaimer: { color: theme.color.onSurface3, fontSize: 11, textAlign: 'center', marginTop: 12, paddingHorizontal: theme.space.xl, lineHeight: 15 },
  activeCard: { alignItems: 'center', backgroundColor: theme.color.brand3, borderRadius: theme.radius.lg, padding: theme.space.xl, marginHorizontal: theme.space.lg, marginTop: theme.space.md, gap: 8 },
  activeTitle: { color: theme.color.onSurface, fontSize: 20, fontWeight: '800' },
  activeBody: { color: theme.color.onSurface2, fontSize: 14, textAlign: 'center', lineHeight: 20 },
  unavailable: { color: theme.color.onSurface2, fontSize: 14, textAlign: 'center', marginTop: theme.space.lg, paddingHorizontal: theme.space.xl, lineHeight: 20 },
  errMsg: { color: theme.color.error, fontSize: 13, textAlign: 'center', marginTop: 10, paddingHorizontal: theme.space.xl },
  restoreBtn: { alignItems: 'center', paddingVertical: 14 },
  trialTag: { position: 'absolute', top: -10, alignSelf: 'center', backgroundColor: theme.color.brand, paddingHorizontal: 8, paddingVertical: 3, borderRadius: theme.radius.pill },
  trialTagText: { color: theme.color.onBrand, fontSize: 9, fontWeight: '800' },
  restoreText: { color: theme.color.brand, fontSize: 14, fontWeight: '700' },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.75)', alignItems: 'center', justifyContent: 'center', padding: theme.space.xl },
  modalCard: { backgroundColor: theme.color.surface2, borderRadius: theme.radius.lg, padding: theme.space.xl, borderWidth: 1, borderColor: theme.color.border, width: '100%' },
  modalTitle: { color: theme.color.onSurface, fontSize: 20, fontWeight: '800' },
  modalBody: { color: theme.color.onSurface2, fontSize: 14, marginTop: 8, lineHeight: 20 },
  modalButtons: { flexDirection: 'row', gap: 10, marginTop: theme.space.lg },
  modalBtn: { flex: 1, height: 48, borderRadius: theme.radius.pill, alignItems: 'center', justifyContent: 'center' },
  modalGhost: { backgroundColor: theme.color.surface3, borderWidth: 1, borderColor: theme.color.border },
  modalGhostText: { color: theme.color.onSurface, fontWeight: '600' },
  modalPrimary: { backgroundColor: theme.color.brand },
  modalPrimaryText: { color: theme.color.onBrand, fontWeight: '700' },
});
