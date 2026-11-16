import React, { useState } from 'react';
import { LogIn, UserPlus } from 'lucide-react';
import { apiClient } from '../api/client';
import type { AuthUser } from './AuthContext';

interface Props {
  expired: boolean;
  onSignedIn: (u: AuthUser) => void;
}

export const LoginPage: React.FC<Props> = ({ expired, onSignedIn }) => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(expired ? 'Your session expired. Please sign in again.' : null);

  const pwProblem = mode === 'register'
    ? (password.length < 10 ? 'At least 10 characters' : password !== confirm ? 'Passwords do not match' : null)
    : null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null); setInfo(null);
    try {
      if (mode === 'register') {
        const r = await apiClient<{ message: string }>('/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) });
        setInfo(r.message); setMode('login'); setConfirm('');
      } else {
        const r = await apiClient<{ user: AuthUser }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
        setPassword('');
        onSignedIn(r.user);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16, backgroundColor: 'var(--bg-app)' }}>
      <form onSubmit={submit} className="card" style={{ width: '100%', maxWidth: 400, padding: 28, display: 'flex', flexDirection: 'column', gap: 14 }} aria-labelledby="auth-title">
        <div>
          <h1 id="auth-title" style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>PolyPilot</h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{mode === 'login' ? 'Sign in to your workspace' : 'Create an account'}</p>
        </div>
        {info && <div role="status" style={{ fontSize: 13, padding: '8px 10px', borderRadius: 6, background: 'var(--info-bg)', color: 'var(--info-text)' }}>{info}</div>}
        {error && <div role="alert" style={{ fontSize: 13, padding: '8px 10px', borderRadius: 6, background: 'var(--danger-bg)', color: 'var(--danger-text)' }}>{error}</div>}
        <div className="form-group">
          <label className="form-label" htmlFor="email">Email</label>
          <input id="email" className="form-input" type="email" autoComplete="email" required maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="password">Password</label>
          <input id="password" className="form-input" type="password" required minLength={mode === 'register' ? 10 : 1} maxLength={128}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {mode === 'register' && (
          <div className="form-group">
            <label className="form-label" htmlFor="confirm">Confirm password</label>
            <input id="confirm" className="form-input" type="password" required autoComplete="new-password" maxLength={128} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            <span className="form-hint">{pwProblem ?? 'Looks good'}</span>
          </div>
        )}
        <button className="btn btn-primary" type="submit" disabled={busy || !email || !password || !!pwProblem}>
          {mode === 'login' ? <><LogIn size={14} /> {busy ? 'Signing in…' : 'Sign in'}</> : <><UserPlus size={14} /> {busy ? 'Creating…' : 'Create account'}</>}
        </button>
        <button type="button" className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null); }}>
          {mode === 'login' ? 'No account? Register' : 'Have an account? Sign in'}
        </button>
      </form>
    </main>
  );
};
