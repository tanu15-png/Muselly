import { useEffect, useRef, useState } from 'react';
import { PrivateImage } from './InspirationUploader';
import { Button } from './ui';

export default function FashionReferencePicker({ entity, images, initialIds = [], onConfirm, onCancel }) {
  const [selected, setSelected] = useState(initialIds.filter(id => images.some(image => image.id === id)));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const dialog = useRef(null);
  useEffect(() => { dialog.current.showModal(); }, []);
  async function save() {
    setSaving(true); setError('');
    try { await onConfirm(selected); }
    catch (failure) { setError(failure.message || 'Couldn’t save this connection. Try again.'); }
    finally { setSaving(false); }
  }
  return <dialog ref={dialog} className="fashion-reference-dialog" aria-labelledby="fashion-reference-title" onCancel={event => { event.preventDefault(); if (!saving) onCancel(); }}>
    <h2 id="fashion-reference-title">How does {entity.name} inspire your style?</h2>
    <p>Choose the looks that express the connection.</p>
    {images.length ? <div className="fashion-reference-grid">{images.map(image => <button type="button" key={image.id} aria-label={`Select ${image.filename}`} aria-pressed={selected.includes(image.id)} disabled={saving} onClick={() => setSelected(ids => ids.includes(image.id) ? ids.filter(id => id !== image.id) : [...ids, image.id])}><PrivateImage image={image} retryable={false} /><span>{selected.includes(image.id) ? 'Selected' : 'Select'}</span></button>)}</div> : <p><a href="/taste-test?edit=1&step=inspirations">Add reference images</a> to connect this discovery to your style.</p>}
    {error && <p role="alert">{error}</p>}
    <div className="fashion-reference-actions"><button type="button" className="culture-text-button" disabled={saving} onClick={onCancel}>Cancel</button><Button disabled={!selected.length || saving} onClick={save}>{saving ? 'Saving…' : 'Save connection'}</Button></div>
  </dialog>;
}
