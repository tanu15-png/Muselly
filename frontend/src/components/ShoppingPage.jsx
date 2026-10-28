import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Heart, Search, ThumbsDown } from 'lucide-react';
import { useAuth } from './AuthProvider';
import { Brand, Button, Eyebrow } from './ui';
import SignIn from './SignIn';
import ResilientImage from './ResilientImage';
import { apiRequest } from '../lib/supabase';
import { readAgentEvents } from '../lib/shoppingAgent';
import { shoppingFeedbackStore } from '../lib/shoppingFeedback';
import '../styles/dashboard.css';
import '../styles/shop.css';

const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value);
const store = shoppingFeedbackStore();

export function OutfitShop({ ownerId }) {
  const [query, setQuery] = useState(() => (new URLSearchParams(window.location.search).get('q') || '').slice(0, 280));
  const [correction, setCorrection] = useState('');
  const [progress, setProgress] = useState('');
  const [result, setResult] = useState(null);
  const [choices, setChoices] = useState({});
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(0);
  const [error, setError] = useState('');
  const [syncError, setSyncError] = useState('');
  const [syncAttempt, setSyncAttempt] = useState(0);
  const [likedOnly, setLikedOnly] = useState(false);
  const [last, setLast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const flight = useRef(null), active = useRef(true), requests = useRef(new Set()), lock = useRef(false), initialized = useRef(false);
  function apply(state) { if (active.current) { setChoices(state.choices); setPending(Object.keys(state.pending).length); } }
  async function api(path, options = {}) {
    const controller = new AbortController(); requests.current.add(controller);
    try {
      const { onProgress, ...rest } = options;
      const response = await apiRequest(path, { ...rest, expectedOwner: ownerId, signal: controller.signal });
      return onProgress ? await readAgentEvents(response, onProgress) : response;
    }
    finally { requests.current.delete(controller); }
  }
  async function flush() {
    if (flight.current) return flight.current;
    flight.current = (async () => {
      let state = store.load(ownerId);
      while (Object.keys(state.pending).length) {
        if (!active.current) throw new Error('Saving paused.');
        const event = Object.values(state.pending)[0];
        await api('/api/shop/feedback', { method: 'POST', body: { product_id: event.product_id, choice: event.choice } });
        state = store.acknowledge(ownerId, event); apply(state);
      }
      if (active.current) setSyncError('');
    })().catch(failure => { if (active.current) { setSyncError('Saved on this device. Sync will retry.'); setSyncAttempt(value => value + 1); } throw failure; }).finally(() => { flight.current = null; });
    return flight.current;
  }
  useEffect(() => {
    active.current = true;
    initialized.current = false;
    (async () => {
      try {
        apply(store.load(ownerId));
        const server = await api('/api/shop/feedback');
        if (active.current) apply(store.merge(ownerId, server.choices));
      } catch (failure) { if (active.current) setSyncError('Couldn’t sync your choices. They remain on this device.'); }
      finally { if (active.current) { initialized.current = true; setReady(true); } }
    })();
    const online = () => { if (initialized.current) flush().catch(() => {}); };
    window.addEventListener('online', online);
    return () => { active.current = false; requests.current.forEach(controller => controller.abort()); window.removeEventListener('online', online); };
  }, [ownerId]);
  useEffect(() => {
    if (!ready || !pending) return;
    const timer = setTimeout(() => flush().catch(() => {}), syncError ? 5000 : 700);
    return () => clearTimeout(timer);
  }, [pending, choices, ready, syncError, syncAttempt]);
  async function find(text = query, offset = 0, liked = likedOnly, followup = false) {
    if (lock.current || !ready) return;
    lock.current = true; setBusy(true); setError(''); setProgress('Syncing your choices');
    try {
      await flush();
      const context = (followup || offset) ? result?.agent : null;
      const data = liked ? await api('/api/shop/search', { method: 'POST', body: { query: 'outfit', offset, limit: 24, liked_only: true } })
        : await api('/api/shop/agent', { method: 'POST', stream: true,
          body: { message: offset ? '' : text || 'outfit', offset,
            ...(context ? { session_id: context.session_id, revision: context.revision } : {}) },
          onProgress: message => { if (active.current) setProgress(message); } });
      if (active.current) { setResult(previous => offset ? { ...data, products: [...new Map([...previous.products, ...data.products].map(row => [row.product_id, row])).values()] } : data); setSearchQuery(text || 'outfit'); if (followup) setCorrection(''); }
    } catch (failure) { if (active.current) setError(failure.message || 'Couldn’t find outfits. Please retry.'); }
    finally { lock.current = false; if (active.current) { setBusy(false); setProgress(''); } }
  }
  function choose(id, choice) {
    try { const before = choices[id] || 'clear'; apply(store.choose(ownerId, id, choice)); setLast({ id, before, choice }); setError(''); }
    catch { setError('Enable browser storage to save choices. Your choice has not changed.'); }
  }
  const products = (result?.products || []).filter(row => choices[row.product_id] !== 'dislike' && (!likedOnly || choices[row.product_id] === 'like'))
    .sort((a, b) => (b.taste_match ?? -1) - (a.taste_match ?? -1));
  return <main id="main-content" className="container outfit-shop">
    <div className="shop-heading"><Eyebrow>Shop your Qloo taste</Eyebrow><h1>Find your next <em>favorite.</em></h1></div>
    <form className="outfit-request" onSubmit={event => { event.preventDefault(); setLikedOnly(false); find(query, 0, false); }}>
      <label htmlFor="outfit-query">What would you like to wear?</label><textarea id="outfit-query" value={query} maxLength={280} required minLength={2} onChange={event => setQuery(event.target.value)} placeholder="A dress for a Switzerland vacation under ₹3,000" rows={2} />
      <div className="shop-request-actions"><small>Women’s clothing · budget per item</small><Button disabled={busy || !ready || query.trim().length < 2} type="submit"><Search size={16} />{busy ? 'Finding your favorites…' : 'Find my outfit'}</Button></div>
    </form>
    <div className="shop-examples">{['Everyday office outfit under ₹2,000', 'A floral midi dress under ₹1,500'].map(example => <button type="button" key={example} disabled={busy || !ready} onClick={() => { setQuery(example); setLikedOnly(false); find(example, 0, false); }}>{example}</button>)}</div>
    <div className="shop-toolbar"><button type="button" className="culture-text-button" aria-pressed={likedOnly} disabled={busy || !ready} onClick={() => { const liked = !likedOnly; setLikedOnly(liked); find(liked ? 'outfit' : query || 'outfit', 0, liked); }}><Heart size={14} />{likedOnly ? 'Back to search' : 'My likes'}</button><small role="status">{syncError ? <>{syncError} <button className="culture-text-button" onClick={() => flush().catch(() => {})}>Retry</button></> : pending ? `${pending} saving…` : 'Choices synced'}</small></div>
    {last && <div className="shop-choice-status" role="status">{last.choice === 'dislike' ? 'Not for me saved.' : last.choice === 'like' ? 'Liked.' : 'Choice removed.'} <button className="culture-text-button" onClick={() => { choose(last.id, last.before); setLast(null); }}>Undo</button></div>}
    {busy && <p className="shop-agent-progress" role="status" aria-live="polite">{progress}…</p>}
    {error && <p role="alert">{error}</p>}
    {result?.agent && !likedOnly && <section className="shop-agent" aria-label="Shopping assistant">
      <p>{result.agent.message}</p>
      {result.agent.mode === 'rules_fallback' && <small>Language interpretation is temporarily unavailable. Using supported clothing terms.</small>}
      <form onSubmit={event => { event.preventDefault(); find(correction, 0, false, true); }}>
        <label htmlFor="outfit-correction">{result.agent.question ? 'Tell me a little more' : 'What should I change?'}</label>
        <div><input id="outfit-correction" value={correction} onChange={event => setCorrection(event.target.value)} maxLength={280} minLength={2} required placeholder="Less formal, more floral, or cheaper…" disabled={busy} />
        <Button type="submit" variant="secondary" disabled={busy || correction.trim().length < 2}>Update</Button></div>
      </form>
    </section>}
    {result && !result.agent?.question && <><div className="shop-results-heading"><h2>{likedOnly ? 'Your liked pieces' : 'Pieces for your request'}</h2><span>{Math.max(products.length, result.total - (result.products.length - products.length))} matches · {result.catalog_count.toLocaleString()} products</span></div>
      <p className="shop-catalog-note">Highest taste match first · estimated from your taste signals. Confirm current price, size and availability at the store.</p>
      <div className="shop-applied">{result.filters?.categories?.map(category => <span key={category}>{category}</span>)}{result.filters?.max_price && <span>Up to {money(result.filters.max_price)}</span>}{result.taste?.linked_discoveries > 0 && <span>{result.taste.linked_discoveries} linked cultural {result.taste.linked_discoveries === 1 ? 'discovery' : 'discoveries'}</span>}{result.taste?.qloo_brands > 0 && <span>{result.taste.qloo_brands} Qloo-connected brands in catalog</span>}</div>
      {result.taste?.qloo_status === 'unavailable' && <p className="shop-catalog-note">Qloo brand connections are temporarily unavailable. Your saved fashion preferences still guide results.</p>}
      {result.taste?.qloo_status === 'no_saved_interests' && <p className="shop-catalog-note"><a href="/dashboard">Save cultural discoveries and add fashion notes</a> to make this more personal.</p>}
      {products.length ? <div className="outfit-product-grid">{products.map(row => <article className="outfit-product" key={row.product_id} aria-label={row.name}>
        <a href={row.product_url} target="_blank" rel="noopener noreferrer" tabIndex={-1} aria-hidden="true"><ResilientImage src={row.image_url} alt={row.name} loading="lazy" /></a>
        <div className="outfit-product-copy"><small>{row.brand}</small><h3>{row.name}</h3><div className="shop-product-score"><strong>{money(row.price)}</strong>{Number.isFinite(row.taste_match) && <span title="Estimated agreement with your available taste signals; not a probability.">{row.taste_match}% taste match</span>}</div>{row.why?.length > 0 && <p className="shop-match-reason">{row.why[0]}</p>}
          <div className="outfit-product-feedback"><button type="button" aria-pressed={choices[row.product_id] === 'like'} disabled={!ready} onClick={() => choose(row.product_id, choices[row.product_id] === 'like' ? 'clear' : 'like')}><Heart size={16} />{choices[row.product_id] === 'like' ? 'Liked' : 'I like this'}</button><button type="button" disabled={!ready} onClick={() => choose(row.product_id, 'dislike')}><ThumbsDown size={16} />Not for me</button></div>
          <a className="shop-store-link" href={row.product_url} target="_blank" rel="noopener noreferrer">View on {row.retailer || 'Myntra'} <ArrowUpRight size={14} /></a>
        </div></article>)}</div> : <p className="shop-empty">{result.notice || (likedOnly ? 'Your liked pieces will appear here.' : 'No pieces match these details. Try a wider budget or fewer details.')}</p>}
      {result.products.length < result.total && <Button variant="secondary" disabled={busy} onClick={() => find(searchQuery, result.products.length)}>{busy ? 'Loading…' : 'Show more'}</Button>}
    </>}
  </main>;
}

export default function ShoppingPage() {
  const { status, user, error, retry } = useAuth();
  useEffect(() => { document.title = 'Shop your taste — Muselly'; }, []);
  useEffect(() => {
    try {
      if (status === 'signed-out') sessionStorage.setItem('muselly-explore-return', '/shop');
      if (status === 'signed-in') sessionStorage.removeItem('muselly-explore-return');
    } catch { /* Shopping can still open when session storage is unavailable. */ }
  }, [status]);
  const header = <header className="dashboard-header"><div className="container dashboard-nav"><Brand /><nav aria-label="Shopping navigation"><a href="/dashboard">My fashion direction</a></nav></div></header>;
  return <>{header}{status === 'signed-in' && user ? <OutfitShop key={user.id} ownerId={user.id} /> : status === 'signed-out' ? <SignIn /> : <main className="container outfit-shop"><p role="status">{error || 'Checking your sign-in…'}</p>{status === 'error' && <Button onClick={retry}>Retry</Button>}</main>}</>;
}
