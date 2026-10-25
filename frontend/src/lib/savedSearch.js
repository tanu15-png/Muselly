import { readCache } from './sessionCache';

const prefix = 'muselly-last-search-v1:';
const stores = () => {
  const available = [];
  for (const name of ['localStorage', 'sessionStorage']) {
    try { available.push(globalThis[name]); } catch { /* Storage can be blocked. */ }
  }
  return available.filter(Boolean);
};

export function readSavedSearch(owner) {
  if (!owner) return null;
  for (const storage of stores()) {
    try {
      const value = JSON.parse(storage.getItem(prefix + owner));
      if (value && typeof value.query === 'string' && Array.isArray(value.selected) && value.filters && typeof value.filters === 'object') return value;
    } catch { /* Try the other storage before falling back to the old cache. */ }
  }
  return readCache(owner, 'shopping')?.value ?? null;
}

export function saveSearch(owner, value) {
  if (!owner) return;
  for (const storage of stores()) {
    try { storage.setItem(prefix + owner, JSON.stringify(value)); } catch { /* Search still works without storage. */ }
  }
}

export function clearSavedSearches() {
  for (const storage of stores()) {
    try {
      for (let index = storage.length - 1; index >= 0; index -= 1) {
        const key = storage.key(index);
        if (key?.startsWith(prefix)) storage.removeItem(key);
      }
    } catch { /* Storage is optional. */ }
  }
}
