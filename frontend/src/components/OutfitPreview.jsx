import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../lib/supabase';
import { Button } from './ui';

export default function OutfitPreview({ ownerId, query, onSearch }) {
  const [items, setItems] = useState([]), [selected, setSelected] = useState(null);
  const [quota, setQuota] = useState(null), [busy, setBusy] = useState(false);
  const [error, setError] = useState(''), [change, setChange] = useState('');
  const lock = useRef(false), feedbackLock = useRef(false);
  const [savingFeedback, setSavingFeedback] = useState(false);
  async function vote(choice, reason = null) {
    if (feedbackLock.current || !selected) return;
    const previous = selected;
    const feedback = choice === 'clear' ? null : { choice, reason };
    const update = value => { setSelected(value); setItems(rows => rows.map(row => row.id === value.id ? value : row)); };
    feedbackLock.current = true; setSavingFeedback(true); setError('');
    update({ ...selected, feedback });
    try {
      await apiRequest(`/api/outfits/${selected.id}/feedback`, { method: 'PUT', expectedOwner: ownerId, body: { choice, reason } });
    } catch (failure) { update(previous); setError('Your choice was not saved. Please retry.'); }
    finally { feedbackLock.current = false; setSavingFeedback(false); }
  }
  const [pieces, setPieces] = useState([]);
  const [activity, setActivity] = useState('');
  async function findPieces() {
    setBusy(true); setError(''); setActivity('Finding outfit pieces...');
    try { const data = await apiRequest(`/api/outfits/${selected.id}/similar`, { method: 'POST', expectedOwner: ownerId }); setPieces(data.queries); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    let active = true;
    apiRequest('/api/outfits', { expectedOwner: ownerId }).then(data => {
      if (active) { setItems(data.outfits); setSelected(data.outfits[0] || null); setQuota(data); }
    }).catch(() => { if (active) setError('Could not load outfit previews. Refresh to retry.'); });
    return () => { active = false; };
  }, [ownerId]);
  async function generate(correction = false) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(''); setActivity('Creating your outfit from your request and Qloo taste...');
    try {
      const data = await apiRequest('/api/outfits', { expectedOwner: ownerId, method: 'POST', timeoutMs: 180000,
        body: { message: correction ? change : query, ...(correction ? { parent_id: selected.id } : {}) } });
      setItems(previous => [data.outfit, ...previous]); setSelected(data.outfit); setPieces([]); setQuota(data); setChange('');
    } catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  }
  const exhausted = !quota || quota.daily_remaining <= 0 || quota.total_remaining <= 0;
  return <section className="outfit-preview" aria-label="Outfit inspiration">
    <Button variant="secondary" disabled={savingFeedback || busy || exhausted || query.trim().length < 2} onClick={() => generate()}>{selected ? 'Generate another outfit' : 'Generate one outfit'}</Button>
    {quota && <small> {quota.daily_remaining} of 3 left today · {quota.total_remaining} total remaining. One image per click, including revisions. Resets at midnight UTC.</small>}
    {busy && <p role="status">{activity}</p>}
    {error && <p role="alert">{error}</p>}
    {selected && <>
      <p>AI outfit inspiration · similar pieces may differ</p>
      <img src={`data:${selected.mime};base64,${selected.image}`} alt="Generated outfit inspiration"  />
      <div className="outfit-product-feedback">
        <button type="button" disabled={savingFeedback || busy} aria-pressed={selected.feedback?.choice === 'like'} onClick={() => vote(selected.feedback?.choice === 'like' ? 'clear' : 'like')}>I like this</button>
        <button type="button" disabled={savingFeedback || busy} aria-pressed={selected.feedback?.choice === 'dislike'} onClick={() => vote(selected.feedback?.choice === 'dislike' ? 'clear' : 'dislike')}>Not for me</button>
      </div>
      {selected.feedback && <div className="feedback-details">
        <label htmlFor="outfit-feedback-reason">{selected.feedback.choice === 'like' ? 'What do you like?' : 'What feels wrong?'} (optional)</label>
        <select id="outfit-feedback-reason" disabled={savingFeedback || busy} value={selected.feedback.reason || ''} onChange={event => vote(selected.feedback.choice, event.target.value || null)}>
          <option value="">No specific reason</option><option value="color">Color</option><option value="shape">Shape</option><option value="overall style">Overall style</option>
        </select>
        <small role="status">{savingFeedback ? 'Saving…' : 'Saved · helps shape your next outfit'}</small>
        <button type="button" disabled={savingFeedback || busy} onClick={() => vote('clear')}>Clear choice</button>
      </div>}
      <p><small>{selected.qloo_brands} Qloo-connected brands considered{selected.qloo_status !== 'ready' ? ' · limited Qloo context' : ''}</small></p>
      <form onSubmit={event => { event.preventDefault(); generate(true); }}>
        <label htmlFor="preview-correction">What should change?</label>
        <input id="preview-correction" value={change} onChange={event => setChange(event.target.value)} maxLength={280} placeholder="Keep the trousers, change the top" />
        <Button disabled={savingFeedback || busy || exhausted || change.trim().length < 2}>Revise image</Button>
      </form>
      <Button variant="secondary" disabled={savingFeedback || busy} onClick={findPieces}>Find pieces to shop</Button>
      {pieces.map(piece => <button type="button" key={piece} onClick={() => onSearch(piece)}>{piece}</button>)}
      {items.length > 1 && <select disabled={savingFeedback || busy} aria-label="Saved outfit previews" value={selected.id} onChange={event => { setSelected(items.find(item => item.id === event.target.value)); setPieces([]); }}>{items.map((item, index) => <option key={item.id} value={item.id}>Outfit {items.length - index}</option>)}</select>}
    </>}
  </section>;
}
