import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import ExplorePage from './ExplorePage';
import ExtensionPage from './ExtensionPage';
import { useAuth } from './AuthProvider';
import { apiRequest, supabase } from '../lib/supabase';

vi.mock('./AuthProvider', () => ({ AuthProvider: ({ children }) => children, useAuth: vi.fn() }));
vi.mock('../lib/supabase', () => ({ apiRequest: vi.fn(), supabase: { auth: { getSession: vi.fn() } } }));
beforeEach(() => {
  sessionStorage.clear(); localStorage.clear(); window.scrollTo = vi.fn();
  useAuth.mockReturnValue({ status: 'signed-in', user: { id: 'owner', email: 'style@example.com' } });
  apiRequest.mockReset();
  apiRequest.mockImplementation(async path => { if (path === '/api/extension/saved') return { items: [] }; throw { status: 404 }; });
});
afterEach(() => { cleanup(); sessionStorage.clear(); window.history.replaceState({}, '', '/'); vi.unstubAllGlobals(); });

it('keeps the landing page focused on cultural discovery', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Discover cultural connections' })).toBeTruthy();
  expect(screen.getByText(/connected to your taste by Qloo/)).toBeTruthy();
  expect(document.getElementById('for-you')).toBeNull();
  expect(document.getElementById('faqs')).toBeTruthy();
  expect(screen.queryByRole('link', { name: /extension/i })).toBeNull();
  expect(screen.queryByRole('searchbox')).toBeNull();
});

it('shows Qloo brands without extension promotions or product requests', async () => {
  window.history.replaceState({}, '', '/explore'); render(<App />);
  expect(await screen.findByRole('heading', { name: /Find the brands/ })).toBeTruthy();
  expect(screen.getByRole('region', { name: 'Brand discovery' })).toBeTruthy();
  expect(screen.queryByRole('textbox', { name: 'What are you looking for?' })).toBeNull();
  expect(screen.queryByRole('link', { name: /extension/i })).toBeNull();
  expect(apiRequest.mock.calls.some(([path]) => path.startsWith('/api/extension'))).toBe(false);
  expect(apiRequest.mock.calls.some(([path]) => path.startsWith('/api/search'))).toBe(false);
  expect(apiRequest.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
});

it('keeps the existing brand page reachable directly and navigates home', async () => {
  window.history.replaceState({}, '', '/explore');
  render(<App />);
  expect(await screen.findByRole('heading', { name: /Find the brands/ })).toBeTruthy();
  fireEvent.click(screen.getByRole('link', { name: 'Home' }));
  expect(screen.getByRole('heading', { name: /Discover fashion/ })).toBeTruthy();
  await act(async () => { window.history.replaceState({}, '', '/explore'); window.dispatchEvent(new PopStateEvent('popstate')); });
  expect(await screen.findByRole('heading', { name: /Find the brands/ })).toBeTruthy();
});

it('keeps brand exploration behind sign-in', async () => {
  window.history.replaceState({}, '', '/explore#brand-affinities'); useAuth.mockReturnValue({ status: 'signed-out', user: null });
  render(<ExplorePage />); expect(screen.getByRole('button', { name: 'Sign in with email' })).toBeTruthy();
  await waitFor(() => expect(sessionStorage.getItem('muselly-explore-return')).toBe('/explore#brand-affinities'));
  expect(apiRequest).not.toHaveBeenCalled();
});

it('explains unpacked installation and does not silently pair an account', async () => {
  window.history.replaceState({}, '', '/extension'); render(<ExtensionPage />);
  expect(screen.getByRole('link', { name: 'Get Extension' }).hasAttribute('download')).toBe(true);
  expect(screen.getByText('Load unpacked')).toBeTruthy();
  expect(supabase.auth.getSession).not.toHaveBeenCalled();
});

it('sends the access session only after an explicit valid connection action', async () => {
  const nonce = 'a'.repeat(64), extensionId = 'a'.repeat(32);
  window.history.replaceState({}, '', `/extension/connect?extension_id=${extensionId}&nonce=${nonce}`);
  const sendMessage = vi.fn((id, message, callback) => callback({ ok: true }));
  vi.stubGlobal('chrome', { runtime: { sendMessage } });
  supabase.auth.getSession.mockResolvedValue({ data: { session: { access_token: 'access-test', expires_at: 9999999999 } } });
  render(<ExtensionPage connect />); expect(sendMessage).not.toHaveBeenCalled();
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Connect extension' })));
  expect(sendMessage).toHaveBeenCalledWith(extensionId, { type:'MUSELLY_CONNECT', nonce, accessToken:'access-test', expiresAt:9999999999 }, expect.any(Function));
  expect(screen.getByRole('heading', { name: 'Connected to Muselly.' })).toBeTruthy();
});

it.each(['/extension', '/extension/connect'])('does not expose the removed setup route %s', path => {
  window.history.replaceState({}, '', path);
  render(<App />);
  expect(screen.getByRole('heading', { name: 'This page is still on the moodboard.' })).toBeTruthy();
  expect(screen.queryByRole('link', { name: 'Get Extension' })).toBeNull();
});
