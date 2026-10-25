// @vitest-environment node
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';
import { beforeEach, expect, it, vi } from 'vitest';

let internal, external, chrome, fetchMock;
function storage() {
  const values = {};
  return { values, get: async key => Object.fromEntries([key].flat().map(k=>[k,values[k]])), set: async data => Object.assign(values,data),
    remove: async keys => { for (const key of [keys].flat()) delete values[key]; }, clear: async () => { for (const key of Object.keys(values)) delete values[key]; },
    setAccessLevel: async () => {} };
}
beforeEach(() => {
  fetchMock = vi.fn();
  chrome = {
    sidePanel: { setPanelBehavior: async () => {}, open: async () => {} }, action: { onClicked: { addListener: vi.fn() } }, storage: { session: storage(), local: storage() },
    runtime: { id:'self', getURL: path => 'chrome-extension://self/' + path,
      onMessage: { addListener: fn => { internal = fn; } }, onMessageExternal: { addListener: fn => { external = fn; } } },
    tabs: { create:vi.fn(async () => ({})), query:async () => [{id:1,windowId:1,url:'https://www.myntra.com/dresses'}], captureVisibleTab:vi.fn(async () => 'data:image/png;base64,preview') },
    scripting:{executeScript:vi.fn(async () => [{result:{supported:true,items:[{title:'dress',url:'https://www.myntra.com/dress',price:'1000'}],page:'https://www.myntra.com/dresses',message:'Loaded products'}}])}
  };
  const source = readFileSync(new URL('../../../extension/worker.js',import.meta.url),'utf8').replace(/^import .*;\r?\n/gm,'');
  vm.runInNewContext(source, { chrome, fetch:fetchMock, WEB_ORIGIN:'http://localhost:5173', extractProducts:()=>{}, selectSnapshotRegion:()=>{}, crypto:webcrypto, URL, Date, Uint8Array, AbortSignal });
});
const send = message => new Promise(resolve => internal(message,{id:'self',url:'chrome-extension://self/panel.html'},resolve));
const pair = (message, sender={url:'http://localhost:5173/extension/connect',frameId:0}) => new Promise(resolve => external(message,sender,resolve));

it('does not allow a retailer content script to access privileged operations', () => {
  expect(internal({type:'STATUS'},{id:'self',url:'https://www.myntra.com/'},vi.fn())).toBe(false);
  expect(fetchMock).not.toHaveBeenCalled();
});

it('requires a live nonce, trusted origin and verified account before storing a session', async () => {
  await send({type:'CONNECT'});
  const nonce = chrome.storage.session.values.pairing.nonce;
  expect(chrome.tabs.create.mock.calls[0][0].url).toContain('extension_id=self&nonce=');
  const message={type:'MUSELLY_CONNECT',nonce,accessToken:'access-token',expiresAt:Date.now()/1000+3600};
  expect((await pair(message,{url:'https://evil.example/',frameId:0})).ok).toBe(false);
  expect((await pair({...message,nonce:'wrong'})).ok).toBe(false);
  fetchMock.mockResolvedValue({ok:true,json:async()=>({id:'owner',email:'owner@example.com'})});
  expect((await pair(message)).ok).toBe(true);
  expect(chrome.storage.session.values.connection.token).toBe('access-token');
  expect(chrome.storage.local.values.connection).toBeUndefined();
  expect((await pair(message)).ok).toBe(false); // Consumed nonce cannot be replayed.
});

it('ranks only extracted page data through the fixed Muselly backend', async () => {
  chrome.storage.session.values.connection={token:'secret',expiresAt:Date.now()/1000+3600,user:{id:'owner'}};
  fetchMock.mockResolvedValue({ok:true,json:async()=>({products:[],scanned:1})});
  expect((await send({type:'RANK',query:'dress under 2000'})).ok).toBe(true);
  expect(fetchMock.mock.calls[0][0]).toBe('http://localhost:5173/api/extension/rank');
  const request=fetchMock.mock.calls[0][1];
  expect(request.headers.Authorization).toBe('Bearer secret');
  expect(JSON.parse(request.body).items).toHaveLength(1);
});

it('captures only on explicit request and clears the workspace on disconnect', async () => {
  expect(chrome.tabs.captureVisibleTab).not.toHaveBeenCalled();
  expect((await send({type:'SNAPSHOT'})).data.image).toContain('data:image/png');
  chrome.storage.local.values.workspace={owner:'owner',query:'dress'};
  await send({type:'DISCONNECT'});
  expect(chrome.storage.local.values.workspace).toBeUndefined();
});

it('selects a page region before capture and preserves viewport coordinates for high DPI crops', async () => {
  const selection = { x:100, y:80, width:300, height:400, viewportWidth:1200, viewportHeight:900 };
  chrome.scripting.executeScript.mockResolvedValue([{result:selection}]);
  const response = await send({type:'SNAPSHOT',select:true});
  expect(response.data.selection).toEqual(selection);
  expect(chrome.tabs.captureVisibleTab).toHaveBeenCalledOnce();
  expect(chrome.scripting.executeScript.mock.invocationCallOrder[0]).toBeLessThan(chrome.tabs.captureVisibleTab.mock.invocationCallOrder[0]);
});

it('does not capture after a cancelled selection and explains missing tab permission', async () => {
  chrome.scripting.executeScript.mockResolvedValue([{result:null}]);
  expect((await send({type:'SNAPSHOT',select:true})).data.cancelled).toBe(true);
  expect(chrome.tabs.captureVisibleTab).not.toHaveBeenCalled();
  chrome.scripting.executeScript.mockRejectedValue(new Error('Cannot access tab'));
  expect((await send({type:'SNAPSHOT',select:true})).error).toContain('toolbar icon');
});


it('persists feedback and reranks the same owner candidates without reading the page again', async () => {
  chrome.storage.session.values.connection={token:'secret',expiresAt:Date.now()/1000+3600,user:{id:'owner'}};
  fetchMock.mockResolvedValue({ok:true,json:async()=>({products:[],scanned:1})});
  await send({type:'RANK',query:'dress'});
  const item={title:'dress',url:'https://www.myntra.com/dress',price:'1000'};
  expect((await send({type:'FEEDBACK',kind:'wrong_shape',item})).ok).toBe(true);
  expect(chrome.scripting.executeScript).toHaveBeenCalledOnce();
  expect(fetchMock.mock.calls[1][0]).toContain('/feedback');
  expect(fetchMock.mock.calls[2][0]).toContain('/rank');
});

it('does not expose image description as a worker action', async () => {
  expect((await send({type:'DESCRIBE',image:'anything'})).ok).toBe(false);
  expect(fetchMock).not.toHaveBeenCalled();
});


it('explains how to grant store access when Chrome hides the active tab URL', async () => {
  chrome.tabs.query=async()=>[{id:1,windowId:1}];
  const response=await send({type:'RANK',query:'dress'});
  expect(response.ok).toBe(false);
  expect(response.error).toContain('Allow this store');
  expect(chrome.scripting.executeScript).not.toHaveBeenCalled();
});

it('directs a shopper from the Muselly dashboard to a retailer instead of asking for toolbar permission', async () => {
  chrome.tabs.query=async()=>[{id:1,windowId:1,url:'http://localhost:5173/dashboard'}];
  const response=await send({type:'RANK',query:'dress'});
  expect(response.error).toContain('You are on Muselly');
  expect(chrome.scripting.executeScript).not.toHaveBeenCalled();
});
