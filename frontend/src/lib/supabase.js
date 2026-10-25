import { createClient } from '@supabase/supabase-js';
import { clearCache } from './sessionCache';

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

export const supabase = url && key ? createClient(url, key, {
  auth: { flowType: 'pkce', detectSessionInUrl: true, persistSession: true, autoRefreshToken: true },
}) : null;

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export async function apiRequest(path, { method = 'GET', body, signal, blob = false, expectedOwner } = {}) {
  if (!supabase) throw new ApiError('Sign-in is currently unavailable.', 503);
  const { data, error } = await supabase.auth.getSession();
  if (error) throw error;
  if (!data.session) throw new ApiError('Please sign in to continue.', 401);
  if (expectedOwner && data.session.user?.id !== expectedOwner) throw new ApiError('Sign in to the original account to sync these choices.', 401);
  const response = await fetch(path, {
    method, signal: AbortSignal.any([...(signal ? [signal] : []), AbortSignal.timeout(blob ? 45000 : 120000)]), cache: 'no-store',
    headers: { Authorization: `Bearer ${data.session.access_token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (blob && response.ok) {
    if (!/^image\/(png|jpeg|webp)(?:;|$)/i.test(response.headers.get('Content-Type') || '')) {
      throw new ApiError('The server returned a page instead of an image. Check the API connection and retry.', 502);
    }
    return response.blob();
  }
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && data.session.user?.id) clearCache(data.session.user.id);
    throw new ApiError(typeof result?.detail === 'string' ? result.detail : 'Unable to complete this request. Please try again.', response.status);
  }
  if (method !== 'GET' && path.startsWith('/api/onboarding') && data.session.user?.id) clearCache(data.session.user.id);
  return result;
}

export async function uploadInspiration(id, file, onProgress) {
  if (!supabase) throw new ApiError('Sign-in is currently unavailable.', 503);
  const { data, error } = await supabase.auth.getSession();
  if (error) throw error;
  if (!data.session) throw new ApiError('Please sign in to continue.', 401);
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open('PUT', `/api/onboarding/images/${id}`);
    request.timeout = 120000;
    request.setRequestHeader('Authorization', `Bearer ${data.session.access_token}`);
    request.setRequestHeader('Content-Type', file.type);
    request.setRequestHeader('X-Filename', encodeURIComponent(file.name));
    request.upload.onprogress = event => { if (event.lengthComputable) onProgress(Math.round(event.loaded / event.total * 100)); };
    request.onload = () => {
      let result;
      try { result = JSON.parse(request.responseText); } catch { /* handled below */ }
      if (request.status >= 200 && request.status < 300 && result?.id) { if (data.session.user?.id) clearCache(data.session.user.id); resolve(result); }
      else reject(new ApiError(typeof result?.detail === 'string' ? result.detail : 'Upload failed. Please retry.', request.status));
    };
    request.onerror = () => reject(new ApiError('The upload connection was interrupted. Check that the backend is still running, then retry.', 503));
    request.ontimeout = () => reject(new ApiError('The upload timed out after two minutes. The server may still be saving it; reload your images before retrying.', 504));
    request.send(file);
  });
}
