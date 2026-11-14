import AsyncStorage from '@react-native-async-storage/async-storage';

let cached: string | null = null;

function genId() {
  return 'dev-' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

export async function getDeviceId(): Promise<string> {
  if (cached) return cached;
  let id = await AsyncStorage.getItem('dp:deviceId');
  if (!id) {
    id = genId();
    await AsyncStorage.setItem('dp:deviceId', id);
  }
  cached = id;
  return id;
}
