import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import { AppState, Platform } from "react-native";
import Purchases, { LOG_LEVEL } from "react-native-purchases";
import type { PurchasesPackage } from "react-native-purchases";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth } from "../AuthContext";

export const REVENUECAT_ENTITLEMENT_IDENTIFIER = "pro";
function platformApiKey() {
  if (Platform.OS === "android") return process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY;
  if (Platform.OS === "ios") return process.env.EXPO_PUBLIC_REVENUECAT_IOS_API_KEY;
  return undefined; // A browser or Test Store must never grant paid Android access.
}
export const rcEnabled = Boolean(platformApiKey());
export function initializeRevenueCat() {
  const key = platformApiKey();
  if (!key) return;
  Purchases.setLogLevel(__DEV__ ? LOG_LEVEL.DEBUG : LOG_LEVEL.WARN);
  Purchases.configure({ apiKey: key });
}

function useSubscriptionContext() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const userId = user?.user_id;
  const [readyId, setReadyId] = useState<string | null>(null);
  const [identityError, setIdentityError] = useState(false);
  const identityQueue = useRef(Promise.resolve());
  const identityReady = Boolean(userId && readyId === userId);
  const entitlementKey = ["pro-verified", userId];

  useEffect(() => {
    let cancelled = false;
    setReadyId(null);
    setIdentityError(false);
    queryClient.removeQueries({ queryKey: ["pro-verified"] });
    if (!rcEnabled) return;
    // Serialize account switches so a late login cannot overwrite a newer identity.
    identityQueue.current = identityQueue.current.catch(() => {}).then(async () => {
      if (cancelled) return;
      try {
        if (userId) {
          await Purchases.logIn(userId);
          if (!cancelled && await Purchases.getAppUserID() === userId) setReadyId(userId);
        } else if (!(await Purchases.isAnonymous())) {
          await Purchases.logOut();
        }
      } catch {
        if (!cancelled) setIdentityError(true);
      }
    });
    return () => { cancelled = true; };
  }, [userId, queryClient]);

  const entitlementQuery = useQuery({
    queryKey: entitlementKey,
    queryFn: () => api.syncEntitlement(),
    enabled: identityReady,
    retry: false,
    staleTime: 0,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });
  const offeringsQuery = useQuery({
    queryKey: ["revenuecat", "offerings"],
    queryFn: () => Purchases.getOfferings(),
    enabled: rcEnabled,
    staleTime: 300_000,
  });
  useEffect(() => {
    const refresh = () => { void queryClient.invalidateQueries({ queryKey: ["pro-verified"] }); };
    const subscription = AppState.addEventListener("change", state => { if (state === "active") refresh(); });
    if (rcEnabled) Purchases.addCustomerInfoUpdateListener(refresh);
    return () => {
      subscription.remove();
      if (rcEnabled) Purchases.removeCustomerInfoUpdateListener(refresh);
    };
  }, [queryClient]);

  async function verify() {
    const state = await api.syncEntitlement();
    queryClient.setQueryData(entitlementKey, state);
    return state;
  }
  async function checkIdentity() {
    if (!identityReady || !userId || await Purchases.getAppUserID() !== userId) {
      throw new Error("Finish signing into your account before purchasing or restoring.");
    }
  }
  const purchaseMutation = useMutation({
    mutationFn: async (pkg: PurchasesPackage) => {
      await checkIdentity();
      await Purchases.purchasePackage(pkg);
      try {
        const state = await verify();
        if (!state.is_pro) throw new Error("pending");
        return state;
      } catch {
        throw new Error("Purchase received; Pro verification is pending. Retry verification—do not buy again.");
      }
    },
  });
  const restoreMutation = useMutation({
    mutationFn: async () => {
      await checkIdentity();
      await Purchases.restorePurchases();
      const state = await verify();
      if (!state.is_pro) throw new Error("No active Pro subscription was verified for this account.");
      return state;
    },
  });
  const expiry = entitlementQuery.data?.expires_at;
  const isSubscribed = identityReady && !entitlementQuery.isError &&
    entitlementQuery.data?.is_pro === true && Boolean(expiry && Date.parse(expiry) > Date.now());
  return {
    offerings: offeringsQuery.data, isSubscribed, identityReady, identityError, rcEnabled,
    isLoading: offeringsQuery.isLoading || (identityReady && entitlementQuery.isPending),
    verificationError: entitlementQuery.error instanceof Error ? entitlementQuery.error.message : null,
    retryVerification: verify,
    purchase: purchaseMutation.mutateAsync, restore: restoreMutation.mutateAsync,
    isPurchasing: purchaseMutation.isPending, isRestoring: restoreMutation.isPending,
  };
}
type SubscriptionContextValue = ReturnType<typeof useSubscriptionContext>;
const Context = createContext<SubscriptionContextValue | null>(null);
export function SubscriptionProvider({ children }: { children: React.ReactNode }) {
  const value = useSubscriptionContext();
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useSubscription() {
  const ctx = useContext(Context);
  if (!ctx) throw new Error("useSubscription must be used within a SubscriptionProvider");
  return ctx;
}
