const prefix = 'muselly-cache-v1:';
export const FRESH_FOR = 5 * 60 * 1000;
const MAX_AGE = 30 * 60 * 1000;

export function readCache(owner, name) {
  if (!owner) return null;
  try {
    const entry = JSON.parse(sessionStorage.getItem(`${prefix}${owner}:${name}`));
    const age = Date.now() - entry?.savedAt;
    if (!entry || !Number.isFinite(age) || age < 0 || age > MAX_AGE) return null;
    return { ...entry, fresh: age < FRESH_FOR };
  } catch { return null; }
}

export function writeCache(owner, name, value) {
  if (!owner) return;
  try { sessionStorage.setItem(`${prefix}${owner}:${name}`, JSON.stringify({ value, savedAt: Date.now() })); }
  catch { /* Storage may be unavailable or full; normal requests still work. */ }
}

export function clearCache(owner, name) {
  try {
    const start = owner ? `${prefix}${owner}:` : prefix;
    for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
      const key = sessionStorage.key(index);
      if (key?.startsWith(start) && (!name || key === `${start}${name}`)) sessionStorage.removeItem(key);
    }
  } catch { /* Storage is optional. */ }
}
