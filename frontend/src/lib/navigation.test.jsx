// @vitest-environment node
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { openTasteTest } from './navigation';

beforeEach(() => {
  vi.stubGlobal('PopStateEvent', class { constructor(type) { this.type = type; } });
  vi.stubGlobal('window', { history: { replaceState: vi.fn(), pushState: vi.fn() }, location: { hash: '' }, dispatchEvent: vi.fn(), scrollTo: vi.fn() });
  const storage = new Map();
  vi.stubGlobal('sessionStorage', {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: key => storage.delete(key),
  });
});
afterEach(() => vi.unstubAllGlobals());

it('returns an OAuth callback to discovery with its query and consumes the destination', () => {
  sessionStorage.setItem('muselly-explore-return', '/explore?q=midi%20dress#brand-affinities');
  openTasteTest();
  expect(window.history.replaceState).toHaveBeenCalledWith({}, '', '/explore?q=midi%20dress#brand-affinities');
  expect(sessionStorage.getItem('muselly-explore-return')).toBeNull();
});

it.each(['https://example.com/explore', '//example.com/explore', '/explore/../sign-in', '/explore-something'])('rejects an unexpected return destination: %s', destination => {
  sessionStorage.setItem('muselly-explore-return', destination);
  openTasteTest();
  expect(window.history.replaceState).toHaveBeenCalledWith({}, '', '/taste-test');
});
