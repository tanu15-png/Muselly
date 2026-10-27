import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import FashionDirectionBoard from './FashionDirectionBoard';
import { apiRequest } from '../lib/supabase';
vi.mock('../lib/supabase', () => ({ apiRequest: vi.fn() }));
const entity = { entity_id: 'film-1', name: 'Little Women', domain: 'movie', image: '/poster.png', preference: 'like', fashion_note: 'Cream floral dresses' };
let changed;
beforeEach(() => { vi.resetAllMocks(); localStorage.clear(); changed = vi.fn(); apiRequest.mockResolvedValue({}); });
afterEach(cleanup);
function open() { render(<FashionDirectionBoard entities={[entity]} ownerId="owner" onChange={changed} />); }
it('shows a compact note instead of reference image controls', () => {
  open(); expect(screen.getByRole('textbox').value).toBe('Cream floral dresses');
  expect(screen.queryByText('Choose looks')).toBeNull();
});
it('automatically saves a locally durable note without replacing cultural feedback', async () => {
  open(); fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Tailored black jackets' } });
  expect(localStorage.getItem('muselly-fashion-note:owner:film-1')).toBe('Tailored black jackets');
  await waitFor(() => expect(apiRequest).toHaveBeenCalledWith('/api/onboarding/culture/feedback/film-1/fashion-note', {
    method: 'PATCH', expectedOwner: 'owner', body: { note: 'Tailored black jackets' },
  }));
  await waitFor(() => expect(screen.getByRole('status').textContent).toBe('Saved'));
});
it('restores an unsynced owner-scoped draft and retains it after failure', async () => {
  localStorage.setItem('muselly-fashion-note:owner:film-1', 'Blue linen');
  apiRequest.mockRejectedValue(new Error('Offline')); open();
  expect(screen.getByRole('textbox').value).toBe('Blue linen');
  await waitFor(() => expect(screen.getByRole('status').textContent).toBe('Not synced. Will retry.'));
  expect(localStorage.getItem('muselly-fashion-note:owner:film-1')).toBe('Blue linen');
});
it('removes the fashion connection while preserving the cultural like', async () => {
  open(); fireEvent.click(screen.getByRole('button', { name: 'Remove connection' }));
  await waitFor(() => expect(changed).toHaveBeenCalledWith('film-1', false, undefined));
  expect(apiRequest.mock.calls[0][1].body).toEqual({ preference: 'like', fashion_inspiration: false });
});
