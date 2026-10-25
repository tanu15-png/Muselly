import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowUpRight, RefreshCw, Sparkles } from 'lucide-react';
import { Button, Card, Eyebrow } from './ui';
import { apiRequest } from '../lib/supabase';
import { brandLink } from '../lib/brandLinks';
import { readCache, writeCache } from '../lib/sessionCache';

const endpoint = '/api/onboarding/enrichment';
const expired = run => run?.status === 'running' && Date.now() - Date.parse(run.created_at) >= 120000;

function failureMessage(failure) {
  if (failure.status === 401) return 'Please sign in again to see your brand affinities.';
  if (failure.status === 429) return 'Brand enrichment has reached its usage limit. Please try again later.';
  if (failure.status === 503) return 'Brand enrichment is currently unavailable. Your saved preferences and style insights are still here.';
  if (failure.status === 504 || failure.name === 'AbortError') return 'Brand enrichment took too long. Check progress or try again in a moment.';
  return 'We couldn’t update your brand affinities. Your saved style profile is unchanged. Please try again.';
}

export default function EnrichmentPanel({ revision, ownerId }) {
  const cached = useRef(readCache(ownerId, 'enrichment'));
  const [run, setRun] = useState(cached.current?.value ?? null);
  const [loading, setLoading] = useState(!cached.current);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [paused, setPaused] = useState(false);
  const active = useRef(true);
  const pending = useRef(null);
  const polls = useRef(0);
  const previousRevision = useRef(revision);
  const save = useCallback(result => {
    setRun(result);
    writeCache(ownerId, 'enrichment', result);
  }, [ownerId]);
  const read = useCallback(async signal => {
    try {
      const result = await apiRequest(endpoint, { signal });
      if (active.current && !signal?.aborted) { save(result); setError(''); }
    } catch (failure) {
      if (!active.current || signal?.aborted) return;
      if (failure.status === 404) { save(null); setError(''); }
      else setError(failureMessage(failure));
    }
  }, [save]);
  useEffect(() => {
    active.current = true;
    return () => { active.current = false; pending.current?.abort(); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const entry = readCache(ownerId, 'enrichment');
    const changed = previousRevision.current !== revision;
    previousRevision.current = revision;
    if (!changed && entry?.fresh && entry.value?.status !== 'running') { setLoading(false); return; }
    setLoading(!entry);
    read(controller.signal).finally(() => {
      if (active.current && !controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [read, revision, ownerId]);
  useEffect(() => { polls.current = 0; setPaused(false); }, [run?.id]);
  useEffect(() => {
    if (run?.status !== 'running' || expired(run) || busy || paused) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      polls.current += 1;
      if (polls.current >= 30) { setPaused(true); return; }
      read(controller.signal);
    }, 4000);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [run, busy, paused, read]);

  async function update(path = endpoint, options = { method: 'POST' }) {
    if (busy) return;
    setBusy(true); setError('');
    const controller = new AbortController();
    pending.current = controller;
    const timer = setTimeout(() => controller.abort(), 75000);
    try {
      const result = await apiRequest(path, { ...options, signal: controller.signal });
      if (active.current) save(result);
    } catch (failure) {
      if (active.current) {
        await read();
        if (active.current && failure.status !== 409) setError(failureMessage(failure));
      }
    } finally {
      clearTimeout(timer);
      if (active.current) setBusy(false);
    }
  }

  const visible = run?.status === 'succeeded' ? run : run?.previous_successful;
  const result = visible?.result;
  const affinities = result?.affinities || [];
  const resolutions = result?.resolutions || [];
  const running = busy || (run?.status === 'running' && !expired(run));
  const evidence = resolutions.filter(item => item.status === 'resolved').map(item => item.input);
  const dismissed = run?.dismissed || [];
  return <section className="profile-section" aria-labelledby="enrichment-title">
    <div className="profile-section-heading"><div><Eyebrow>Connections beyond your moodboard</Eyebrow><h2 id="enrichment-title">Brands to explore.</h2><p>Discover brand affinities from your favorite brands and cultural interests.</p></div><span className="profile-source-label">Qloo affinities</span></div>
    <Card className="profile-enrichment">
      <p>Find fashion brands connected to the brands and cultural interests you already enjoy.</p>
      {loading && <p role="status">Loading saved brand affinities…</p>}
      {running && <p role="status">Finding connections in your interests. Your previous affinities stay available.</p>}
      {visible?.stale && <p className="enrichment-notice">Your preferences or style analysis have changed. Refresh these affinities to use your latest profile.</p>}
      {(paused || expired(run)) && <p className="enrichment-notice">The last update is taking longer than expected. Check progress or retry.</p>}
      {error && <p role="alert">{error}</p>}
      {!error && run?.status === 'failed' && <p role="status">The last enrichment could not finish. Your previous results and style profile are still saved.</p>}
      {!loading && !result && !running && <p>No saved brand affinities yet. Enrich your preferences when you’re ready.</p>}
      {result && <>
        {evidence.length > 0 && <p className="profile-muted">Based on your saved interests: {[...new Set(evidence)].join(', ')}.</p>}
        {['fashion', 'broader-brand'].map(category => {
          const values = affinities.filter(item => item.category === category);
          return values.length > 0 && <div key={category} className="enrichment-group"><h3>{category === 'fashion' ? 'Fashion brand affinities' : 'Broader brand affinities'}</h3>{category === 'broader-brand' && <p>These brands have no verified fashion category in this response.</p>}<ul>{values.map(item => { const link = brandLink(item); return <li key={item.entity_id}><div><strong>{item.name}</strong><span className="profile-source-label">From Qloo · based on your saved interests</span></div><div className="enrichment-actions"><a className="text-link enrichment-visit" href={link.href} target="_blank" rel="noopener noreferrer" aria-label={`${link.label}: ${item.name} (opens in a new tab)`}>{link.label} <ArrowUpRight size={14} /></a><button className="enrichment-preference" type="button" disabled={busy} onClick={() => update(`${endpoint}/affinities/${item.entity_id}`, { method: 'PUT', body: { dismissed: true } })}>Not for me<span className="sr-only">: {item.name}</span></button></div></li>; })}</ul></div>;
        })}
        {!affinities.length && <div className="enrichment-empty"><h3>No brand affinities added yet.</h3><p>{result.outcome === 'no-supported-signals' ? 'Qloo couldn’t use these interests to find related brands. Add a favorite artist, movie, or another fashion brand to give it more to connect.' : result.outcome === 'fashion-category-unavailable' ? 'Your interests matched, but Qloo couldn’t provide a verified fashion category. Try again later.' : dismissed.length ? 'You’ve hidden the available brand affinities. Restore a brand below or update your interests.' : 'Qloo found no related fashion brands for these interests. Try adding another favorite brand or artist.'}</p><div className="profile-buttons"><Button href="/taste-test?edit=1&question=q7" variant="secondary">Add a favorite artist</Button><Button href="/taste-test?edit=1&question=q13" variant="secondary">Edit favorite brands</Button></div></div>}

      </>}
      {dismissed.length > 0 && <details className="profile-reflections"><summary>Hidden brand affinities ({dismissed.length})</summary><ul>{dismissed.map(item => <li key={item.entity_id}>{item.name} <button className="enrichment-preference" type="button" disabled={busy} onClick={() => update(`${endpoint}/affinities/${item.entity_id}`, { method: 'PUT', body: { dismissed: false } })}>Restore<span className="sr-only">: {item.name}</span></button></li>)}</ul></details>}
      <div className="profile-buttons"><Button disabled={loading || running} onClick={() => update(`${endpoint}${visible ? '?force=true' : ''}`)}><Sparkles size={16} />{busy ? 'Updating affinities…' : visible ? 'Refresh brand affinities' : 'Enrich my preferences'}</Button>{(running || paused || expired(run)) && <Button variant="secondary" disabled={loading || busy} onClick={() => { polls.current = 0; setPaused(false); read(); }}><RefreshCw size={16} /> Check enrichment progress</Button>}{error && !running && <Button variant="secondary" disabled={loading || busy} onClick={() => read()}>Reload saved affinities</Button>}</div>
      {visible?.completed_at && <p className="profile-meta">{affinities.length ? `${affinities.length} brand affinities saved` : 'Last checked'} {new Date(visible.completed_at).toLocaleDateString()}</p>}
    </Card>
  </section>;
}
