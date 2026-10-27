import { ReadableStream } from 'node:stream/web';
import { TextDecoder, TextEncoder } from 'node:util';
globalThis.TextDecoder ??= TextDecoder;
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { OutfitShop } from './ShoppingPage';
import { apiRequest } from '../lib/supabase';
import { shoppingFeedbackStore } from '../lib/shoppingFeedback';
vi.mock('../lib/supabase', () => ({ apiRequest: vi.fn(), supabase: null }));
vi.mock('./AuthProvider', () => ({ useAuth: () => ({ status: 'signed-in', user: { id: 'owner' } }) }));
function agentResponse(result) {
  const bytes = new TextEncoder().encode(JSON.stringify({ type: 'progress', message: 'Exploring Qloo connections' }) + '\n' + JSON.stringify({ type: 'result', result }) + '\n');
  return { body: new ReadableStream({ start(controller) { controller.enqueue(bytes); controller.close(); } }) };
}
const product = { product_id: '101', name: 'Floral midi dress', brand: 'Example', price: 900, taste_match: 87, image_url: '/images/romantic-dress.png', product_url: 'https://www.myntra.com/dresses/example/101/buy', why: ['Matches floral in your linked looks'] };
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear();
  apiRequest.mockImplementation(async path => path.endsWith('/feedback') ? { choices: {} } : agentResponse({
    agent: { session_id: 'session-1', revision: 1, message: 'A shortlist guided by your taste.', question: false },
    products: [product], total: 1, catalog_count: 1500, filters: { categories: ['Dresses'], max_price: 1000 }, taste: { qloo_status: 'ready', qloo_brands: 1, linked_discoveries: 1 },
  }));
});
afterEach(cleanup);
it('waits for initial server reconciliation before replaying feedback on an online event', async () => {
  shoppingFeedbackStore().choose('owner', '101', 'like');
  let resolveInitial;
  apiRequest.mockImplementation((path, options) => options?.method === 'POST' ? Promise.resolve({}) : new Promise(resolve => { resolveInitial = resolve; }));
  render(<OutfitShop ownerId="owner" />);
  await waitFor(() => expect(resolveInitial).toBeTruthy());
  fireEvent(window, new Event('online'));
  expect(apiRequest.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  resolveInitial({ choices: {} });
  await waitFor(() => expect(screen.getByRole('button', { name: 'My likes' }).disabled).toBe(false));
});
async function search() {
  render(<OutfitShop ownerId="owner" />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'My likes' }).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('What would you like to wear?'), { target: { value: 'floral dress under 1000' } });
  fireEvent.click(screen.getByRole('button', { name: 'Find my outfit' }));
  await screen.findByRole('article', { name: product.name });
}
it('shows product links and snapshot pricing with a plain-English search', async () => {
  await search(); expect(screen.getByText('87% taste match')).toBeTruthy(); expect(screen.getByRole('link', { name: 'View on Myntra' }).getAttribute('href')).toBe(product.product_url);
  expect(screen.getByText(/confirm current price/i)).toBeTruthy();
  expect(apiRequest.mock.calls.find(([path]) => path.endsWith('/agent'))[1]).toMatchObject({ expectedOwner: 'owner', body: { message: 'floral dress under 1000', offset: 0 } });
});

it('labels each retailer and preserves its direct product link', async () => {
  const ajio = { ...product, product_id: 'ajio:123_blue', retailer: 'AJIO', product_url: 'https://www.ajio.com/example/p/123_blue' };
  apiRequest.mockImplementation(async path => path.endsWith('/feedback') ? { choices: {} } : agentResponse({
    agent: { session_id: 'session-1', revision: 1, message: 'Your shortlist.' }, products: [ajio], total: 1,
    catalog_count: 2500, filters: {}, taste: {},
  }));
  await search();
  expect(screen.getByRole('link', { name: 'View on AJIO' }).getAttribute('href')).toBe(ajio.product_url);
});
it('likes immediately during a stalled save, restores after reload, and supports dislike undo', async () => {
  await search();
  const prior = apiRequest.getMockImplementation();
  apiRequest.mockImplementation((path, options) => options?.method === 'POST' && path.endsWith('/feedback') ? new Promise(() => {}) : prior(path, options));
  fireEvent.click(screen.getByRole('button', { name: 'I like this' }));
  expect(screen.getByRole('button', { name: 'Liked' }).getAttribute('aria-pressed')).toBe('true');
  cleanup();
  render(<OutfitShop ownerId="owner" />);
  await waitFor(() => expect(JSON.parse(localStorage.getItem('muselly-shopping-feedback:owner')).choices[101]).toBe('like'));
  cleanup(); apiRequest.mockImplementation(prior);
  await search();
  expect(screen.getByRole('button', { name: 'Liked' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Not for me' }));
  expect(screen.queryByRole('article', { name: product.name })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
  expect(screen.getByRole('article', { name: product.name })).toBeTruthy();
});

it('sends a follow-up using the returned conversation context', async () => {
  await search();
  fireEvent.change(screen.getByLabelText('What should I change?'), { target: { value: 'less formal' } });
  fireEvent.click(screen.getByRole('button', { name: 'Update' }));
  await waitFor(() => expect(apiRequest.mock.calls.filter(([path]) => path.endsWith('/agent'))).toHaveLength(2));
  expect(apiRequest.mock.calls.filter(([path]) => path.endsWith('/agent'))[1][1].body).toEqual({
    message: 'less formal', offset: 0, session_id: 'session-1', revision: 1,
  });
});
