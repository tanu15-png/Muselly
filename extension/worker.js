import { WEB_ORIGIN } from './config.js';
import { extractProducts } from './extract.js';
import { selectSnapshotRegion } from './snapshot.js';

// Invoke an actual action handler so activeTab is granted before opening the
// persistent side panel. Merely focusing an already-open panel is not a grant.
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => {});
chrome.action.onClicked.addListener(tab => {
  chrome.sidePanel.open({ windowId: tab.windowId }).catch(() => {});
});
chrome.storage.local.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' }).catch(() => {});
chrome.storage.session.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' }).catch(() => {});

async function api(path, body, method = body ? 'POST' : 'GET') {
  const { connection } = await chrome.storage.session.get('connection');
  if (!connection || connection.expiresAt * 1000 < Date.now() + 10000) throw new Error('Connect your Muselly account again to continue.');
  const response = await fetch(WEB_ORIGIN + path, { method, cache: 'no-store', signal: AbortSignal.timeout(path.startsWith('/api/onboarding/enrichment') ? 70000 : 30000),
    headers: { Authorization: `Bearer ${connection.token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}) });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) await chrome.storage.session.remove('connection');
    throw new Error(typeof data?.detail === 'string' ? data.detail : 'Muselly could not complete this request.');
  }
  return data;
}

async function activeTab(shopping = false) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error('Open a shopping website in the active tab first.');
  if (!tab.url) throw new Error('Choose your retailer under Store access and click Allow this store, or click the Muselly toolbar icon on the shopping tab. Then retry.');
  if (!/^https?:\/\//.test(tab.url)) throw new Error('Open a shopping website in the active tab first.');
  if (shopping && new URL(tab.url).origin === WEB_ORIGIN) throw new Error('You are on Muselly. Open a retailer search, such as Myntra, keep that shopping tab active, then find your favorites there.');
  return tab;
}

async function handle(message) {
  switch (message.type) {
    case 'CONNECT': {
      const bytes = crypto.getRandomValues(new Uint8Array(32));
      const nonce = [...bytes].map(v => v.toString(16).padStart(2,'0')).join('');
      await chrome.storage.session.set({ pairing: { nonce, expires: Date.now() + 5 * 60 * 1000 } });
      await chrome.tabs.create({ url: `${WEB_ORIGIN}/extension/connect?extension_id=${chrome.runtime.id}&nonce=${nonce}` });
      return { connecting: true };
    }
    case 'STATUS': {
      const { connection } = await chrome.storage.session.get('connection');
      return { connected: Boolean(connection && connection.expiresAt * 1000 > Date.now() + 10000), user: connection?.user, website: WEB_ORIGIN };
    }
    case 'DISCONNECT':
      await chrome.storage.session.clear(); await chrome.storage.local.remove(['workspace']); return { disconnected: true };
    case 'PROFILE': return api('/api/extension/profile');
    case 'SEARCH': return api('/api/extension/search', { query: String(message.query || '').slice(0,300), explore: Boolean(message.explore) });
    case 'REFRESH_BRANDS': return api('/api/onboarding/enrichment?force=true', {});
    case 'CLEAR_FEEDBACK': return api('/api/extension/feedback', null, 'DELETE');
    case 'FEEDBACK': {
      await api('/api/extension/feedback', {item: message.item, kind: message.kind});
      const { ranking, connection } = await chrome.storage.session.get(['ranking', 'connection']);
      if (!ranking || ranking.owner !== connection?.user.id) return {saved:true};
      try { return await api('/api/extension/rank', ranking.body); }
      catch (error) { return {saved:true, note:'Your correction was saved. Rank the page again to update results. ' + error.message}; }
    }
    case 'RANK': {
      const tab = await activeTab(true);
      let extracted;
      try {
        const [frame] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: extractProducts });
        extracted = frame.result;
      } catch { throw new Error('Open Store access, choose this retailer and click Allow this store, then retry. You can also click the Muselly toolbar icon on this shopping tab.'); }
      if (!extracted?.supported || !extracted.items.length) throw new Error(extracted?.message || 'No products could be read on this page.');
      const body = { query: String(message.query || '').slice(0,300), items: extracted.items, sort: 'personalized' };
      const data = await api('/api/extension/rank', body);
      const { connection } = await chrome.storage.session.get('connection');
      await chrome.storage.session.set({ranking:{owner:connection.user.id, body}});
      return { ...data, page: extracted.page, message: extracted.message };
    }
    case 'SNAPSHOT': {
      const tab = await activeTab();
      let selection;
      try {
        if (message.select) {
          const [frame] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: selectSnapshotRegion });
          selection = frame.result;
          if (!selection) return { cancelled: true };
          if ((await activeTab()).id !== tab.id) throw new Error('The active tab changed.');
        }
        const image = await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' });
        return { image, selection, page: tab.url, capturedAt: new Date().toISOString() };
      } catch {
        throw new Error('Click the Muselly toolbar icon on the shopping tab, then take a snapshot again. Keep that tab active while selecting.');
      }
    }
    case 'SAVE_PRODUCT': return api('/api/extension/saved', { title: message.item.title, url: message.item.url, image: message.item.image || '' });
    case 'SAVED': return api('/api/extension/saved');
    case 'SAVE_SNAPSHOT': {
      if (typeof message.image !== 'string' || !/^data:image\/(png|jpeg|webp);base64,/.test(message.image) || message.image.length > 14000000) throw new Error('Choose a snapshot under 10 MB.');
      const { connection } = await chrome.storage.session.get('connection');
      if (!connection || connection.expiresAt * 1000 <= Date.now()) throw new Error('Connect Muselly again before saving.');
      const blob = await (await fetch(message.image)).blob();
      const response = await fetch(`${WEB_ORIGIN}/api/onboarding/images/${crypto.randomUUID()}`, {
        method: 'PUT', signal: AbortSignal.timeout(70000), headers: { Authorization: `Bearer ${connection.token}`, 'Content-Type': blob.type,
          'X-Filename': encodeURIComponent(`Muselly snapshot ${new Date().toISOString().slice(0,10)}.${blob.type === 'image/jpeg' ? 'jpg' : blob.type === 'image/webp' ? 'webp' : 'png'}`) }, body: blob });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Snapshot could not be saved.');
      return data;
    }
    default: throw new Error('Unknown extension action.');
  }
}

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  // Retailer pages/content scripts cannot invoke privileged worker operations.
  if (sender.id !== chrome.runtime.id || !sender.url?.startsWith(chrome.runtime.getURL(''))) return false;
  handle(message).then(data => respond({ ok: true, data })).catch(error => respond({ ok: false, error: error.message || 'Action failed.' }));
  return true;
});

chrome.runtime.onMessageExternal.addListener((message, sender, respond) => {
  if (message?.type !== 'MUSELLY_CONNECT') return false;
  (async () => {
    if (new URL(sender.url || '').origin !== WEB_ORIGIN || sender.frameId !== 0) throw new Error('Untrusted connection page.');
    const { pairing } = await chrome.storage.session.get('pairing');
    if (!pairing || pairing.expires < Date.now() || message.nonce !== pairing.nonce) throw new Error('Connection request expired. Start Connect again in the extension.');
    if (typeof message.accessToken !== 'string' || message.accessToken.length > 10000 || !Number.isFinite(message.expiresAt) || message.expiresAt * 1000 <= Date.now()) throw new Error('Sign in to Muselly again.');
    const response = await fetch(WEB_ORIGIN + '/api/auth/me', { signal: AbortSignal.timeout(15000), headers: { Authorization: `Bearer ${message.accessToken}` } });
    if (!response.ok) throw new Error('Muselly could not verify this account.');
    const user = await response.json();
    if (!user.id || !user.email) throw new Error('Invalid account response.');
    await chrome.storage.session.remove('pairing');
    const { connection: previous } = await chrome.storage.session.get('connection');
    const { workspace } = await chrome.storage.local.get('workspace');
    if ((previous?.user.id || workspace?.owner) !== user.id) await chrome.storage.local.remove('workspace');
    await chrome.storage.session.set({ connection: { token: message.accessToken, expiresAt: message.expiresAt, user } });
    return { connected: true };
  })().then(data => respond({ ok: true, data })).catch(error => respond({ ok: false, error: error.message }));
  return true;
});
