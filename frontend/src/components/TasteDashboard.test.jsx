import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { IDBFactory } from 'fake-indexeddb';
import TasteDashboard from './TasteDashboard';
import { apiRequest } from '../lib/supabase';
import { createDiscoveryStore } from '../lib/discoveryOutbox';
const storage = vi.hoisted(() => ({ current: null }));
vi.mock('../lib/supabase', () => ({ apiRequest: vi.fn(), supabase: null }));
vi.mock('../lib/discoveryOutbox', async original => {
  const module = await original();
  return { ...module, discoveryStore: new Proxy({}, { get: (_, key) => (...args) => storage.current[key](...args) }) };
});
const cards = Array.from({ length: 12 }, (_, index) => ({ entity_id: `entity-${index}`, domain: ['artist', 'movie', 'tv_show', 'book'][index % 4], type: `urn:entity:${['artist', 'movie', 'tv_show', 'book'][index % 4]}`, name: `Discovery ${index + 1}`, image: null }));
const profile = { completed_at: '2026-10-10', answers: {}, images: [{ id: 'look-1', filename: 'look.jpg', updated_at: '2026-10-10' }] };
const analytics = { visual: { analyzed_images: 1, saved_images: 1, colors: [{ label: 'Cream', count: 1, image_ids: ['look-1'] }], patterns: [{ label: 'Floral', count: 1, image_ids: ['look-1'] }], aesthetics: [], stated_colors: ['Pastels'] }, cultural: { totals: { shown: 1, liked: 0, disliked: 0, known: 0, fashion: 0 }, domains: [{ id: 'artist', shown: 1, liked: 0, disliked: 0, known: 0, fashion: 0, rated: 0, like_rate: null }], themes: [], history: [], sessions: 1 }, combined: { fashion_entities: [], fashion_themes: [] } };
let run;
beforeEach(() => {
  vi.resetAllMocks(); storage.current = createDiscoveryStore(new IDBFactory());
  run = { status: 'succeeded', result: { domains: [] }, session: { id: 's1', queue: structuredClone(cards), domains: [], has_more: false } };
  apiRequest.mockImplementation(async (path, options) => {
    if (options?.blob) return new Blob(['image']);
    if (path === '/api/onboarding') return profile;
    if (path.startsWith('/api/onboarding/analysis')) return { status: 'succeeded', stale: false, sources: {}, result: { images: [] } };
    if (path.endsWith('/culture/analytics')) return analytics;
    if (path.endsWith('/sync')) return { acked: options.body.actions.map(row => row.event_id) };
    return structuredClone(run);
  });
  URL.createObjectURL = vi.fn(() => 'blob:preview'); URL.revokeObjectURL = vi.fn(); HTMLElement.prototype.scrollIntoView = vi.fn();
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
});
afterEach(cleanup);
async function open() { render(<TasteDashboard user={{ id: 'owner' }} />); await screen.findByRole('article', { name: 'Discovery 1' }); }
it('shows a single mixed poster without category tabs or a request per view', async () => {
  await open(); expect(screen.queryByRole('button', { name: 'Mix', exact: true })).toBeNull();
  for (const name of ['Music', 'Films', 'Shows', 'Books']) expect(screen.queryByRole('button', { name, exact: true })).toBeNull();
  expect(screen.queryByRole('article', { name: 'Discovery 2' })).toBeNull();
  await waitFor(async () => expect((await storage.current.load('owner')).pending.some(row => row.action === 'shown')).toBe(true));
  expect(apiRequest.mock.calls.some(([path]) => path.includes('/shown/'))).toBe(false);
});
it('advances immediately after a durable local choice without waiting for the server', async () => {
  await open(); fireEvent.click(screen.getByRole('button', { name: 'I like this' }));
  await screen.findByRole('article', { name: 'Discovery 2' });
  expect(apiRequest.mock.calls.some(([path]) => path.includes('/choices/'))).toBe(false);
  const local = await storage.current.load('owner');
  expect(local.pending.some(row => row.action === 'like')).toBe(true);
  expect(local.run.session.queue[0].name).toBe('Discovery 2');
});
it('restores the local next card after reloading and keeps stale server cards hidden', async () => {
  await open(); fireEvent.click(screen.getByRole('button', { name: 'Not for me' })); await screen.findByRole('article', { name: 'Discovery 2' });
  cleanup(); render(<TasteDashboard user={{ id: 'owner' }} />);
  await screen.findByRole('article', { name: 'Discovery 2' });
  expect(screen.queryByRole('article', { name: 'Discovery 1' })).toBeNull();
});
it('undo restores locally before any server response', async () => {
  await open(); fireEvent.click(screen.getByRole('button', { name: 'Use as fashion inspiration' }));
  await screen.findByRole('article', { name: 'Discovery 2' });
  expect(screen.queryByRole('dialog')).toBeNull();
  expect((await storage.current.load('owner')).pending.find(row => row.action === 'fashion').reference_image_ids).toBeUndefined();
  fireEvent.click(screen.getByRole('button', { name: 'Undo' })); await screen.findByRole('article', { name: 'Discovery 1' });
  const local = await storage.current.load('owner');
  expect(local.pending.filter(row => row.action !== 'shown').map(row => row.action)).toEqual(['fashion', 'undo']);
});
it('waits for acknowledgements before fetching analytics but keeps the deck interactive', async () => {
  await open(); let release;
  const prior = apiRequest.getMockImplementation(); let held = false;
  apiRequest.mockImplementation((path, options) => {
    if (path.endsWith('/sync') && !held) { held = true; return new Promise(resolve => { release = () => resolve({ acked: options.body.actions.map(row => row.event_id) }); }); }
    return prior(path, options);
  });
  fireEvent.click(screen.getByRole('button', { name: 'I like this' })); await screen.findByRole('article', { name: 'Discovery 2' });
  fireEvent.click(screen.getByText('View analytics'));
  await waitFor(() => expect(release).toBeTruthy());
  expect(apiRequest.mock.calls.some(([path]) => path.endsWith('/culture/analytics'))).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: 'Already know' })); await screen.findByRole('article', { name: 'Discovery 3' });
  release(); await screen.findByRole('heading', { name: 'Your color palette' });
  expect(screen.getByRole('heading', { name: 'Patterns you save' })).toBeTruthy();
});
it('failed synchronization retains choices and does not disable the next card', async () => {
  await open(); const prior = apiRequest.getMockImplementation();
  apiRequest.mockImplementation((path, options) => path.endsWith('/sync') ? Promise.reject(new Error('Offline')) : prior(path, options));
  fireEvent.click(screen.getByRole('button', { name: 'I like this' })); await screen.findByRole('article', { name: 'Discovery 2' });
  fireEvent.click(screen.getByText('View analytics')); await screen.findByText('Waiting to sync your latest choices before showing analytics.');
  fireEvent.click(screen.getByRole('button', { name: 'Not for me' })); await screen.findByRole('article', { name: 'Discovery 3' });
  expect((await storage.current.load('owner')).pending.filter(row => row.action !== 'shown')).toHaveLength(2);
  expect(apiRequest.mock.calls.some(([path]) => path.endsWith('/culture/analytics'))).toBe(false);
});
it('automatically retries unavailable music even before a choice is made', async () => {
  run.session.domains = [{ id: 'artist', status: 'unavailable' }];
  await open();
  await waitFor(() => expect(apiRequest.mock.calls.some(([path]) => path.includes('/batch?retry=true'))).toBe(true), { timeout: 5000 });
});
it('keeps inspirations accessible and opens visual evidence from analytics', async () => {
  await open(); const library = screen.getByText('My inspirations').closest('details'); expect(library.open).toBe(false);
  fireEvent.click(screen.getByText('View analytics')); await screen.findByRole('heading', { name: 'Your color palette' });
  fireEvent.click(screen.getByRole('button', { name: /Cream/ })); expect(library.open).toBe(true);
  expect(screen.getByRole('link', { name: /Manage inspirations/ }).getAttribute('href')).toContain('step=inspirations');
});

it('keeps the selected analytics view after syncing another deck choice', async () => {
  await open(); fireEvent.click(screen.getByText('View analytics'));
  await screen.findByRole('heading', { name: 'Your color palette' });
  fireEvent.click(screen.getByRole('button', { name: 'Cultural taste', exact: true }));
  await screen.findByRole('heading', { name: 'Your cultural taste' });
  fireEvent.click(screen.getByRole('button', { name: 'I like this' }));
  await screen.findByRole('article', { name: 'Discovery 2' });
  await screen.findByRole('heading', { name: 'Your cultural taste' });
  expect(screen.getByRole('button', { name: 'Cultural taste', exact: true }).getAttribute('aria-pressed')).toBe('true');
});
