import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import ProductSearch from './ProductSearch';
import { apiRequest } from '../lib/supabase';
import { clearCache } from '../lib/sessionCache';

vi.mock('../lib/supabase', () => ({ apiRequest: vi.fn() }));
const sources = { sources: [{ id:'avia', name:'AVIA', mode:'catalog', qloo_affinity:true },{ id:'myntra',name:'Myntra',mode:'website' }], default_source_ids:['avia','myntra'] };
let result;
beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  vi.resetAllMocks();
  result = { products:[{ id:'avia:1',title:'Cream Midi Dress',source_name:'AVIA',url:'https://avia.com/products/dress?variant=1',image:'https://cdn.shopify.com/dress.jpg',
    price:{amount:'4500',currency:'INR',estimated:true},original_price:{amount:'50',currency:'USD'},selected_options:{size:'M',color:'Cream'},
    why:['Matches your saved neutral palette.'],match_label:'Matches your taste' }],
    applied_filters:{ category:'dresses',color:'cream',size:'M',max_price:'5000',currency:'INR',sort:'personalized' },
    source_statuses:[{ id:'avia',name:'AVIA',status:'ok' }],retailer_links:[{ id:'myntra',name:'Myntra',url:'https://www.myntra.com/cream-dress' }],
    status:'ok',exchange:{source:'ECB',date:'2026-10-16'},searched_at:'2026-10-18T12:00:00Z' };
  apiRequest.mockImplementation(async (path) => path.endsWith('/sources') ? sources : result);
});
afterEach(() => { cleanup(); vi.useRealTimers(); window.history.replaceState({}, '', '/'); });
async function open() { render(<ProductSearch />); await screen.findByRole('checkbox',{name:/AVIA/}); }
async function search() {
  fireEvent.change(screen.getByLabelText('What are you looking for?'),{target:{value:'A cream dress under ₹5,000 size M'}});
  await act(async () => { fireEvent.click(screen.getByRole('button',{name:'Find products'})); });
}

it('loads source choices without automatically searching or making AI requests', async () => {
  await open();
  expect(apiRequest.mock.calls).toHaveLength(1);
  expect(apiRequest.mock.calls[0][0]).toBe('/api/search/sources');
  expect(screen.queryByRole('article')).toBeNull();
});

it('restores the query, source choices and recent products when returning to discovery', async () => {
  result.searched_at = new Date().toISOString();
  const first = render(<ProductSearch ownerId="owner" />);
  await screen.findByRole('checkbox', { name: /AVIA/ });
  await search();
  first.unmount(); apiRequest.mockClear();
  render(<ProductSearch ownerId="owner" />);
  expect(screen.getByRole('heading', { name: 'Cream Midi Dress' })).toBeTruthy();
  expect(screen.getByLabelText('What are you looking for?').value).toBe('A cream dress under ₹5,000 size M');
  expect(apiRequest).not.toHaveBeenCalled();
});

it.each([false, true])('keeps the last search across a new browser session and a day away (empty: %s)', async empty => {
  if (empty) result.products = [];
  const first = render(<ProductSearch ownerId="owner" />);
  await screen.findByRole('checkbox', { name: /AVIA/ });
  await search();
  first.unmount(); sessionStorage.clear(); apiRequest.mockClear();
  vi.useFakeTimers(); vi.setSystemTime(Date.now() + 24 * 60 * 60 * 1000);
  render(<ProductSearch ownerId="owner" />);
  expect(screen.getByLabelText('What are you looking for?').value).toBe('A cream dress under ₹5,000 size M');
  expect(screen.getByText(/Saved search from/)).toBeTruthy();
  expect(screen.getByRole('heading', { name: empty ? 'No products matched these filters.' : 'Cream Midi Dress' })).toBeTruthy();
  await act(async () => {});
  expect(apiRequest.mock.calls.some(([path]) => path === '/api/search/products')).toBe(false);
});

it('keeps saved search results when preference caches are invalidated and isolates accounts', async () => {
  const first = render(<ProductSearch ownerId="owner" />);
  await screen.findByRole('checkbox', { name: /AVIA/ });
  await search(); first.unmount(); clearCache('owner');
  const second = render(<ProductSearch ownerId="owner" />);
  expect(screen.getByRole('heading', { name: 'Cream Midi Dress' })).toBeTruthy();
  expect(screen.getByText(/update prices, availability, and taste matches/)).toBeTruthy();
  await act(async () => {}); second.unmount();
  render(<ProductSearch ownerId="other-owner" />);
  expect(screen.queryByRole('article')).toBeNull();
  expect(screen.getByLabelText('What are you looking for?').value).toBe('');
  await act(async () => {});
});

it('synchronizes an edited search with the URL and restores it on browser return', async () => {
  window.history.replaceState({}, '', '/explore?q=old+request');
  const first = render(<ProductSearch ownerId="owner" initialQuery="old request" />);
  await screen.findByRole('checkbox', { name: /AVIA/ }); await search();
  const query = new URLSearchParams(window.location.search).get('q');
  expect(query).toBe('A cream dress under ₹5,000 size M');
  first.unmount();
  render(<ProductSearch ownerId="owner" initialQuery={query} />);
  expect(screen.getByRole('heading', { name: 'Cream Midi Dress' })).toBeTruthy();
});

it('starts a different explicit home query without showing products from the previous query', async () => {
  const first = render(<ProductSearch ownerId="owner" />);
  await screen.findByRole('checkbox', { name: /AVIA/ }); await search(); first.unmount();
  const second = render(<ProductSearch ownerId="owner" initialQuery="running shoes" />);
  expect(screen.queryByRole('article')).toBeNull();
  expect(screen.getByLabelText('What are you looking for?').value).toBe('running shoes');
  second.unmount();
  render(<ProductSearch ownerId="owner" />);
  expect(screen.getByRole('heading', { name: 'Cream Midi Dress' })).toBeTruthy();
});

it('retrieves real products on explicit search and renders prices, explanations, and store links', async () => {
  await open(); await search();
  expect(apiRequest).toHaveBeenCalledWith('/api/search/products',expect.objectContaining({method:'POST',body:expect.objectContaining({query:'A cream dress under ₹5,000 size M',source_ids:['avia','myntra']})}));
  expect(screen.getByRole('heading',{name:'Cream Midi Dress'})).toBeTruthy();
  const card=screen.getByRole('article');
  expect(within(card).getByText(/Approx./).textContent).toMatch(/4,500/);
  expect(within(card).getByText(/at the store/).textContent).toContain('$50.00');
  expect(within(card).getByText('Matches your saved neutral palette.')).toBeTruthy();
  const link=screen.getByRole('link',{name:'View on AVIA'});
  expect(link.href).toBe('https://avia.com/products/dress?variant=1');
  expect(link.target).toBe('_blank'); expect(link.rel).toContain('noopener');
  expect(screen.getByRole('link',{name:'Search Myntra'}).href).toBe('https://www.myntra.com/cream-dress');
  expect(screen.getByText(/ECB rates dated/)).toBeTruthy();
});

it('sends editable filters and excludes deselected sources', async () => {
  await open();
  fireEvent.click(screen.getByText('Refine your search'));
  fireEvent.change(screen.getByLabelText('Maximum price'),{target:{value:'3000'}});
  fireEvent.change(screen.getByLabelText('Size, as listed by the store'),{target:{value:'S'}});
  fireEvent.change(screen.getByLabelText('Currency'),{target:{value:'USD'}});
  fireEvent.change(screen.getByLabelText('Ranking'),{target:{value:'relevance'}});
  fireEvent.click(screen.getByRole('checkbox',{name:/AVIA/}));
  await search();
  expect(apiRequest).toHaveBeenLastCalledWith('/api/search/products',expect.objectContaining({body:expect.objectContaining({source_ids:['myntra'],max_price:'3000',size:'S',currency:'USD',sort:'relevance'})}));
});

it('keeps results from healthy stores when another source fails', async () => {
  await open(); result.status='partial'; result.source_statuses.push({id:'other',name:'Other store',status:'timeout'});
  await search();
  expect(screen.getByText(/Some stores couldn’t respond: Other store/)).toBeTruthy();
  expect(screen.getByRole('article')).toBeTruthy();
});

it('shows an honest empty state and external-only searches without fake cards', async () => {
  await open(); result.products=[]; result.status='external_only';
  await search();
  expect(screen.getByRole('heading',{name:'Continue your search on a retailer website.'})).toBeTruthy();
  expect(screen.queryByRole('article')).toBeNull();
  expect(screen.getByRole('link',{name:'Search Myntra'})).toBeTruthy();
});

it('shows provider failures without fabricating or replacing earlier results', async () => {
  await open(); await search();
  apiRequest.mockRejectedValueOnce({message:'Selected stores are unavailable.',status:503});
  await search();
  expect(screen.getByRole('alert').textContent).toContain('Selected stores are unavailable.');
  expect(screen.getByRole('article')).toBeTruthy();
});

it('requires a selected store and handles broken product images', async () => {
  await open(); fireEvent.click(screen.getByRole('checkbox',{name:/AVIA/}));
  fireEvent.click(screen.getByText('Search your retailer websites'));
  fireEvent.click(screen.getByRole('checkbox',{name:'Myntra'}));
  await search();
  expect(screen.getByRole('alert').textContent).toContain('Choose at least one store');
  expect(apiRequest.mock.calls).toHaveLength(1);
  fireEvent.click(screen.getByRole('checkbox',{name:/AVIA/})); await search();
  fireEvent.error(screen.getByRole('img',{name:'Cream Midi Dress'}));
  expect(screen.getByText('Image unavailable')).toBeTruthy();
});
