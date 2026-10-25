import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import EnrichmentPanel from './EnrichmentPanel';
import { apiRequest } from '../lib/supabase';
import { writeCache } from '../lib/sessionCache';

vi.mock('../lib/supabase', () => ({ apiRequest: vi.fn() }));
const endpoint = '/api/onboarding/enrichment';
let saved;
const success = () => ({ id: 'run-1', status: 'succeeded', stale: false, completed_at: '2026-10-17T12:00:00Z', dismissed: [],
  result: { outcome: 'enriched', resolutions: [{ input: 'Zara', status: 'resolved' }, { input: 'Unknown brand', status: 'unsupported' }],
    affinities: [{ entity_id: 'brand-id', name: 'COS', category: 'fashion' }] } });
beforeEach(() => {
  sessionStorage.clear();
  vi.resetAllMocks();
  saved = success();
  apiRequest.mockImplementation(async () => saved);
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

it('shows cached affinities immediately on return without another saved-results request', async () => {
  const first = render(<EnrichmentPanel ownerId="owner" />);
  await screen.findByText('COS');
  first.unmount(); apiRequest.mockClear();
  render(<EnrichmentPanel ownerId="owner" />);
  expect(screen.getByText('COS')).toBeTruthy();
  expect(screen.queryByText('Loading saved brand affinities…')).toBeNull();
  expect(apiRequest).not.toHaveBeenCalled();
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Refresh brand affinities' })));
  expect(apiRequest).toHaveBeenCalledWith(`${endpoint}?force=true`, expect.objectContaining({ method: 'POST' }));
});

it('revalidates older cached brands in the background without removing them', async () => {
  vi.useFakeTimers();
  writeCache('owner', 'enrichment', saved);
  vi.advanceTimersByTime(6 * 60 * 1000);
  apiRequest.mockImplementation(() => new Promise(() => {}));
  render(<EnrichmentPanel ownerId="owner" />);
  expect(screen.getByText('COS')).toBeTruthy();
  expect(screen.queryByText('Loading saved brand affinities…')).toBeNull();
  expect(apiRequest).toHaveBeenCalledTimes(1);
});

it('does not show a different account’s cached affinities', () => {
  writeCache('another-owner', 'enrichment', saved);
  apiRequest.mockImplementation(() => new Promise(() => {}));
  render(<EnrichmentPanel ownerId="owner" />);
  expect(screen.queryByText('COS')).toBeNull();
  expect(screen.getByText('Loading saved brand affinities…')).toBeTruthy();
});

it('loads saved affinities with provenance and makes no provider-generating request', async () => {
  render(<EnrichmentPanel />);
  expect(await screen.findByText('COS')).toBeTruthy();
  expect(screen.getByText('Qloo affinities')).toBeTruthy();
  expect(screen.getByText(/Based on your saved interests: Zara/)).toBeTruthy();
  expect(screen.queryByText(/Unknown brand/)).toBeNull();
  expect(screen.queryByText(/Interests kept in your profile/)).toBeNull();
  expect(apiRequest.mock.calls.every(([, options]) => !options?.method)).toBe(true);
});

it('only generates on explicit activation and requests a refresh for existing results', async () => {
  render(<EnrichmentPanel />);
  await screen.findByText('COS');
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Refresh brand affinities' })); });
  expect(apiRequest).toHaveBeenCalledWith(`${endpoint}?force=true`, expect.objectContaining({ method: 'POST' }));
});

it('starts empty profiles with an explicit enrichment action', async () => {
  apiRequest.mockRejectedValueOnce({ status: 404 });
  render(<EnrichmentPanel />);
  const button = await screen.findByRole('button', { name: 'Enrich my preferences' });
  await waitFor(() => expect(button.disabled).toBe(false));
  await act(async () => { fireEvent.click(button); });
  expect(apiRequest).toHaveBeenCalledWith(endpoint, expect.objectContaining({ method: 'POST' }));
  expect(screen.getByText('COS')).toBeTruthy();
});

it('keeps previous affinities available on provider failure and shows stale provenance', async () => {
  saved.stale = true;
  render(<EnrichmentPanel />);
  await screen.findByText('COS');
  expect(screen.getByText(/Refresh these affinities/)).toBeTruthy();
  apiRequest.mockRejectedValueOnce({ status: 503 });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Refresh brand affinities' })); });
  expect(screen.getByRole('alert').textContent).toMatch(/currently unavailable/);
  expect(screen.getByText('COS')).toBeTruthy();
});

it('dismisses and restores a brand through explicit preference updates', async () => {
  render(<EnrichmentPanel />);
  await screen.findByText('COS');
  saved = { ...saved, dismissed: [{ entity_id: 'brand-id', name: 'COS' }], result: { ...saved.result, affinities: [] } };
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Not for me.*COS/ })); });
  expect(apiRequest).toHaveBeenCalledWith(`${endpoint}/affinities/brand-id`, expect.objectContaining({ method: 'PUT', body: { dismissed: true } }));
  expect(screen.getByText(/Hidden brand affinities/)).toBeTruthy();
  fireEvent.click(screen.getByText('Hidden brand affinities (1)'));
  saved = success();
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Restore.*COS/ })); });
  expect(apiRequest).toHaveBeenCalledWith(`${endpoint}/affinities/brand-id`, expect.objectContaining({ method: 'PUT', body: { dismissed: false } }));
  expect(screen.getByRole('button', { name: /Not for me.*COS/ })).toBeTruthy();
});

it('presents no-coverage results without inventing affinities', async () => {
  saved.result = { ...saved.result, outcome: 'no-supported-signals', affinities: [], resolutions: [] };
  render(<EnrichmentPanel />);
  expect(await screen.findByText('No brand affinities added yet.')).toBeTruthy();
  expect(screen.getByRole('link', { name: 'Add a favorite artist' }).getAttribute('href')).toBe('/taste-test?edit=1&question=q7');
  expect(screen.getByText(/Last checked/)).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Check enrichment progress' })).toBeNull();
  expect(screen.queryByText('COS')).toBeNull();
});

it('links existing saved brands to verified sites without refreshing enrichment', async () => {
  saved.result.affinities = [{ entity_id: '2bbdf9d4-9d86-476c-b6ee-d2fa9ecf2a23', name: 'Nykaa Fashion', category: 'fashion' }];
  render(<EnrichmentPanel />);
  const link = await screen.findByRole('link', { name: /Visit website: Nykaa Fashion/ });
  expect(link.href).toBe('https://www.nykaafashion.com/');
  expect(link.target).toBe('_blank');
  expect(link.rel).toContain('noopener');
  expect(link.rel).toContain('noreferrer');
  expect(apiRequest.mock.calls.every(([, options]) => !options?.method)).toBe(true);
});

it('offers a clearly labelled search when an official link is not verified', async () => {
  saved.result.affinities = [{ entity_id: 'new-brand', name: 'Unknown & Brand', category: 'fashion' }];
  render(<EnrichmentPanel />);
  const link = await screen.findByRole('link', { name: /Find website: Unknown & Brand/ });
  expect(new URL(link.href).searchParams.get('q')).toBe('Unknown & Brand official website');
  expect(screen.queryByRole('link', { name: /Visit website/ })).toBeNull();
});

it('restores a running request after refresh and checks status without regenerating', async () => {
  vi.useFakeTimers();
  saved = { id: 'pending', status: 'running', created_at: new Date().toISOString(), previous_successful: success() };
  await act(async () => { render(<EnrichmentPanel />); });
  expect(screen.getByText('COS')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Refresh brand affinities' }).disabled).toBe(true);
  saved = success();
  await act(async () => { vi.advanceTimersByTime(4000); });
  expect(screen.getByRole('button', { name: 'Refresh brand affinities' }).disabled).toBe(false);
  expect(apiRequest.mock.calls.every(([, options]) => !options?.method)).toBe(true);
});
