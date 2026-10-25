import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './AuthProvider';
import { supabase } from '../lib/supabase';
import { readCache, writeCache } from '../lib/sessionCache';
import { readSavedSearch, saveSearch } from '../lib/savedSearch';

vi.mock('../lib/supabase', () => ({ supabase: { auth: {
  onAuthStateChange: vi.fn(), getSession: vi.fn(),
} } }));

function Status() {
  const { status, error, retry } = useAuth();
  return <><p>{status}</p><p>{error}</p><button onClick={retry}>Retry</button></>;
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  vi.useFakeTimers();
  supabase.auth.onAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } });
  supabase.auth.getSession.mockResolvedValue({ data: { session: { access_token: 'test-token' } }, error: null });
  vi.stubGlobal('fetch', vi.fn());
});

it('keeps verified content mounted when returning to a tab emits the same session', async () => {
  fetch.mockResolvedValue({ ok: true, json: async () => ({ id: 'user-id', email: 'user@example.com' }) });
  await act(async () => { render(<AuthProvider><Status /></AuthProvider>); });
  const onAuth = supabase.auth.onAuthStateChange.mock.calls[0][0];
  await act(async () => onAuth('SIGNED_IN', { access_token: 'test-token' }));
  expect(screen.getByText('signed-in')).toBeTruthy();
  expect(fetch).toHaveBeenCalledTimes(1);
  writeCache('user-id', 'enrichment', { status: 'succeeded' });
  saveSearch('user-id', { query: 'dress', filters: {}, selected: [], result: null });
  await act(async () => onAuth('SIGNED_OUT', null));
  expect(screen.getByText('signed-out')).toBeTruthy();
  expect(readCache('user-id', 'enrichment')).toBeNull();
  expect(readSavedSearch('user-id')).toBeNull();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); vi.clearAllMocks(); });

it('times out a stalled backend and can verify the session on retry', async () => {
  fetch.mockImplementationOnce(() => new Promise(() => {}));
  await act(async () => { render(<AuthProvider><Status /></AuthProvider>); });
  const signal = fetch.mock.calls[0][1].signal;
  await act(async () => { vi.advanceTimersByTime(15000); });
  expect(signal.aborted).toBe(true);
  expect(screen.getByText('error')).toBeTruthy();
  expect(screen.getByText(/Python backend/)).toBeTruthy();

  fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ id: 'user-id', email: 'user@example.com' }) });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Retry' })); });
  expect(screen.getByText('signed-in')).toBeTruthy();
  await act(async () => { vi.advanceTimersByTime(15000); });
  expect(screen.getByText('signed-in')).toBeTruthy();
});

it('cancels verification when the provider unmounts', async () => {
  fetch.mockImplementationOnce(() => new Promise(() => {}));
  let view;
  await act(async () => { view = render(<AuthProvider><Status /></AuthProvider>); });
  const signal = fetch.mock.calls[0][1].signal;
  view.unmount();
  expect(signal.aborted).toBe(true);
  expect(vi.getTimerCount()).toBe(0);
});
