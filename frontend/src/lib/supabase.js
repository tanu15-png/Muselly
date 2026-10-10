import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

export const supabase = url && key ? createClient(url, key, {
  auth: { flowType: 'pkce', detectSessionInUrl: true, persistSession: true, autoRefreshToken: true },
}) : null;

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export async function apiRequest(path, { method = 'GET', body, signal, blob = false } = {}) {
  if (!supabase) throw new ApiError('Sign-in is currently unavailable.', 503);
  const { data, error } = await supabase.auth.getSession();
  if (error) throw error;
  if (!data.session) throw new ApiError('Please sign in to continue.', 401);
  const response = await fetch(path, {
    method, signal, cache: 'no-store',
    headers: { Authorization: `Bearer ${data.session.access_token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (blob && response.ok) return response.blob();
  const result = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(typeof result?.detail === 'string' ? result.detail : 'Unable to complete this request. Please try again.', response.status);
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
      if (request.status >= 200 && request.status < 300 && result?.id) resolve(result);
      else reject(new ApiError(typeof result?.detail === 'string' ? result.detail : 'Upload failed. Please retry.', request.status));
    };
    request.onerror = request.ontimeout = () => reject(new ApiError('Upload interrupted. Please retry.', 503));
    request.send(file);
  });
}
