// @vitest-environment node
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

vi.mock('@supabase/supabase-js', () => ({ createClient: () => ({ auth: {
  getSession: async () => ({ data: { session: { access_token: 'test-access' } } }),
} }) }));
let request, upload;
beforeEach(async () => {
  vi.stubEnv('VITE_SUPABASE_URL', 'https://test.supabase.co');
  vi.stubEnv('VITE_SUPABASE_PUBLISHABLE_KEY', 'test-key');
  vi.resetModules();
  vi.stubGlobal('XMLHttpRequest', class {
    constructor() { request = this; this.upload = {}; }
    open() {} setRequestHeader() {} send() {}
  });
  upload = (await import('./supabase')).uploadInspiration;
});
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

it('distinguishes a browser connection interruption from an upload timeout', async () => {
  const failure = upload('image-id', { type:'image/png', name:'look.png' }, () => {});
  const assertion = expect(failure).rejects.toMatchObject({ status:503, message:expect.stringContaining('connection was interrupted') });
  await Promise.resolve(); await Promise.resolve(); request.onerror(); await assertion;
});

it('explains that a timed-out upload may still be saving instead of reporting a generic error', async () => {
  const failure = upload('image-id', { type:'image/png', name:'look.png' }, () => {});
  const assertion = expect(failure).rejects.toMatchObject({ status:504, message:expect.stringContaining('server may still be saving') });
  await Promise.resolve(); await Promise.resolve(); request.ontimeout(); await assertion;
});

it('preserves the backend JSON detail for a failed upload', async () => {
  const failure = upload('image-id', { type:'image/png', name:'look.png' }, () => {});
  const assertion = expect(failure).rejects.toMatchObject({ status:503, message:'Unable to access your taste profile. Please try again.' });
  await Promise.resolve(); await Promise.resolve();
  request.status = 503; request.responseText = JSON.stringify({ detail:'Unable to access your taste profile. Please try again.' });
  request.onload(); await assertion;
});

it('rejects an HTML success response instead of creating a broken private image preview', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>app</html>', {headers:{'Content-Type':'text/html'}})));
  const { apiRequest } = await import('./supabase');
  await expect(apiRequest('/api/onboarding/images/image-id', {blob:true})).rejects.toMatchObject({status:502, message:expect.stringContaining('page instead of an image')});
});

it('returns private image bytes when the API sends a real image response', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('image-bytes', {headers:{'Content-Type':'image/png'}})));
  const { apiRequest } = await import('./supabase');
  const blob = await apiRequest('/api/onboarding/images/image-id', {blob:true});
  expect(blob.type).toBe('image/png');
  expect(await blob.text()).toBe('image-bytes');
});
