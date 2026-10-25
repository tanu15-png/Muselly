import { WEB_ORIGIN } from './config.js';
const $ = id => document.getElementById(id);
for (const [id,path] of [['home','/'],['profile','/dashboard'],['brands','/explore']]) $(id).href = WEB_ORIGIN + path;
let busy = false, snapshotImage = null, originalImage = null, drag = null, userId = null;
const canvas = $('snapshot'), context = canvas.getContext('2d');
const inspirationPlaceholder = $('inspiration-preview').firstElementChild.cloneNode(true);

async function call(type, payload = {}) {
  const owner = userId;
  let timer;
  const response = await Promise.race([
    chrome.runtime.sendMessage({ type, ...payload }),
    new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Muselly took too long to respond. Check your connection, then retry.')), 90000); }),
  ]).finally(() => clearTimeout(timer));
  if (type !== 'STATUS' && type !== 'DISCONNECT' && owner !== userId) throw new Error('Your account changed. Please retry this action.');
  if (!response?.ok) throw new Error(response?.error || 'Muselly did not respond. Try reopening the side panel.');
  return response.data;
}
async function action(label, task) {
  if (busy) return;
  busy = true; $('status').textContent = label; $('error').hidden = true;
  document.querySelectorAll('button, input, textarea, select').forEach(control => control.disabled = true);
  try { await task(); }
  catch (error) { $('error').textContent = error.message; $('error').hidden = false; $('error').scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
  finally { busy = false; $('status').textContent = ''; document.querySelectorAll('button, input, textarea, select').forEach(control => control.disabled = false); }
}
async function persist(patch = {}) {
  if (!userId) return;
  const owner = userId;
  const { workspace = {} } = await chrome.storage.local.get('workspace');
  if (owner !== userId) return;
  await chrome.storage.local.set({ workspace: { ...(workspace.owner === owner ? workspace : {}), ...patch, owner, query: $('query').value, sort: 'personalized' } });
}
async function connection() {
  const state = await call('STATUS');
  const nextOwner = state.connected ? state.user.id : null;
  if (userId && userId !== nextOwner) {
    $('results').replaceChildren(); $('stores').replaceChildren(); $('saved').replaceChildren(); $('query').value = '';
    $('result-summary').textContent = ''; $('snapshot-area').hidden = true; 
    snapshotImage = null; originalImage = null; canvas.width = 0; canvas.height = 0;
    $('inspiration-preview').replaceChildren(inspirationPlaceholder.cloneNode(true));
    $('inspiration-copy').textContent = 'A look you love. A little spark of you.';
  }
  userId = nextOwner;
  $('account').textContent = state.connected ? `Connected as ${state.user.email}` : 'Connect your signed-in Muselly profile to personalize shopping.';
  $('connect').textContent = state.connected ? 'Reconnect / refresh profile' : 'Connect Muselly';
  $('disconnect').hidden = !state.connected;
  document.querySelector('.account-settings').open = !state.connected;
  if (state.connected) {
    const { workspace } = await chrome.storage.local.get('workspace');
    if (workspace?.owner === userId) {
      $('query').value = workspace.query || ''; 
      if (workspace.results && workspace.resultsQuery === workspace.query) renderResults(workspace.results, true);
      if (workspace.links) renderLinks(workspace.links, true);

    }
  }
}
function link(href, text) {
  const a = document.createElement('a'); a.href = href; a.textContent = text; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a;
}
function renderLinks(data, restored = false) {
  $('stores').replaceChildren();
  const discoveries = document.createElement('div');
  for (const brand of data.discoveries || []) {
    const section = document.createElement('section'), title = document.createElement('h3'), copy = document.createElement('p');
    title.textContent = brand.name;
    copy.className = 'note'; copy.textContent = (brand.based_on?.length ? 'Qloo discovery using saved interests: ' + brand.based_on.join(', ') + '. ' : 'Discovered through Qloo from your saved interests. ') + brand.note;
    section.append(title, copy);
    if (brand.links.length) {
      const chooser = document.createElement('select'); chooser.setAttribute('aria-label', 'Retailer for ' + brand.name);
      for (const store of brand.links) { const option = document.createElement('option'); option.value = store.url; option.textContent = store.name; chooser.append(option); }
      const visit = link(brand.links[0].url, 'Search ' + brand.links[0].name);
      chooser.onchange = () => { visit.href = chooser.value; visit.textContent = 'Search ' + chooser.selectedOptions[0].textContent; };
      section.append(chooser, visit);
    }
    discoveries.append(section);
  }
  $('stores').prepend(discoveries);
  const retailers = document.createElement('details'), heading = document.createElement('summary');
  heading.textContent = 'Browse all retailers'; retailers.open = !data.discoveries?.length;
  retailers.append(heading, ...data.links.map(store => link(store.url, store.name))); $('stores').append(retailers);
  $('brand-status').textContent = data.discoveries?.length ? (data.explore ? 'More Qloo discoveries beyond your first shortlist.' : 'Your Qloo discoveries: start with a brand below.') : 'No current Qloo discoveries for this selection. Update discoveries, or browse retailers below.';
  if (restored) $('brand-status').textContent = 'Saved discoveries. Search again to use your current taste and Qloo brands.';
  const note = document.createElement('p'); note.className = 'note'; note.textContent = data.note; $('stores').append(note);
  const query = document.createElement('p'); query.className = 'note'; query.textContent = `Store search: ${data.query}`; $('stores').prepend(query);
}
function productCard(item, saved = false) {
  const article = document.createElement('article'); article.className = 'product';
  if (item.image) { const img = document.createElement('img'); img.src = item.image; img.alt = item.title; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer'; img.onerror = () => { const fallback = document.createElement('p'); fallback.className = 'note'; fallback.textContent = 'Image unavailable. Open the product at the store to view it.'; img.replaceWith(fallback); }; article.append(img); }
  const title = document.createElement('h3'); title.textContent = item.title; article.append(title);
  if (item.price) {
    const price = document.createElement('p'); price.className = 'price'; price.textContent = `${item.price.estimated ? 'Approx. ' : ''}${new Intl.NumberFormat('en-IN',{style:'currency',currency:item.price.currency}).format(Number(item.price.amount))}`; article.append(price);
    if (item.price.estimated) { const original = document.createElement('p'); original.textContent = `${item.original_price.amount} ${item.original_price.currency} at the store`; article.append(original); }
  }
  if (item.why) {
    const details = document.createElement('details'), summary = document.createElement('summary'), list = document.createElement('ul'); summary.textContent = 'Why it matches';
    item.why.forEach(why => { const li = document.createElement('li'); li.textContent = why; list.append(li); }); details.append(summary,list); article.append(details);
    const stock = document.createElement('span'); stock.className = 'badge'; stock.textContent = 'Listed price only · confirm size and stock at store'; article.append(stock);
  }
  article.append(link(item.url, 'View at store ↗'));
  if (!saved) { const save = document.createElement('button'); save.textContent = 'Save to Muselly'; save.className = 'quiet'; save.onclick = () => action('Saving to your Muselly account…', async () => { await call('SAVE_PRODUCT',{item}); save.textContent = 'Saved to Muselly'; }); article.append(save); }
  if (!saved && item.feedback_item) {
    const controls = document.createElement('div'); controls.className = 'corrections';
    for (const [kind, label] of [['more_like_this','More like this'],['not_my_style','Not my style'],['too_expensive','Too expensive'],['wrong_shape','Wrong shape'],['wrong_color','Wrong color']]) {
      const button = document.createElement('button'); button.className = 'secondary'; button.textContent = label;
      button.onclick = () => action('Helping your shortlist get closer…', async () => {
        const data = await call('FEEDBACK', {kind, item:item.feedback_item});
        if (data.products) { renderResults(data); await persist({results:data, resultsQuery:$('query').value}); }
        else $('result-summary').textContent = data.note || 'Correction saved. Find your favorites again to update your shortlist.';
        $('brand-status').textContent = kind === 'more_like_this' ? 'Preference saved. Update Qloo discoveries to include brands from products you like.' : 'Correction saved for future shopping. Reset corrections any time.';
      }); controls.append(button);
    }
    article.append(controls);
  }
  return article;
}
function renderResults(data, restored = false) {
  $('results').replaceChildren(...data.products.map(item => productCard(item)));
  $('result-summary').textContent = `${data.products.length} matches from ${data.scanned} loaded products. ${data.unknown_prices ? `${data.unknown_prices} cards had no readable price. ` : ''}${restored ? 'Saved results. Rank again to update prices and matches. ' : ''}${data.scope}${data.exchange ? ` Currency estimates: ${data.exchange.source}, ${data.exchange.date}.` : ''}`;
  if (!restored) $('brand-status').textContent = data.qloo_matched ? `${data.qloo_matched} products from your Qloo discovery brands in this shortlist.` : 'No current Qloo brand matches on this page. Discover brands above to broaden your search.';
  if (!data.products.length) {
    const empty = document.createElement('p');
    const reasons = Object.keys(data.excluded || {}).map(reason => ({category:'product type',garment:'garment type',fit:'fit',details:'cut, pattern or material',variant_or_preferences:'color, size, budget or saved preferences',keywords:'search keywords',feedback:'your saved corrections'}[reason] || reason));
    empty.textContent = `Read ${data.scanned} products, but none have the requested details in their page text.${reasons.length ? ` Filtered by: ${reasons.join('; ')}.` : ''} Try a more specific store search or scroll the store to load more products.`;
    $('results').append(empty);
  }
}
async function imageToCanvas(source, selection) {
  const image = new Image(); image.src = source; await image.decode();
  // Bound storage and request sizes while keeping garment details readable.
  const sx = selection ? selection.x * image.width / selection.viewportWidth : 0;
  const sy = selection ? selection.y * image.height / selection.viewportHeight : 0;
  const width = selection ? selection.width * image.width / selection.viewportWidth : image.width;
  const height = selection ? selection.height * image.height / selection.viewportHeight : image.height;
  const scale = Math.min(1, 1600 / Math.max(width, height));
  canvas.width = Math.max(1, Math.round(width * scale)); canvas.height = Math.max(1, Math.round(height * scale));
  context.drawImage(image,sx,sy,width,height,0,0,canvas.width,canvas.height);
  snapshotImage = canvas.toDataURL('image/png'); $('snapshot-area').hidden = false;
  const thumbnail = new Image(); thumbnail.src = snapshotImage; thumbnail.alt = '';
  $('inspiration-preview').replaceChildren(thumbnail);
  $('inspiration-copy').textContent = 'Ready to save to your inspiration library.';
  $('crop-selection').hidden = true;
}
async function captureSnapshot() {
  $('status').textContent = 'Drag around a look on the shopping page. Press Esc to cancel.';
  const result = await call('SNAPSHOT', { select: true });
  if (result.cancelled) return false;
  await imageToCanvas(result.image, result.selection);
  originalImage = snapshotImage;
  
  await persist();
  return true;
}
$('capture').onclick = () => action('Drag around a look on the shopping page. Press Esc to cancel.', captureSnapshot);
$('upload').onchange = () => action('Opening image…', async () => {
  const file = $('upload').files[0]; if (!file) return;
  if (!['image/png','image/jpeg','image/webp'].includes(file.type) || file.size > 10*1024*1024) throw new Error('Choose a PNG, JPG, or WebP under 10 MB.');
  const reader = new FileReader(); originalImage = await new Promise((resolve,reject) => { reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file); });
  await imageToCanvas(originalImage);
  
  $('upload').value = '';
  await persist();
});
function canvasPoint(event) {
  const rect = canvas.getBoundingClientRect();
  return { x: Math.max(0, Math.min(canvas.width, (event.clientX-rect.left)*canvas.width/rect.width)), y: Math.max(0, Math.min(canvas.height, (event.clientY-rect.top)*canvas.height/rect.height)) };
}
function cancelCrop() { drag = null; $('crop-selection').hidden = true; }
canvas.onpointerdown = event => {
  if (busy || event.button !== 0) return;
  event.preventDefault(); drag = canvasPoint(event); canvas.setPointerCapture(event.pointerId);
};
canvas.onpointermove = event => {
  if (!drag) return;
  const end = canvasPoint(event), box = $('crop-selection'); box.hidden = false;
  Object.assign(box.style, { left: `${Math.min(drag.x,end.x)/canvas.width*100}%`, top: `${Math.min(drag.y,end.y)/canvas.height*100}%`, width: `${Math.abs(end.x-drag.x)/canvas.width*100}%`, height: `${Math.abs(end.y-drag.y)/canvas.height*100}%` });
};
canvas.onpointerup = event => {
  if (!drag || busy) return;
  const {x,y} = canvasPoint(event);
  const sx = Math.min(drag.x,x), sy = Math.min(drag.y,y), width = Math.abs(x-drag.x), height = Math.abs(y-drag.y); cancelCrop();
  if (width < 12 || height < 12) return;
  const crop = document.createElement('canvas'); crop.width = Math.round(width); crop.height = Math.round(height); crop.getContext('2d').drawImage(canvas,sx,sy,width,height,0,0,width,height);
  action('Cropping your inspiration…', () => imageToCanvas(crop.toDataURL('image/png')));
};
canvas.onpointercancel = cancelCrop;
canvas.onlostpointercapture = cancelCrop;
canvas.onkeydown = event => { if (event.key === 'Escape') cancelCrop(); };
$('reset-crop').onclick = () => action('Resetting crop…', () => imageToCanvas(originalImage));
$('save-snapshot').onclick = () => action('Saving your private inspiration…', async () => {
  if (!snapshotImage && !await captureSnapshot()) return;
  await call('SAVE_SNAPSHOT',{image:snapshotImage});
  $('snapshot-status').textContent = 'Saved to your Muselly inspiration library. You can update Style DNA on your dashboard.';
  $('snapshot-area').hidden = true;
});
$('connect').onclick = () => action('Opening Muselly to connect securely…', () => call('CONNECT'));
$('disconnect').onclick = () => action('Disconnecting…', async () => { await call('DISCONNECT'); await connection(); });
$('search-form').onsubmit = event => { event.preventDefault(); action('Preparing store searches…', async () => {
  const links = await call('SEARCH',{query:$('query').value}); renderLinks(links);
  $('results').replaceChildren(); $('result-summary').textContent = '';
  await persist({links, results:null});
}); };
$('allow-store').onclick = () => action('Requesting access to your selected store…', async () => {
  // Call directly from this click, before any await, to preserve the user gesture.
  const granted = await chrome.permissions.request({origins: [$('access-store').value]});
  if (!granted) throw new Error('Store access was not allowed. You can retry Allow this store or use the toolbar icon on the retailer tab.');
  $('access-status').textContent = 'Access allowed. Open this retailer in the active tab, then click Find my favorites on this page.';
});
$('rank').onclick = () => action('Reading loaded products and matching your taste…', async () => {
  if ($('query').value.trim().length < 2) throw new Error('Write a product prompt first, such as midi dress under 2000.');
  const data = await call('RANK',{query:$('query').value,sort:'personalized'});
  renderResults(data); $('shopping-tools').open = true;
  $('result-summary').scrollIntoView({ block: 'start', behavior: 'smooth' });
  await persist({results:data, resultsQuery:$('query').value});
});
$('load-saved').onclick = () => action('Loading your saved products…', async () => { const data = await call('SAVED'); $('saved').replaceChildren(...data.items.map(item => productCard(item,true))); if (!data.items.length) $('saved').textContent = 'No saved products yet.'; });
$('query').oninput = () => { $('results').replaceChildren(); $('result-summary').textContent = ''; };
$('query').onchange = () => persist({results:null}).catch(() => {});
$('explore').onclick = () => action('Exploring more Qloo brand discoveries…', async () => {
  if ($('query').value.trim().length < 2) throw new Error('Tell us what you are shopping for first.');
  const data = await call('SEARCH',{query:$('query').value, explore:true}); renderLinks(data); await persist({links:data});
});
$('refresh-brands').onclick = () => action('Updating your Qloo discoveries…', async () => {
  const data = await call('REFRESH_BRANDS');
  $('stores').replaceChildren(); $('results').replaceChildren(); $('result-summary').textContent = '';
  await persist({links:null, results:null});
  $('brand-status').textContent = data.stale ? 'Your taste changed during enrichment. Update again for current discoveries.' : `${data.result?.affinities?.length || 0} Qloo brand discoveries ready. Search to explore them.`;
});
$('clear-feedback').onclick = () => action('Resetting your corrections…', async () => {
  await call('CLEAR_FEEDBACK'); $('results').replaceChildren(); $('result-summary').textContent = 'Corrections cleared. Find your favorites again to rebuild your shortlist.';
  await persist({results:null});
});
chrome.storage.onChanged.addListener((changes,area) => { if (area === 'session' && changes.connection) connection().catch(() => {}); });
connection().catch(error => { $('error').textContent = error.message; $('error').hidden = false; });
