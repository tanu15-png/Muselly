import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SignIn from './SignIn';
import AuthCallback from './AuthCallback';
import { useAuth } from './AuthProvider';
import { supabase } from '../lib/supabase';
import { openTasteTest } from '../lib/navigation';

vi.mock('./AuthProvider', () => ({ useAuth: vi.fn() }));
vi.mock('../lib/supabase', () => ({ supabase: { auth: {
  signUp: vi.fn(), signInWithPassword: vi.fn(), resend: vi.fn(), signInWithOAuth: vi.fn(), signOut: vi.fn(),
} } }));
vi.mock('../lib/navigation', () => ({ openTasteTest: vi.fn() }));

const signedOut = { status: 'signed-out', user: null, error: '', retry: vi.fn() };
const signedIn = { status: 'signed-in', user: { id: 'verified-id', email: 'style@example.com' }, error: '', retry: vi.fn() };

beforeEach(() => {
  vi.resetAllMocks();
  useAuth.mockReturnValue(signedOut);
  supabase.auth.signUp.mockResolvedValue({ data: { session: null }, error: null });
  supabase.auth.resend.mockResolvedValue({ error: null });
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

async function register() {
  fireEvent.click(screen.getByRole('button', { name: 'Sign in with email' }));
  fireEvent.click(screen.getByRole('button', { name: 'Create an account' }));
  fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'style@example.com' } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'test-password' } });
  await act(async () => { fireEvent.submit(screen.getByRole('button', { name: 'Create account' }).closest('form')); });
}

describe('email registration and confirmation', () => {
  it('keeps unconfirmed accounts on a confirmation screen without requesting another sign-in', async () => {
    render(<SignIn />);
    await register();
    expect(supabase.auth.signUp).toHaveBeenCalledWith({ email: 'style@example.com', password: 'test-password', options: { emailRedirectTo: `${window.location.origin}/auth/callback` } });
    expect(screen.getByRole('heading', { name: 'Check your inbox' })).toBeTruthy();
    expect(screen.queryByLabelText('Password')).toBeNull();
    expect(screen.getByText(/no extra sign-in/)).toBeTruthy();
    expect(supabase.auth.signInWithPassword).not.toHaveBeenCalled();
    expect(openTasteTest).not.toHaveBeenCalled();
  });

  it('continues immediate registration only after the backend verifies its session', async () => {
    supabase.auth.signUp.mockResolvedValue({ data: { session: { access_token: 'new-session' } }, error: null });
    const view = render(<SignIn />);
    await register();
    expect(openTasteTest).not.toHaveBeenCalled();
    useAuth.mockReturnValue(signedIn);
    view.rerender(<SignIn />);
    await waitFor(() => expect(openTasteTest).toHaveBeenCalledTimes(1));
    expect(supabase.auth.signInWithPassword).not.toHaveBeenCalled();
  });

  it('continues when confirmation in another tab produces a verified session', async () => {
    const view = render(<SignIn />);
    await register();
    useAuth.mockReturnValue(signedIn);
    view.rerender(<SignIn />);
    await waitFor(() => expect(openTasteTest).toHaveBeenCalledTimes(1));
  });

  it('resends confirmation using the same callback and enforces a cooldown', async () => {
    vi.useFakeTimers();
    render(<SignIn />);
    await register();
    expect(screen.getByRole('button', { name: 'Resend in 60s' }).disabled).toBe(true);
    await act(async () => { vi.advanceTimersByTime(60_000); });
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Resend confirmation email' })); });
    expect(supabase.auth.resend).toHaveBeenCalledWith({ type: 'signup', email: 'style@example.com', options: { emailRedirectTo: `${window.location.origin}/auth/callback` } });
    expect(screen.getByRole('button', { name: 'Resend in 60s' }).disabled).toBe(true);
    expect(screen.getByText(/Confirmation requested/)).toBeTruthy();
  });

  it('shows mail-service failures instead of claiming confirmation succeeded', async () => {
    supabase.auth.signUp.mockResolvedValue({ data: {}, error: { code: 'email_address_not_authorized', message: 'Email address not authorized' } });
    render(<SignIn />);
    await register();
    expect(screen.getByRole('alert').textContent).toMatch(/couldn’t send a confirmation/);
    expect(screen.queryByRole('heading', { name: 'Check your inbox' })).toBeNull();
    expect(openTasteTest).not.toHaveBeenCalled();
  });

  it('lets existing unconfirmed accounts request confirmation without registering again', async () => {
    supabase.auth.signInWithPassword.mockResolvedValue({ error: { code: 'email_not_confirmed' } });
    render(<SignIn />);
    fireEvent.click(screen.getByRole('button', { name: 'Sign in with email' }));
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'style@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'test-password' } });
    await act(async () => { fireEvent.submit(screen.getByRole('button', { name: 'Sign in with email' }).closest('form')); });
    expect(screen.getByRole('heading', { name: 'Check your inbox' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Resend confirmation email' }).disabled).toBe(false);
    expect(supabase.auth.signUp).not.toHaveBeenCalled();
  });
});

describe('email and Google callbacks', () => {
  it('offers recovery when session verification stalls', async () => {
    vi.useFakeTimers();
    useAuth.mockReturnValue({ status: 'loading' });
    render(<AuthCallback />);
    await act(async () => { vi.advanceTimersByTime(20000); });
    expect(screen.getByText(/Sign-in is taking too long/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Return to sign in' })).toBeTruthy();
    expect(openTasteTest).not.toHaveBeenCalled();
  });

  it('opens the taste test directly after verification', () => {
    useAuth.mockReturnValue(signedIn);
    render(<AuthCallback />);
    expect(openTasteTest).toHaveBeenCalledTimes(1);
  });

  it('keeps failed callbacks signed out', () => {
    render(<AuthCallback />);
    expect(openTasteTest).not.toHaveBeenCalled();
    expect(screen.getByRole('link', { name: 'Return to sign in' })).toBeTruthy();
  });
});
