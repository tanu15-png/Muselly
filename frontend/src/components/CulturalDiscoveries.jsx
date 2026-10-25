import { useCallback, useEffect, useRef, useState } from 'react';
import { BookOpen, Film, Heart, Music2, Pause, Play, RotateCcw, Sparkles, Tv, X, Check } from 'lucide-react';
import { Button, Eyebrow } from './ui';
import { apiRequest } from '../lib/supabase';
import { discoveryStore, createOutboxSync } from '../lib/discoveryOutbox';
import ResilientImage from './ResilientImage';
import DiscoveryAnalytics from './DiscoveryAnalytics';
import FashionReferencePicker from './FashionReferencePicker';

const endpoint = '/api/onboarding/culture';
const labels = { artist: 'Music', movie: 'Films', tv_show: 'Shows', book: 'Books' };
const icons = { artist: Music2, movie: Film, tv_show: Tv, book: BookOpen };

export default function CulturalDiscoveries({ prepareImages, onEvidence, ownerId, images = [] }) {
  const [fashionCard, setFashionCard] = useState(null);
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [localSaving, setLocalSaving] = useState(false);
  const [error, setError] = useState('');
  const [storageError, setStorageError] = useState('');
  const [syncError, setSyncError] = useState('');
  const [syncAttempt, setSyncAttempt] = useState(0);
  const [paused, setPaused] = useState(false);
  const [pendingRows, setPendingRows] = useState([]);
  const [lastChoice, setLastChoice] = useState(null);
  const [analyticsOpen, setAnalyticsOpen] = useState(false);
  const [analyticsTab, setAnalyticsTab] = useState('visual');
  const [analyticsRevision, setAnalyticsRevision] = useState(0);
  const [analyticsSyncing, setAnalyticsSyncing] = useState(false);
  const [analyticsReady, setAnalyticsReady] = useState(false);
  const active = useRef(true);
  const requests = useRef(new Set());
  const worker = useRef(null);
  const current = useRef(null);
  const localLock = useRef(false);
  const batchLock = useRef(false);
  const automaticBatches = useRef(0);
  const musicAttempts = useRef(0);
  const retryDelay = useRef(2000);
  const runRef = useRef(null);
  const queue = run?.session?.queue || [];
  const card = queue[0];
  const sessionId = run?.session?.id;
  const visible = run?.status === 'succeeded' ? run : run?.previous_successful;
  const domains = run?.session?.domains || visible?.result?.domains || [];
  const failedKey = domains.filter(domain => domain.status === 'unavailable').map(domain => domain.id).join(',');
  const running = run?.status === 'running' && Date.now() - Date.parse(run.created_at) < 120000;
  const pendingChoices = pendingRows.filter(row => row.action !== 'shown').length;

  const apply = useCallback(state => {
    if (!active.current) return;
    current.current = state;
    runRef.current = state.run;
    setRun(state.run); setPendingRows(state.pending); setLastChoice(state.lastChoice);
  }, []);
  const request = useCallback(async (path, options = {}) => {
    const controller = new AbortController(); requests.current.add(controller);
    try { return await apiRequest(path, { ...options, expectedOwner: ownerId, signal: controller.signal }); }
    finally { requests.current.delete(controller); }
  }, [ownerId]);
  const accept = useCallback(async data => { const state = await discoveryStore.accept(ownerId, data); apply(state); return state; }, [ownerId, apply]);
  const flush = useCallback(async () => {
    if (!worker.current) throw new Error('Local saving is still opening.');
    const state = await worker.current.flush();
    if (active.current) { apply(state); setSyncError(''); retryDelay.current = 2000; }
    return state;
  }, [apply]);
  useEffect(() => {
    active.current = true;
    const instance = createOutboxSync({ owner: ownerId, store: discoveryStore, send: (id, actions) => request(`${endpoint}/sessions/${id}/sync`, { method: 'POST', body: { actions } }),
      onState: state => { if (active.current) { apply(state); setAnalyticsRevision(value => value + 1); } },
      onError: failure => { if (active.current) { setSyncError(failure.message || 'Choices are saved on this device. Sync will retry.'); retryDelay.current = Math.min(retryDelay.current * 2, 30000); setSyncAttempt(value => value + 1); } },
    });
    worker.current = instance;
    (async () => {
      try {
        const local = await discoveryStore.load(ownerId);
        if (!active.current) return;
        apply(local); setStorageError('');
        if (local.run) setLoading(false);
        try {
          // Replay durable actions before accepting the server's queue after reload.
          await instance.flush();
          if (active.current) await accept(await request(endpoint));
        } catch (failure) { if (active.current && failure.name !== 'AbortError') setError(local.run ? '' : 'Couldn’t load discoveries. Your local choices are retained.'); }
      } catch (failure) { if (active.current) setStorageError(failure.message || 'Enable browser storage to save choices locally.'); }
      finally { if (active.current) setLoading(false); }
    })();
    const online = () => { flush().catch(() => {}); };
    const visibleAgain = () => { if (document.visibilityState === 'visible') online(); };
    window.addEventListener('online', online); document.addEventListener('visibilitychange', visibleAgain);
    return () => { active.current = false; instance.stop(); requests.current.forEach(controller => controller.abort()); window.removeEventListener('online', online); document.removeEventListener('visibilitychange', visibleAgain); };
  }, [ownerId, apply, accept, request, flush]);

  useEffect(() => {
    if (!pendingRows.length) return;
    const timer = setTimeout(() => flush().catch(() => {}), syncError ? retryDelay.current : pendingChoices >= 5 ? 0 : 2000);
    return () => clearTimeout(timer);
  }, [pendingRows, pendingChoices, syncError, syncAttempt, flush]);
  useEffect(() => {
    if (!sessionId || !card || paused || storageError) return;
    let cancelled = false;
    discoveryStore.shown(ownerId, card).then(state => { if (!cancelled) apply(state); })
      .catch(failure => { if (!cancelled) setStorageError(failure.message); });
    return () => { cancelled = true; };
  }, [sessionId, card?.entity_id, ownerId, paused, storageError, apply]);
  useEffect(() => {
    const images = queue.slice(1, 4).filter(item => item.image).map(item => { const image = new Image(); image.referrerPolicy = 'no-referrer'; image.src = item.image; return image; });
    return () => { images.forEach(image => { image.src = ''; }); };
  }, [card?.entity_id]);
  useEffect(() => {
    if (!running || starting) return;
    const timer = setTimeout(() => request(endpoint).then(accept).catch(() => {}), 4000);
    return () => clearTimeout(timer);
  }, [run, running, starting, request, accept]);

  async function loadMore(automatic = false, retry = false) {
    const latest = runRef.current;
    if (!latest?.session || batchLock.current || starting || paused || storageError) return;
    if (automatic && automaticBatches.current >= 3 && !retry) return;
    batchLock.current = true; automaticBatches.current += 1; setFetching(true);
    try {
      // Retrying a failed category needn't delay behind writes; its results are
      // reconciled against the local consumed-card ledger before display.
      if (!retry) await flush();
      const query = new URLSearchParams();
      if (retry) query.set('retry', 'true');
      if (runRef.current?.session?.queue[0]) query.set('anchor', runRef.current.session.queue[0].entity_id);
      const data = await request(`${endpoint}/sessions/${latest.session.id}/batch${query.size ? `?${query}` : ''}`, { method: 'POST' });
      if (active.current) { await accept(data); setError(''); }
    } catch (failure) { if (active.current && !retry) setError(failure.message || 'Couldn’t prepare more discoveries. Try again.'); }
    finally { batchLock.current = false; if (active.current) setFetching(false); }
  }
  useEffect(() => {
    if (!sessionId || paused || starting || fetching || error || storageError || !run.session.has_more) return;
    if (queue.length <= 8 || run.session.choices_since_refresh >= 5) loadMore(true);
  }, [run, sessionId, paused, starting, fetching, error, storageError]);
  useEffect(() => {
    if (!failedKey || paused || starting || storageError || musicAttempts.current >= 3) return;
    const timer = setTimeout(() => {
      if (batchLock.current) return;
      musicAttempts.current += 1;
      loadMore(true, true);
    }, 2000 * 2 ** musicAttempts.current);
    return () => clearTimeout(timer);
  }, [failedKey, paused, starting, storageError, fetching]);

  async function choose(action, referenceImageIds) {
    if (action === 'fashion' && !referenceImageIds) { setFashionCard(card); return; }
    if (localLock.current || starting || !card || storageError) return;
    localLock.current = true; setLocalSaving(true);
    try { apply(await discoveryStore.choose(ownerId, fashionCard || card, action, referenceImageIds)); automaticBatches.current = 0; setError(''); setFashionCard(null); }
    catch (failure) { setStorageError(failure.message || 'Couldn’t save on this device. Your card has not advanced.'); }
    finally { localLock.current = false; if (active.current) setLocalSaving(false); }
  }
  async function undo() {
    if (localLock.current || !lastChoice) return;
    localLock.current = true; setLocalSaving(true);
    try { apply(await discoveryStore.undo(ownerId, lastChoice.event_id)); automaticBatches.current = 0; }
    catch (failure) { setStorageError(failure.message); }
    finally { localLock.current = false; if (active.current) setLocalSaving(false); }
  }
  async function start() {
    if (starting || fetching) return;
    setStarting(true); setError('');
    const controller = new AbortController(); requests.current.add(controller);
    try {
      await flush(); await prepareImages(controller.signal);
      if (!active.current || controller.signal.aborted) return;
      await accept(await request(`${endpoint}${visible ? '?force=true' : ''}`, { method: 'POST' }));
      if (active.current) { setPaused(false); automaticBatches.current = 0; musicAttempts.current = 0; setAnalyticsRevision(value => value + 1); }
    } catch (failure) { if (active.current) setError(failure.message || 'Couldn’t start discoveries. Please retry.'); }
    finally { requests.current.delete(controller); if (active.current) setStarting(false); }
  }
  useEffect(() => {
    if (!analyticsOpen) return;
    let cancelled = false;
    setAnalyticsReady(false); setAnalyticsSyncing(true);
    flush().then(() => { if (!cancelled) { setAnalyticsReady(true); setAnalyticsSyncing(false); setAnalyticsRevision(value => value + 1); } })
      .catch(() => { if (!cancelled) setAnalyticsSyncing(false); });
    return () => { cancelled = true; };
  }, [analyticsOpen, pendingRows.length, flush]);
  const Icon = icons[card?.domain] || Sparkles;
  const disabled = localSaving || starting || Boolean(storageError);
  return <section id="cultural-discoveries" className="culture-section" aria-labelledby="culture-title">
    {fashionCard && <FashionReferencePicker entity={fashionCard} images={images} onCancel={() => setFashionCard(null)} onConfirm={ids => choose('fashion', ids)} />}
    <div className="culture-heading deck-heading"><div><Eyebrow>Powered by Qloo</Eyebrow><h1 id="culture-title">Discover your <em>direction.</em></h1><p>One discovery. Your choice.</p></div><Button variant="secondary" disabled={starting || loading || fetching || running || Boolean(storageError)} onClick={start}>{sessionId ? 'Refresh discoveries' : 'Start discovering'}<Sparkles size={15} /></Button></div>
    <div className="deck-toolbar deck-toolbar--mixed"><small aria-live="polite">{pendingRows.length ? syncError ? `${pendingChoices || pendingRows.length} waiting to sync` : pendingChoices ? `Syncing ${pendingChoices} choice${pendingChoices === 1 ? '' : 's'}…` : 'Syncing…' : 'Synced'}</small>{sessionId && <button type="button" className="culture-text-button" onClick={() => setPaused(value => !value)}>{paused ? <Play size={14} /> : <Pause size={14} />}{paused ? 'Resume' : 'Pause'}</button>}</div>
    <div aria-live="polite">{(loading || starting && !card || running) && <p role="status">Finding your connections…</p>}{(error || storageError) && <p role="alert" className="culture-notice">{storageError || error}</p>}{syncError && <p className="deck-sync-notice">Choices remain on this device. <button className="culture-text-button" onClick={() => flush().catch(() => {})}>Retry sync</button></p>}{paused && <p role="status">Paused. Your place is saved.</p>}</div>
    {card && !paused ? <article className="discovery-poster" aria-label={card.name} key={card.entity_id}>
      <div className={`deck-art culture-art--${card.domain}`}>{card.image ? <ResilientImage src={card.image} alt={card.name} /> : <div className="deck-art-placeholder"><Icon size={56} strokeWidth={1} /><span>{card.name}</span></div>}<span className="culture-category"><Icon size={13} />{labels[card.domain]}</span></div>
      <div className="deck-card-copy"><span className="profile-source-label">{card.domain === 'artist' ? 'Artist discovery' : 'Qloo discovery'}</span><h2>{card.name}</h2><div className="deck-choices">{[['like', 'I like this', Heart], ['dislike', 'Not for me', X], ['known', 'Already know', Check], ['fashion', 'Use as fashion inspiration', Sparkles]].map(([action, label, ActionIcon]) => <button type="button" key={action} disabled={disabled} onClick={() => choose(action)}><ActionIcon size={19} /><span>{label}</span></button>)}</div><div className="deck-card-footer"><small>{card.image ? 'Artwork supplied through Qloo' : 'Qloo entity · artwork unavailable'}</small><button className="culture-text-button" type="button" disabled={disabled} onClick={() => choose('skip')}>Skip</button></div></div>
    </article> : !loading && !starting && !running && !paused && <div className="culture-empty"><Music2 size={34} /><h2>{sessionId ? 'More connections ahead.' : 'What else might you love?'}</h2><p>{fetching ? 'Preparing your next discoveries…' : sessionId ? 'Load more or refresh your direction.' : 'Start with your saved interests and inspirations.'}</p>{sessionId && run.session.has_more && <Button disabled={fetching} onClick={() => { automaticBatches.current = 0; setError(''); loadMore(); }}>Load more discoveries</Button>}</div>}
    {lastChoice && <div className="deck-last-choice" role="status"><span>{lastChoice.action === 'skip' ? 'Skipped' : 'Saved on this device'} · {lastChoice.card.name}</span><button className="culture-text-button" disabled={disabled} onClick={undo}><RotateCcw size={14} /> Undo</button></div>}
    {failedKey && <div className="deck-category-status">{failedKey.includes('artist') ? 'Music is taking longer. Other discoveries are ready.' : 'Some connections are taking longer.'} <button className="culture-text-button" disabled={fetching || starting} onClick={() => { musicAttempts.current = 0; loadMore(false, true); }}>Retry</button></div>}
    <section id="taste-analytics" className="deck-analytics"><details open={analyticsOpen} onToggle={event => { setAnalyticsReady(false); setAnalyticsOpen(event.currentTarget.open); }}><summary><span>Your taste, in focus</span><span>{analyticsOpen ? 'Close analytics' : 'View analytics'}</span></summary>{analyticsOpen && (!analyticsReady || analyticsSyncing || pendingRows.length ? <div className="analytics-sync"><p role="status">{syncError ? 'Waiting to sync your latest choices before showing analytics.' : 'Syncing your latest choices…'}</p>{syncError && <button className="culture-text-button" onClick={() => flush().catch(() => {})}>Retry sync</button>}</div> : <DiscoveryAnalytics selectedTab={analyticsTab} onTabChange={setAnalyticsTab} revision={analyticsRevision} onEvidence={onEvidence} ownerId={ownerId} images={images} />)}</details></section>
    <details className="culture-details"><summary>Behind your discoveries</summary><p>Qloo connections, mixed across music, films, shows and books. Choices save on this device first and sync in the background.</p><p>Artwork comes through Qloo. Likes and fashion saves inform future batches; familiarity is separate from dislike. No clothing preferences are inferred from poster colors.</p><a href="/taste-test?edit=1&question=q7">Edit my interests ↗</a></details>
  </section>;
}
