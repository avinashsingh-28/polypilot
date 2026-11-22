import React, { useEffect, useState } from 'react';
import { ArrowLeft, CheckCircle2, Eye, EyeOff, KeyRound, LogIn, Mail, ShieldCheck, Sparkles, UploadCloud, UserPlus } from 'lucide-react';
import { apiClient, BASE_URL } from '../api/client';
import { Logo } from '../components/common/Logo';
import type { AuthUser } from './AuthContext';
import './auth.css';

type Mode = 'login' | 'register' | 'forgot' | 'reset';

interface Props {
  expired: boolean;
  resetToken?: string | null;
  authError?: string | null;
  onSignedIn: (u: AuthUser) => void;
  onResetDone?: () => void;
}

const GOOGLE_ERRORS: Record<string, string> = {
  google_denied: 'Google sign-in was cancelled.',
  google_state: 'Google sign-in timed out or was started in another tab. Please try again.',
  google_failed: 'Google sign-in failed. Please try again.',
  google_unverified: 'Your Google account email address is not verified.',
  google_conflict: 'This email is already linked to a different Google account.',
  registration_closed: 'Registration is closed on this instance.',
  account_disabled: 'This account is disabled.',
};

const GoogleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
    <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/>
    <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
    <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/>
    <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/>
  </svg>
);

const TITLES: Record<Mode, [string, string]> = {
  login: ['Welcome back', 'Sign in to your PolyPilot workspace'],
  register: ['Create your account', 'Start preparing verified problems'],
  forgot: ['Forgot your password?', "Enter your email and we'll send you a reset link"],
  reset: ['Choose a new password', 'Use at least 10 characters'],
};

export const LoginPage: React.FC<Props> = ({ expired, resetToken, authError, onSignedIn, onResetDone }) => {
  const [mode, setMode] = useState<Mode>(resetToken ? 'reset' : 'login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(
    authError ? (GOOGLE_ERRORS[authError] ?? GOOGLE_ERRORS.google_failed) : null);
  const [google, setGoogle] = useState(false);
  const [redirecting, setRedirecting] = useState(false);

  useEffect(() => {
    apiClient<{ google: boolean }>('/auth/providers').then((p) => setGoogle(p.google)).catch(() => setGoogle(false));
  }, []);

  // Full-page navigation: the backend redirects to Google and back, then sets the session cookie.
  const signInWithGoogle = () => { setRedirecting(true); window.location.assign(`${BASE_URL}/auth/google/start`); };
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

          {google && (mode === 'login' || mode === 'register') && (
            <>
              <button type="button" className="auth-google" onClick={signInWithGoogle} disabled={redirecting}>
                <GoogleIcon /> {redirecting ? 'Redirecting to Google…' : 'Continue with Google'}
              </button>
              <div className="auth-divider" role="separator">or</div>
            </>
          )}

          {mode !== 'reset' && (
            <div className="form-group">
              <label className="form-label" htmlFor="email">Email</label>
              <input id="email" className="form-input" type="email" autoComplete="email" required maxLength={254}
                placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus={!google} />
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
