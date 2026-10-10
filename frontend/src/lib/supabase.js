import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

export const supabase = url && key ? createClient(url, key, {
  auth: { flowType: 'pkce', detectSessionInUrl: true, persistSession: true, autoRefreshToken: true },
}) : null;

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export async function apiRequest(path, { method = 'GET', body, signal } = {}) {
  if (!supabase) throw new ApiError('Sign-in is currently unavailable.', 503);
  const { data, error } = await supabase.auth.getSession();
  if (error) throw error;
  if (!data.session) throw new ApiError('Please sign in to continue.', 401);
  const response = await fetch(path, {
    method, signal, cache: 'no-store',
    headers: { Authorization: `Bearer ${data.session.access_token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(typeof result?.detail === 'string' ? result.detail : 'Unable to complete this request. Please try again.', response.status);
  return result;
}
