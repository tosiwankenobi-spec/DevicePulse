import { Stack, useRouter } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useEffect, useState } from "react";
import { LogBox, StatusBar, Platform, View, Text, StyleSheet, Pressable, Modal } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import * as Notifications from "expo-notifications";
import * as Linking from "expo-linking";
import AsyncStorage from "@react-native-async-storage/async-storage";

import { useIconFonts } from "@/src/hooks/use-icon-fonts";
import { AuthProvider } from "@/src/AuthContext";


LogBox.ignoreAllLogs(true)

SplashScreen.preventAutoHideAsync();

// 1. Foreground handler — MODULE SCOPE (guard web)
if (Platform.OS !== "web") {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
      shouldShowBanner: true,
      shouldShowList: true,
    }),
  });
}

// 2. Android channel — MODULE SCOPE
if (Platform.OS === "android") {
  Notifications.setNotificationChannelAsync("default", {
    name: "Default",
    importance: Notifications.AndroidImportance.MAX,
    sound: "default",
  });
}

export default function RootLayout() {
  const [loaded, error] = useIconFonts();
  const router = useRouter();
  const [nudgeOpen, setNudgeOpen] = useState(false);

  useEffect(() => {
    if (loaded || error) {
      SplashScreen.hideAsync();
    }
  }, [loaded, error]);

  useEffect(() => {
    if (Platform.OS === "web") return;

    const route = (data: any) => {
      const url = data?.deeplink || data?.action_url;
      if (!url) return;
      url.startsWith("http") ? Linking.openURL(url) : router.push(url);
    };

    // 3. Warm tap
    const tapSub = Notifications.addNotificationResponseReceivedListener((response) => {
      route(response.notification.request.content.data || {});
    });

    // 4. Cold-start tap
    Notifications.getLastNotificationResponseAsync().then((response) => {
      if (response) route(response.notification.request.content.data || {});
    });

    // Denied-permission weekly nudge
    (async () => {
      try {
        const { status, canAskAgain } = await Notifications.getPermissionsAsync();
        if (status !== "denied" || canAskAgain) return;
        const lastNudge = await AsyncStorage.getItem("pushNudgeAt");
        const oneWeek = 7 * 24 * 60 * 60 * 1000;
        if (lastNudge && Date.now() - Number(lastNudge) <= oneWeek) return;
        setNudgeOpen(true);
      } catch {}
    })();

    return () => { tapSub.remove(); };
  }, []);

  const closeNudge = async (openSettings: boolean) => {
    await AsyncStorage.setItem("pushNudgeAt", String(Date.now()));
    setNudgeOpen(false);
    if (openSettings) Linking.openSettings();
  };

  if (!loaded && !error) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: '#050F14' }}>
      <StatusBar barStyle="light-content" backgroundColor="#050F14" />
      <AuthProvider>
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#050F14' }, animation: 'fade' }} />
      </AuthProvider>

      <Modal visible={nudgeOpen} transparent animationType="fade" onRequestClose={() => closeNudge(false)}>
        <View style={styles.nudgeBg}>
          <View style={styles.nudgeCard}>
            <Text style={styles.nudgeTitle}>Turn on notifications</Text>
            <Text style={styles.nudgeBody}>Enable notifications to get cleanup reminders and keep your streak alive.</Text>
            <View style={styles.nudgeButtons}>
              <Pressable style={[styles.nudgeBtn, styles.nudgeGhost]} onPress={() => closeNudge(false)} testID="push-nudge-later">
                <Text style={styles.nudgeGhostText}>Later</Text>
              </Pressable>
              <Pressable style={[styles.nudgeBtn, styles.nudgePrimary]} onPress={() => closeNudge(true)} testID="push-nudge-settings">
                <Text style={styles.nudgePrimaryText}>Open Settings</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  nudgeBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.75)', alignItems: 'center', justifyContent: 'center', padding: 24 },
  nudgeCard: { backgroundColor: '#0B1B24', borderRadius: 20, padding: 24, borderWidth: 1, borderColor: '#163342', width: '100%' },
  nudgeTitle: { color: '#F0FDFA', fontSize: 20, fontWeight: '800' },
  nudgeBody: { color: '#A3C2C2', fontSize: 14, marginTop: 8, lineHeight: 20 },
  nudgeButtons: { flexDirection: 'row', gap: 10, marginTop: 20 },
  nudgeBtn: { flex: 1, height: 48, borderRadius: 999, alignItems: 'center', justifyContent: 'center' },
  nudgeGhost: { backgroundColor: '#122936', borderWidth: 1, borderColor: '#163342' },
  nudgeGhostText: { color: '#F0FDFA', fontWeight: '600' },
  nudgePrimary: { backgroundColor: '#10B981' },
  nudgePrimaryText: { color: '#022C22', fontWeight: '700' },
});
