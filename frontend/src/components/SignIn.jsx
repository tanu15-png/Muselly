import ResilientImage from './ResilientImage';
import { useEffect, useState } from 'react';
import { ArrowRight, Mail } from 'lucide-react';
import { Button, Card } from './ui';
import { useAuth } from './AuthProvider';
import { supabase } from '../lib/supabase';
import { openTasteTest } from '../lib/navigation';

function emailError(failure) {
  if (failure.code === 'email_address_not_authorized') return 'We couldn’t send a confirmation to this email address. Try Google sign-in or contact support.';
  if (['over_email_send_rate_limit', 'over_request_rate_limit'].includes(failure.code)) return 'Too many email requests. Please wait before trying again.';
  if (failure.code === 'unexpected_failure' && /email/i.test(failure.message)) return 'We couldn’t send your confirmation email. Please try again later or use Google sign-in.';
  return failure.message || 'Unable to sign in. Please try again.';
}

function GoogleIcon() {
  return <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.39-.18-2.05H12v3.88h5.38a4.6 4.6 0 0 1-2 3.02v2.52h3.24c1.9-1.75 2.98-4.33 2.98-7.37Z" /><path fill="#34A853" d="M12 22c2.7 0 4.96-.9 6.62-2.4l-3.24-2.52c-.9.6-2.06.96-3.38.96-2.6 0-4.8-1.76-5.59-4.12H3.06v2.6A10 10 0 0 0 12 22Z" /><path fill="#FBBC05" d="M6.41 13.92a6 6 0 0 1 0-3.84v-2.6H3.06a10 10 0 0 0 0 9.04l3.35-2.6Z" /><path fill="#EA4335" d="M12 5.96c1.47 0 2.79.51 3.82 1.51l2.86-2.86A9.6 9.6 0 0 0 12 2a10 10 0 0 0-8.94 5.48l3.35 2.6A5.98 5.98 0 0 1 12 5.96Z" /></svg>;
}

export default function SignIn({ header }) {
  const { status, user, error: authError, retry } = useAuth();
  const [showEmail, setShowEmail] = useState(false);
  const [mode, setMode] = useState('sign-in');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [pendingEmail, setPendingEmail] = useState('');
  const [continueAfterSignup, setContinueAfterSignup] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const unavailable = status === 'unconfigured';
  useEffect(() => { document.title = 'Sign in — Muselly'; }, []);
  useEffect(() => {
    if (continueAfterSignup && status === 'signed-in' && user) openTasteTest();
  }, [continueAfterSignup, status, user]);
  useEffect(() => {
    if (!resendCooldown) return;
    const timer = window.setInterval(() => setResendCooldown(value => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [resendCooldown]);

  async function submitEmail(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const credentials = { email: data.get('email').trim(), password: data.get('password') };
      const result = mode === 'register'
        ? await supabase.auth.signUp({ ...credentials, options: { emailRedirectTo: `${window.location.origin}/auth/callback` } })
        : await supabase.auth.signInWithPassword(credentials);
      if (result.error) throw result.error;
      if (mode === 'register') {
        setContinueAfterSignup(true);
        if (!result.data.session) {
          setPendingEmail(credentials.email);
          setResendCooldown(60);
        }
      }
    } catch (failure) {
      if (failure.code === 'email_not_confirmed') {
        setPendingEmail(data.get('email').trim());
        setContinueAfterSignup(true);
      } else setError(emailError(failure));
    } finally { setBusy(false); }
  }

  async function resendConfirmation() {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await supabase.auth.resend({
        type: 'signup', email: pendingEmail,
        options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
      });
      if (result.error) throw result.error;
      setMessage('Confirmation requested. Check your inbox and spam folder, then open the latest link in this browser.');
    } catch (failure) { setError(emailError(failure)); }
    finally { setResendCooldown(60); setBusy(false); }
  }

  async function signInWithGoogle() {
    setBusy(true);
    setError('');
    try {
      const result = await supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: `${window.location.origin}/auth/callback` } });
      if (result.error) throw result.error;
    } catch (failure) {
      setError(failure.message || 'Unable to sign in with Google. Please try again.');
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    setError('');
    try {
      const { error: failure } = await supabase.auth.signOut();
      if (failure) throw failure;
      setMessage('');
      setPendingEmail('');
      setContinueAfterSignup(false);
    } catch { setError('Unable to sign out. Please try again.'); }
    finally { setBusy(false); }
  }

  return <>{header}<main id="main-content" className="sign-in-page container">
    <Card className="sign-in-card">
      <h1>Your style,<br /><em>all in one place.</em></h1>
      <div className="sign-in-options">
        {status === 'loading' ? <p role="status">Checking your sign-in…</p> : user ? <>
          <p className="signed-in-account">Signed in as {user.email}</p>
          <Button href="/taste-test" className="button--large">Start taste test <ArrowRight size={18} /></Button>
          <button type="button" className="sign-out-link" disabled={busy} onClick={signOut}>Sign out</button>
        </> : <>
          {pendingEmail ? <div className="confirmation-pending">
            <h2>Check your inbox</h2>
            <p>Open the confirmation link for <strong>{pendingEmail}</strong> in this browser. You’ll go straight to your taste test—no extra sign-in.</p>
            <Button onClick={resendConfirmation} disabled={busy || resendCooldown > 0}>{busy ? 'Please wait…' : resendCooldown ? `Resend in ${resendCooldown}s` : 'Resend confirmation email'}</Button>
            <button type="button" className="sign-out-link" disabled={busy} onClick={() => { setPendingEmail(''); setContinueAfterSignup(false); setResendCooldown(0); setMode('register'); setMessage(''); setError(''); }}>Use a different email</button>
          </div> : showEmail ? <>
            <form className="email-sign-in" onSubmit={submitEmail}>
              <label htmlFor="sign-in-email">Email address</label>
              <input id="sign-in-email" name="email" type="email" autoComplete="email" placeholder="you@example.com" maxLength={254} required disabled={busy || unavailable} autoFocus />
              <label htmlFor="sign-in-password">Password</label>
              <input id="sign-in-password" name="password" type="password" autoComplete={mode === 'register' ? 'new-password' : 'current-password'} placeholder="Your password" minLength={mode === 'register' ? 8 : undefined} maxLength={128} required disabled={busy || unavailable} />
              <Button type="submit" disabled={busy || unavailable}>{busy ? 'Please wait…' : mode === 'register' ? 'Create account' : 'Sign in with email'} <ArrowRight size={18} /></Button>
            </form>
            <p className="account-switch">{mode === 'register' ? 'Already have an account?' : 'New to Muselly?'} <button type="button" disabled={busy} onClick={() => { setMode(mode === 'register' ? 'sign-in' : 'register'); setError(''); setMessage(''); }}>{mode === 'register' ? 'Sign in' : 'Create an account'}</button></p>
          </> : <Button className="button--large email-sign-in-option" disabled={busy || unavailable} onClick={() => setShowEmail(true)}><Mail size={19} /> Sign in with email</Button>}
          <div className="sign-in-divider"><span>or</span></div>
          <Button variant="secondary" className="button--large google-sign-in" disabled={busy || unavailable} onClick={signInWithGoogle}><GoogleIcon /> Sign in with Google</Button>
          {!pendingEmail && <p className="sign-in-required">Sign in to start your taste test.</p>}
          {unavailable && <p className="sign-in-error" role="status">Sign-in is currently unavailable. Please try again later.</p>}
          {status === 'error' && <button type="button" className="sign-out-link" onClick={retry}>Retry sign-in check</button>}
        </>}
        {message && <p className="sign-in-message" role="status">{message}</p>}
        {(error || authError) && <p className="sign-in-error" role="alert">{error || authError}</p>}
      </div>
    </Card>
    <div className="sign-in-photo"><ResilientImage src="/images/collage.png" alt="A collage of fashion and personal style inspirations" /><span className="handwritten">A style story.<br />Entirely yours.</span></div>
  </main></>;
}
