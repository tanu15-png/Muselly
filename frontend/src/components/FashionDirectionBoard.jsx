import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../lib/supabase';
import ResilientImage from './ResilientImage';

const labels = { artist: 'Music', movie: 'Film', tv_show: 'Show', book: 'Book' };

function FashionNote({ entity, ownerId }) {
  const key = `muselly-fashion-note:${ownerId}:${entity.entity_id}`;
  const [note, setNote] = useState(() => {
    try { return localStorage.getItem(key) ?? entity.fashion_note ?? ''; }
    catch { return entity.fashion_note || ''; }
  });
  const latest = useRef(note);
  const saved = useRef(entity.fashion_note || '');
  const working = useRef(false);
  const flushPending = useRef(() => {});
  const [status, setStatus] = useState('');
  useEffect(() => () => { flushPending.current(); }, []);
  useEffect(() => {
    let active = true;
    async function flush() {
      if (working.current || latest.current === saved.current) return;
      working.current = true;
      if (active) setStatus('Saving…');
      try {
        while (latest.current !== saved.current) {
          const value = latest.current;
          await apiRequest(`/api/onboarding/culture/feedback/${entity.entity_id}/fashion-note`, {
            method: 'PATCH', expectedOwner: ownerId, body: { note: value },
          });
          saved.current = value;
        }
        try { if (localStorage.getItem(key) === latest.current) localStorage.removeItem(key); } catch { /* storage unavailable */ }
        if (active) setStatus('Saved');
      } catch { if (active) setStatus('Not synced. Will retry.'); }
      finally { working.current = false; }
    }
    flushPending.current = flush;
    const timer = window.setTimeout(flush, 700);
    const retry = window.setInterval(flush, 5000);
    window.addEventListener('online', flush);
    return () => { active = false; clearTimeout(timer); clearInterval(retry); window.removeEventListener('online', flush); };
  }, [note, key, entity.entity_id, ownerId]);
  return <div className="fashion-note"><label htmlFor={`fashion-note-${entity.entity_id}`}>How does this inspire your style?</label>
    <textarea id={`fashion-note-${entity.entity_id}`} rows={3} maxLength={500} value={note} onBlur={() => flushPending.current()}
      placeholder="I like the tailored jackets, dark colors and confident feel."
      onChange={event => { const value = event.target.value; latest.current = value; setNote(value); setStatus('Saving…');
        try { localStorage.setItem(key, value); } catch { setStatus('Draft stays open until saved.'); }
      }} /><small role="status">{status}</small></div>;
}

export default function FashionDirectionBoard({ entities, ownerId, onChange }) {
  const [removing, setRemoving] = useState(null);
  const [error, setError] = useState('');
  const [limit, setLimit] = useState(8);
  async function remove(entity) {
    setRemoving(entity.entity_id); setError('');
    try {
      await apiRequest(`/api/onboarding/culture/feedback/${entity.entity_id}`, {
        method: 'PUT', expectedOwner: ownerId,
        body: { preference: entity.preference || null, fashion_inspiration: false },
      });
      try { localStorage.removeItem(`muselly-fashion-note:${ownerId}:${entity.entity_id}`); } catch { /* storage unavailable */ }
      onChange(entity.entity_id, false, undefined);
    } catch (failure) { setError(failure.message || 'Couldn’t remove this connection. Try again.'); }
    finally { setRemoving(null); }
  }
  return <section className="fashion-direction" aria-labelledby="fashion-direction-title">
    <div className="insight-section-heading"><h2 id="fashion-direction-title">My fashion direction</h2><span>{entities.length} saved {entities.length === 1 ? 'discovery' : 'discoveries'}</span></div>
    <p className="insight-note">Describe what inspires you. Your notes help personalize shopping results.</p>
    {error && <p role="alert">{error}</p>}
    {!entities.length ? <p className="insight-empty">Save a discovery as fashion inspiration to start your direction board.</p> : <div className="fashion-direction-grid">{entities.slice(0, limit).map(entity =>
      <article className="fashion-direction-card fashion-direction-card--note" key={`${ownerId}:${entity.entity_id}`} aria-label={`${entity.name} fashion connection`}>
        <div className="fashion-direction-poster">{entity.image && <ResilientImage src={entity.image} alt={`${entity.name} cultural artwork`} />}</div>
        <div className="fashion-direction-copy"><small>{labels[entity.domain || entity.type?.split(':').pop()] || 'Qloo discovery'}</small><h3>{entity.name}</h3>
          <FashionNote entity={entity} ownerId={ownerId} />
          <div className="fashion-direction-actions"><button type="button" className="culture-text-button" disabled={Boolean(removing)} onClick={() => remove(entity)}>{removing === entity.entity_id ? 'Removing…' : 'Remove connection'}</button></div>
        </div>
      </article>)}</div>}
    {entities.length > limit && <button type="button" className="culture-text-button" onClick={() => setLimit(value => value + 8)}>Show more discoveries</button>}
  </section>;
}
