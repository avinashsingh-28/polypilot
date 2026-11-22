import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { LoginPage } from './LoginPage';

export interface AuthUser {
  id: string;
  email: string;
}

interface AuthState {
  user: AuthUser | null;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState>({ user: null, logout: async () => undefined });
export const useAuth = () => useContext(Ctx);

/** Renders the app only for an authenticated session; otherwise the sign-in page.
 *  Session is an HttpOnly cookie — nothing auth-related is stored in localStorage. */
export const AuthGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [expired, setExpired] = useState(false);
  // A password-reset link opens the app with ?reset_token=…; read it once, then strip it from the
  // address bar so the secret does not stay in history or leak via the Referer header.
  // Google sign-in errors come back as ?auth_error=<code>; read once and strip as well.
  const [{ resetToken: initialReset, authError }] = useState(() => {
    const q = new URLSearchParams(window.location.search);
    const r = { resetToken: q.get('reset_token'), authError: q.get('auth_error') };
    if (r.resetToken || r.authError) window.history.replaceState(null, '', window.location.pathname);
    return r;
  });
  const [resetToken, setResetToken] = useState<string | null>(initialReset);

  const check = useCallback(async () => {
    try {
      setUser(await apiClient<AuthUser>('/auth/me'));
    } catch {
      setUser(null);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => { void check(); }, [check]);
  useEffect(() => {
    const onUnauthorized = () => { setUser((u) => { if (u) setExpired(true); return null; }); };
    window.addEventListener('pp:unauthorized', onUnauthorized);
    return () => window.removeEventListener('pp:unauthorized', onUnauthorized);
  }, []);

  const logout = useCallback(async () => {
    try { await apiClient('/auth/logout', { method: 'POST' }); } finally { setUser(null); setExpired(false); }
  }, []);

  if (checking && !resetToken) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }} role="status">Checking session…</div>;
  }
  if (!user || resetToken) {
    return <LoginPage expired={expired} resetToken={resetToken} authError={authError}
      onResetDone={() => { setResetToken(null); setUser(null); }}   // all sessions were revoked by the reset
      onSignedIn={(u) => { setUser(u); setExpired(false); }} />;
  }
  return <Ctx.Provider value={{ user, logout }}>{children}</Ctx.Provider>;
};
