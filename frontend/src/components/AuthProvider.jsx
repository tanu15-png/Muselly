import { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [initialized, setInitialized] = useState(!supabase);
  const [auth, setAuth] = useState({ status: supabase ? 'loading' : 'unconfigured', user: null, error: '' });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!supabase) return;
    let active = true;
    // Keep this callback synchronous; Supabase uses a lock around auth events.
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, nextSession) => {
      if (active) {
        setSession(nextSession);
        setInitialized(true);
        if (event === 'SIGNED_OUT') setAuth({ status: 'signed-out', user: null, error: '' });
      }
    });
    supabase.auth.getSession().then(({ data, error }) => {
      if (!active) return;
      if (error) setAuth({ status: 'signed-out', user: null, error: 'Unable to complete sign-in. Please try again.' });
      setSession(data.session);
      setInitialized(true);
    }).catch(() => {
      if (active) { setInitialized(true); setAuth({ status: 'error', user: null, error: 'Unable to check sign-in. Please try again.' }); }
    });
    return () => { active = false; subscription.unsubscribe(); };
  }, []);

  useEffect(() => {
    if (!supabase || !initialized) return;
    if (!session) { setAuth(previous => ({ status: 'signed-out', user: null, error: previous.error })); return; }
    const controller = new AbortController();
    setAuth({ status: 'loading', user: null, error: '' });
    fetch('/api/auth/me', { signal: controller.signal, cache: 'no-store', headers: { Authorization: `Bearer ${session.access_token}` } })
      .then(async response => {
        if (!response.ok) {
          const error = new Error(response.status === 401 ? 'Please sign in again to continue.' : 'Unable to check sign-in. Please try again.');
          error.status = response.status;
          throw error;
        }
        return response.json();
      })
      .then(user => {
        if (!user?.id || !user?.email) throw new Error('Unable to check sign-in. Please try again.');
        if (!controller.signal.aborted) setAuth({ status: 'signed-in', user, error: '', token: session.access_token });
      })
      .catch(error => {
        if (!controller.signal.aborted) setAuth({ status: error.status === 401 ? 'signed-out' : 'error', user: null, error: error.message });
      });
    return () => controller.abort();
  }, [session, initialized, revision]);

  // A changed token immediately hides protected content while verification runs.
  const current = auth.status === 'signed-in' && (!session || auth.token !== session.access_token)
    ? { status: session ? 'loading' : 'signed-out', user: null, error: '' } : auth;
  const value = { ...current, retry: () => setRevision(value => value + 1) };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() { return useContext(AuthContext); }
