import React, { useState } from 'react';
import { ArrowLeft, CheckCircle2, Eye, EyeOff, KeyRound, LogIn, Mail, ShieldCheck, Sparkles, UploadCloud, UserPlus } from 'lucide-react';
import { apiClient } from '../api/client';
import { Logo } from '../components/common/Logo';
import type { AuthUser } from './AuthContext';
import './auth.css';

type Mode = 'login' | 'register' | 'forgot' | 'reset';

interface Props {
  expired: boolean;
  resetToken?: string | null;
  onSignedIn: (u: AuthUser) => void;
  onResetDone?: () => void;
}

const TITLES: Record<Mode, [string, string]> = {
  login: ['Welcome back', 'Sign in to your PolyPilot workspace'],
  register: ['Create your account', 'Start preparing verified problems'],
  forgot: ['Forgot your password?', "Enter your email and we'll send you a reset link"],
  reset: ['Choose a new password', 'Use at least 10 characters'],
};

export const LoginPage: React.FC<Props> = ({ expired, resetToken, onSignedIn, onResetDone }) => {
  const [mode, setMode] = useState<Mode>(resetToken ? 'reset' : 'login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(expired ? 'Your session expired. Please sign in again.' : null);

  const needsNewPassword = mode === 'register' || mode === 'reset';
  const pwProblem = needsNewPassword
    ? (password.length < 10 ? 'At least 10 characters' : password !== confirm ? 'Passwords do not match' : null)
    : null;
  const canSubmit = !busy && (mode === 'reset' ? !pwProblem : !!email && (mode === 'forgot' || (!!password && !pwProblem)));

  const go = (m: Mode) => { setMode(m); setError(null); setPassword(''); setConfirm(''); };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null); setInfo(null);
    const post = <T,>(path: string, body: unknown) => apiClient<T>(path, { method: 'POST', body: JSON.stringify(body) });
    try {
      if (mode === 'login') {
        const r = await post<{ user: AuthUser }>('/auth/login', { email, password });
        setPassword('');
        onSignedIn(r.user);
      } else if (mode === 'register') {
        const r = await post<{ message: string }>('/auth/register', { email, password });
        go('login'); setInfo(r.message);
      } else if (mode === 'forgot') {
        const r = await post<{ message: string }>('/auth/forgot-password', { email });
        setInfo(r.message);
      } else {
        const r = await post<{ message: string }>('/auth/reset-password', { token: resetToken, password });
        onResetDone?.();
        go('login'); setInfo(r.message);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const [title, subtitle] = TITLES[mode];
  const submitLabel = { login: 'Sign in', register: 'Create account', forgot: 'Send reset link', reset: 'Set new password' }[mode];
  const SubmitIcon = { login: LogIn, register: UserPlus, forgot: Mail, reset: KeyRound }[mode];

  return (
    <main className="auth-shell">
      <section className="auth-brand" aria-hidden="true">
        <div className="auth-brand-inner">
          <div className="auth-brand-logo"><Logo size={30} /></div>
          <h2>From problem idea to a verified Polygon package.</h2>
          <p>Draft with AI, prove it in a sandbox, publish through the official API.</p>
          <ul>
            <li><Sparkles size={18} /><span><strong>AI drafting</strong> — statement, solutions, validator, generator, editorial</span></li>
            <li><ShieldCheck size={18} /><span><strong>Real verification</strong> — isolated execution, differential & stress testing</span></li>
            <li><UploadCloud size={18} /><span><strong>Polygon sync</strong> — dry run, upload, commit and build with your approval</span></li>
          </ul>
        </div>
      </section>

      <section className="auth-panel">
        <form onSubmit={submit} className="auth-card fade-up" aria-labelledby="auth-title" key={mode}>
          <div className="auth-mobile-logo"><Logo size={26} /></div>
          {(mode === 'forgot' || mode === 'reset') && (
            <button type="button" className="auth-back" onClick={() => go('login')}><ArrowLeft size={14} /> Back to sign in</button>
          )}
          <div>
            <h1 id="auth-title">{title}</h1>
            <p className="auth-sub">{subtitle}</p>
          </div>

          {info && <div role="status" className="auth-alert auth-alert-info"><CheckCircle2 size={16} /><span>{info}</span></div>}
          {error && <div role="alert" className="auth-alert auth-alert-error"><span>{error}</span></div>}

          {mode !== 'reset' && (
            <div className="form-group">
              <label className="form-label" htmlFor="email">Email</label>
              <input id="email" className="form-input" type="email" autoComplete="email" required maxLength={254}
                placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
            </div>
          )}

          {mode !== 'forgot' && (
            <div className="form-group">
              <div className="auth-label-row">
                <label className="form-label" htmlFor="password">{mode === 'reset' ? 'New password' : 'Password'}</label>
                {mode === 'login' && <button type="button" className="auth-link" onClick={() => go('forgot')}>Forgot password?</button>}
              </div>
              <div className="auth-password">
                <input id="password" className="form-input" type={show ? 'text' : 'password'} required maxLength={128}
                  minLength={needsNewPassword ? 10 : 1} autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  value={password} onChange={(e) => setPassword(e.target.value)} autoFocus={mode === 'reset'} />
                <button type="button" className="auth-eye" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'}>
                  {show ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
          )}

          {needsNewPassword && (
            <div className="form-group">
              <label className="form-label" htmlFor="confirm">Confirm password</label>
              <input id="confirm" className="form-input" type={show ? 'text' : 'password'} required maxLength={128}
                autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
              <span className={`form-hint ${pwProblem ? '' : 'auth-ok'}`}>{password || confirm ? (pwProblem ?? 'Looks good') : 'At least 10 characters, not a common password'}</span>
            </div>
          )}

          <button className="btn btn-primary auth-submit" type="submit" disabled={!canSubmit}>
            <SubmitIcon size={15} /> {busy ? 'Please wait…' : submitLabel}
          </button>

          {mode === 'login' && <p className="auth-switch">New to PolyPilot? <button type="button" className="auth-link" onClick={() => go('register')}>Create an account</button></p>}
          {mode === 'register' && <p className="auth-switch">Already have an account? <button type="button" className="auth-link" onClick={() => go('login')}>Sign in</button></p>}
          {mode === 'forgot' && <p className="auth-switch">The link expires after 30 minutes and can be used once.</p>}
        </form>
      </section>
    </main>
  );
};
