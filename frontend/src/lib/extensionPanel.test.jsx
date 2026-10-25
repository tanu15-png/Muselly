import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
let chrome;
const $ = id => document.getElementById(id);
beforeEach(async () => {
  document.body.innerHTML = readFileSync(resolve(process.cwd(), '../extension/panel.html'), 'utf8');
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({});
  Element.prototype.scrollIntoView = vi.fn();
  chrome = {
    permissions: {request:vi.fn(async()=>true)},
    runtime: {sendMessage:vi.fn(async message => ({ok:true,data:message.type === 'STATUS' ? {connected:true,user:{id:'owner',email:'user@example.com'}} : {products:[],scanned:3,unknown_prices:0,excluded:{garment:3},scope:'Loaded products only.'}}))},
    storage: {local:{get:vi.fn(async()=>({})),set:vi.fn(async()=>{})},onChanged:{addListener:vi.fn()}},
  };
  const source = readFileSync(resolve(process.cwd(), '../extension/panel.js'), 'utf8').replace(/^import .*;\r?\n/gm,'');
  new Function('chrome','WEB_ORIGIN',source)(chrome,'http://localhost:5173');
  await waitFor(() => expect($('account').textContent).toContain('Connected as'));
});
afterEach(() => {vi.restoreAllMocks();document.body.innerHTML='';});
it('a rank click calls the worker, expands the results and scrolls to an explicit empty result', async () => {
  $('query').value = 'cream ruched blouse';
  $('rank').click();
  await waitFor(() => expect($('results').textContent).toContain('Read 3 products'));
  expect(chrome.runtime.sendMessage).toHaveBeenCalledWith(expect.objectContaining({type:'RANK',query:'cream ruched blouse'}));
  expect($('shopping-tools').open).toBe(true);
  expect($('result-summary').scrollIntoView).toHaveBeenCalled();
  expect($('results').textContent).toContain('garment type');
});
it('shows and scrolls to a permission error instead of silently doing nothing', async () => {
  $('query').value = 'blouse';
  chrome.runtime.sendMessage.mockResolvedValueOnce({ok:false,error:'Click the Muselly toolbar icon on this shopping tab.'});
  $('rank').click();
  await waitFor(() => expect($('error').hidden).toBe(false));
  expect($('error').textContent).toContain('toolbar icon');
  expect($('error').scrollIntoView).toHaveBeenCalled();
  expect($('rank').disabled).toBe(false);
});
it('explains an empty prompt immediately', async () => {
  $('rank').click();
  await waitFor(() => expect($('error').hidden).toBe(false));
  expect($('error').textContent).toContain('Write a product prompt first');
});
it('renders successful page matches and clears old results when a new store search is submitted', async () => {
  $('query').value = 'cream blouse';
  chrome.runtime.sendMessage.mockResolvedValueOnce({ok:true,data:{products:[{title:'Cream Wrap Blouse',url:'https://www.myntra.com/blouse',why:['Matches your search.']}],scanned:4,scope:'Loaded products only.'}});
  $('rank').click();
  await waitFor(() => expect($('results').textContent).toContain('Cream Wrap Blouse'));
  await waitFor(() => expect($('rank').disabled).toBe(false));
  chrome.runtime.sendMessage.mockResolvedValueOnce({ok:true,data:{links:[],query:'blue shirt',note:'Rank the loaded products.'}});
  $('query').value = 'blue shirt';
  $('search-form').dispatchEvent(new Event('submit',{cancelable:true}));
  await waitFor(() => expect($('results').textContent).toBe(''));
  expect($('stores').textContent).toContain('Store search: blue shirt');
});


it('offers persistent corrections and rerenders the refined shortlist', async () => {
  $('query').value = 'dress';
  const feedbackItem = {title:'Red dress',url:'https://www.myntra.com/red',price:'1500'};
  chrome.runtime.sendMessage.mockResolvedValueOnce({ok:true,data:{products:[{...feedbackItem,price:{amount:'1500',currency:'INR'},feedback_item:feedbackItem}],scanned:2,scope:'Loaded products only.'}});
  $('rank').click();
  await waitFor(() => expect($('results').textContent).toContain('Wrong color'));
  await waitFor(() => expect($('rank').disabled).toBe(false));
  chrome.runtime.sendMessage.mockResolvedValueOnce({ok:true,data:{products:[{title:'Blue dress',url:'https://www.myntra.com/blue'}],scanned:2,scope:'Loaded products only.'}});
  [...$('results').querySelectorAll('button')].find(button=>button.textContent==='Wrong color').click();
  await waitFor(() => expect($('results').textContent).toContain('Blue dress'));
  expect(chrome.runtime.sendMessage).toHaveBeenCalledWith({type:'FEEDBACK',kind:'wrong_color',item:feedbackItem});
});

it('keeps snapshots save-only and offers a single personalized shopping mode', () => {
  expect($('similar')).toBeNull();
  expect($('sort')).toBeNull();
  expect($('save-snapshot').textContent).toContain('Save inspiration');
  expect($('explore').textContent).toContain('beyond my usual style');
});

it('shows Qloo brand searches ahead of generic retailer links', async () => {
  $('query').value='dress';
  chrome.runtime.sendMessage.mockResolvedValueOnce({ok:true,data:{links:[{name:'Myntra',url:'https://www.myntra.com/dress'}],query:'dress',note:'Loaded products only',discoveries:[{name:'COS',note:'Stock is unverified.',links:[{name:'Myntra',url:'https://www.myntra.com/cos-dress'}]}]}});
  $('search-form').dispatchEvent(new Event('submit',{cancelable:true}));
  await waitFor(()=>expect($('stores').textContent).toContain('COS'));
  expect($('stores').querySelector('a').href).toContain('cos-dress');
  expect($('brand-status').textContent).toContain('Qloo discoveries');
});


it('requests access only to the selected retailer from the permission button', async () => {
  $('access-store').value='https://*.myntra.com/*';
  $('allow-store').click();
  expect(chrome.permissions.request).toHaveBeenCalledWith({origins:['https://*.myntra.com/*']});
  await waitFor(()=>expect($('access-status').textContent).toContain('Access allowed'));
});

it('handles a denied store permission without attempting to read products', async () => {
  chrome.permissions.request.mockResolvedValueOnce(false);
  $('allow-store').click();
  await waitFor(()=>expect($('error').textContent).toContain('Store access was not allowed'));
  expect(chrome.runtime.sendMessage).not.toHaveBeenCalledWith(expect.objectContaining({type:'RANK'}));
});
