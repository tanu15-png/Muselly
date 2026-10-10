import { useEffect, useState } from 'react';
import { Button } from './ui';
import { useAuth } from './AuthProvider';
import { openTasteTest } from '../lib/navigation';

export default function AuthCallback({ header }) {
  const { status, error, retry } = useAuth();
  const [timedOut, setTimedOut] = useState(false);
  useEffect(() => {
    if (status !== 'loading') return;
    const timer = window.setTimeout(() => setTimedOut(true), 20000);
    return () => window.clearTimeout(timer);
  }, [status]);
  useEffect(() => {
    document.title = 'Completing sign-in — Muselly';
    if (status === 'signed-in') openTasteTest();
  }, [status]);
  const stalled = status === 'loading' && timedOut;
  const failed = stalled || ['signed-out', 'error', 'unconfigured'].includes(status);
  return <>{header}<main id="main-content" className="taste-page container">
    <p role="status">{stalled ? 'Sign-in is taking too long. Check that the Python backend is running, then return to sign in using the same browser and port where you started. If your email is already confirmed, sign in with your password.' : failed ? error || 'We couldn’t complete sign-in. Please try again.' : 'Completing your sign-in…'}</p>
    {failed && <div className="entry-actions">{status === 'error' && <Button onClick={retry} variant="secondary">Try again</Button>}<Button href="/sign-in">Return to sign in</Button></div>}
  </main></>;
}
