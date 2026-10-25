import { afterEach, beforeEach, expect, it, vi } from 'vitest';
const state = vi.hoisted(() => ({ session: null }));
vi.mock('@supabase/supabase-js', () => ({ createClient: () => ({ auth: { getSession: async () => ({ data: { session: state.session } }) } }) }));
beforeEach(() => {
  vi.resetModules(); vi.stubEnv('VITE_SUPABASE_URL', 'https://example.supabase.co'); vi.stubEnv('VITE_SUPABASE_PUBLISHABLE_KEY', 'public-test-key');
  state.session = { user: { id: 'account-b' }, access_token: 'test-token' };
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ acked: [] }) })));
});
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
it('never sends another account’s queued choices with the current account token', async () => {
  const { apiRequest } = await import('./supabase');
  await expect(apiRequest('/api/onboarding/culture/sessions/s1/sync', { method: 'POST', body: { actions: [] }, expectedOwner: 'account-a' })).rejects.toMatchObject({ status: 401 });
  expect(fetch).not.toHaveBeenCalled();
});
it('allows synchronization only for the matching signed-in account', async () => {
  const { apiRequest } = await import('./supabase');
  await apiRequest('/api/onboarding/culture/sessions/s1/sync', { method: 'POST', body: { actions: [] }, expectedOwner: 'account-b' });
  expect(fetch).toHaveBeenCalledTimes(1);
});
