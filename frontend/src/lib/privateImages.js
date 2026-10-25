import { apiRequest } from './supabase';

// Moodboard and gallery instances share one authenticated download while mounted.
// Nothing is written to persistent browser storage; the last viewer releases it.
const previews = new Map();
export function acquirePrivateImage(image) {
  const key = `${image.id}:${image.updated_at || ''}`;
  let entry = previews.get(key);
  if (!entry) {
    const controller = new AbortController();
    entry = { users: 0, controller, url: null };
    entry.promise = apiRequest(`/api/onboarding/images/${image.id}`, { blob: true, signal: controller.signal }).then(blob => {
      if (controller.signal.aborted) throw new DOMException('Preview released', 'AbortError');
      entry.url = URL.createObjectURL(blob);
      return entry.url;
    });
    previews.set(key, entry);
  }
  entry.users += 1;
  let released = false;
  return { promise: entry.promise, release() {
    if (released) return; released = true;
    if (--entry.users === 0) {
      entry.controller.abort();
      if (entry.url) URL.revokeObjectURL(entry.url);
      if (previews.get(key) === entry) previews.delete(key);
    }
  } };
}
