import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { Platform } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';
import { api, setUnauthorizedHandler } from './api';
import { saveToken, getToken, clearToken } from './authStorage';
import { registerForPush } from './push';
import { rcEnabled } from './lib/revenuecat';

WebBrowser.maybeCompleteAuthSession();

type User = { user_id: string; email: string; name: string; picture?: string } | null;

interface AuthCtx {
  user: User;
  loading: boolean;
  justLoggedIn: boolean;
  clearJustLoggedIn: () => void;
  login: () => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx>({ user: null, loading: true, justLoggedIn: false, clearJustLoggedIn: () => {}, login: async () => {}, logout: async () => {} });
export const useAuth = () => useContext(Ctx);

function extractSessionId(url?: string | null): string | null {
  if (!url) return null;
  const m = url.match(/[?#&]session_id=([^&#]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User>(null);
  const [loading, setLoading] = useState(true);
  const [justLoggedIn, setJustLoggedIn] = useState(false);
  const processed = useRef<Set<string>>(new Set());
  const rcIdentityRef = useRef<string | null>(null);

  const exchange = useCallback(async (sessionId: string) => {
    if (processed.current.has(sessionId)) return;
    processed.current.add(sessionId);
    try {
      const res = await api.createSession(sessionId);
      await saveToken(res.session_token);
      setUser(res.user);
      setJustLoggedIn(true);
    } catch (e) {
      console.log('session exchange failed', e);
    }
  }, []);

  const checkExisting = useCallback(async () => {
    const token = await getToken();
    if (!token) { setUser(null); return; }
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      await clearToken();
      setUser(null);
    }
  }, []);

  const logout = useCallback(async () => {
    try { await api.logout(); } catch {}
    await clearToken();
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(async () => {
      await clearToken();
      setUser(null);
    });
  }, []);

  // Register this device for push whenever a user is signed in (native only)
  useEffect(() => {
    if (user?.user_id) registerForPush(user.user_id);
  }, [user?.user_id]);

  // Bind RevenueCat identity to the authenticated user (COMPULSORY on every auth path)
  useEffect(() => {
    if (!rcEnabled) return;
    (async () => {
      try {
        const Purchases = require('react-native-purchases').default;
        if (user?.user_id && rcIdentityRef.current !== user.user_id) {
          await Purchases.logIn(user.user_id);
          rcIdentityRef.current = user.user_id;
        } else if (!user?.user_id && rcIdentityRef.current) {
          await Purchases.logOut();
          rcIdentityRef.current = null;
        }
      } catch (e) {
        console.log('RevenueCat identity error', e);
      }
    })();
  }, [user?.user_id]);

  // Initial bootstrap
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        if (Platform.OS === 'web') {
          const sid = extractSessionId(window.location.hash) || extractSessionId(window.location.search);
          if (sid) {
            await exchange(sid);
            // clean session_id from URL after success
            try {
              const url = new URL(window.location.href);
              url.hash = '';
              url.searchParams.delete('session_id');
              window.history.replaceState(window.history.state, '', url.toString());
            } catch {}
          } else {
            await checkExisting();
          }
        } else {
          const initial = await Linking.getInitialURL();
          const sid = extractSessionId(initial);
          if (sid) await exchange(sid);
          else await checkExisting();
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [exchange, checkExisting]);

  // Mobile hot deep links
  useEffect(() => {
    if (Platform.OS === 'web') return;
    const sub = Linking.addEventListener('url', ({ url }) => {
      const sid = extractSessionId(url);
      if (sid) exchange(sid);
    });
    return () => sub.remove();
  }, [exchange]);

  const login = useCallback(async () => {
    const redirectUrl = Platform.OS === 'web'
      ? window.location.origin + '/'
      : Linking.createURL('');
    const authUrl = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;

    if (Platform.OS === 'web') {
      window.location.href = authUrl;
      return;
    }
    const result = await WebBrowser.openAuthSessionAsync(authUrl, redirectUrl);
    let sid: string | null = null;
    if (result.type === 'success' && result.url) sid = extractSessionId(result.url);
    if (!sid) {
      const initial = await Linking.getInitialURL();
      sid = extractSessionId(initial);
    }
    if (sid) await exchange(sid);
  }, [exchange]);

  return <Ctx.Provider value={{ user, loading, justLoggedIn, clearJustLoggedIn: () => setJustLoggedIn(false), login, logout }}>{children}</Ctx.Provider>;
};
