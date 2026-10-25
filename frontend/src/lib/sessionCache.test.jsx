// @vitest-environment node
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { clearCache, readCache, writeCache } from './sessionCache';

beforeEach(() => {
  const items = new Map();
  vi.stubGlobal('sessionStorage', {
    get length() { return items.size; },
    key: index => [...items.keys()][index],
    getItem: key => items.get(key) ?? null,
    setItem: (key, value) => items.set(key, value),
    removeItem: key => items.delete(key),
  });
  vi.useFakeTimers();
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

it('expires freshness after five minutes and drops values after thirty minutes', () => {
  writeCache('owner', 'enrichment', { name: 'COS' });
  expect(readCache('owner', 'enrichment').fresh).toBe(true);
  vi.advanceTimersByTime(6 * 60 * 1000);
  expect(readCache('owner', 'enrichment').fresh).toBe(false);
  vi.advanceTimersByTime(25 * 60 * 1000);
  expect(readCache('owner', 'enrichment')).toBeNull();
});

it('isolates accounts and clears account data or all caches without removing unrelated storage', () => {
  writeCache('a', 'enrichment', 'a'); writeCache('a', 'sources', []); writeCache('b', 'enrichment', 'b');
  sessionStorage.setItem('unrelated', 'keep');
  expect(readCache('c', 'enrichment')).toBeNull();
  clearCache('a');
  expect(readCache('a', 'enrichment')).toBeNull();
  expect(readCache('a', 'sources')).toBeNull();
  expect(readCache('b', 'enrichment').value).toBe('b');
  clearCache();
  expect(readCache('b', 'enrichment')).toBeNull();
  expect(sessionStorage.getItem('unrelated')).toBe('keep');
});

it('works without browser storage and ignores corrupt cached data', () => {
  sessionStorage.setItem('muselly-cache-v1:owner:enrichment', '{broken');
  expect(readCache('owner', 'enrichment')).toBeNull();
  vi.stubGlobal('sessionStorage', undefined);
  expect(() => writeCache('owner', 'enrichment', {})).not.toThrow();
  expect(readCache('owner', 'enrichment')).toBeNull();
  expect(() => clearCache()).not.toThrow();
});
