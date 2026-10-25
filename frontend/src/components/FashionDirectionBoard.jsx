import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { apiRequest } from '../lib/supabase';
import { PrivateImage } from './InspirationUploader';
import ResilientImage from './ResilientImage';
import FashionReferencePicker from './FashionReferencePicker';

const labels = { artist: 'Music', movie: 'Film', tv_show: 'Show', book: 'Book' };

export default function FashionDirectionBoard({ entities, images, ownerId, onChange, onEvidence }) {
  const [editing, setEditing] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [error, setError] = useState('');
  const [limit, setLimit] = useState(8);
  async function save(entity, fashion, ids) {
    await apiRequest(`/api/onboarding/culture/feedback/${entity.entity_id}`, {
      method: 'PUT', expectedOwner: ownerId,
      body: { preference: entity.preference || null, fashion_inspiration: fashion,
        ...(ids ? { reference_image_ids: ids } : {}) },
    });
    onChange(entity.entity_id, fashion, ids);
  }
  async function remove(entity) {
    setRemoving(entity.entity_id); setError('');
    try { await save(entity, false); }
    catch (failure) { setError(failure.message || 'Couldn’t remove this connection. Try again.'); }
    finally { setRemoving(null); }
  }
  return <section className="fashion-direction" aria-labelledby="fashion-direction-title">
    <div className="insight-section-heading"><h2 id="fashion-direction-title">My fashion direction</h2><span>{entities.length} saved {entities.length === 1 ? 'discovery' : 'discoveries'}</span></div>
    {editing && <FashionReferencePicker entity={editing} images={images} initialIds={editing.reference_image_ids || []} onCancel={() => setEditing(null)} onConfirm={async ids => { await save(editing, true, ids); setEditing(null); }} />}
    {error && <p role="alert">{error}</p>}
    {!entities.length ? <p className="insight-empty">Save a discovery as fashion inspiration, then choose the looks that connect it to your style.</p> : <div className="fashion-direction-grid">{entities.slice(0, limit).map(entity => {
      const references = images.filter(image => entity.reference_image_ids?.includes(image.id));
      const busy = removing === entity.entity_id;
      return <article className="fashion-direction-card" key={entity.entity_id} aria-label={`${entity.name} fashion connection`}>
        <div className="fashion-direction-media"><div className="fashion-direction-poster">{entity.image ? <ResilientImage src={entity.image} alt={`${entity.name} cultural artwork`} /> : <div className="fashion-poster-placeholder"><Sparkles size={28} /><span>{entity.name}</span></div>}</div>
          <div className="fashion-direction-looks">{references.length ? references.map(image => <button type="button" key={image.id} title={image.filename} aria-label={`View ${image.filename}`} onClick={() => onEvidence([image.id])}><PrivateImage image={image} retryable={false} /></button>) : <div className="fashion-direction-unlinked">Your looks belong here</div>}</div>
        </div>
        <div className="fashion-direction-copy"><small>{labels[entity.domain || entity.type?.split(':').pop()] || 'Qloo discovery'}</small><h3>{entity.name}</h3>
          {references.length > 0 && <div className="fashion-direction-attributes">{entity.colors?.length > 0 && <div aria-label="Colors in linked looks"><small>Colors</small><div className="profile-chips">{entity.colors.map(color => <span key={color}>{color}</span>)}</div></div>}{entity.patterns?.length > 0 && <div aria-label="Patterns in linked looks"><small>Patterns</small><div className="profile-chips">{entity.patterns.map(pattern => <span key={pattern}>{pattern}</span>)}</div></div>}{!entity.colors?.length && !entity.patterns?.length && <small>Colors and patterns appear after reference analysis.</small>}</div>}
          <div className="fashion-direction-actions"><button type="button" className="culture-text-button" disabled={Boolean(removing)} onClick={() => { setError(''); setEditing(entity); }}>{references.length ? 'Edit connection' : 'Choose looks'}</button><button type="button" className="culture-text-button" disabled={Boolean(removing)} onClick={() => remove(entity)}>{busy ? 'Removing…' : 'Remove connection'}</button></div>
        </div>
      </article>;
    })}</div>}
    {entities.length > limit && <button type="button" className="culture-text-button" onClick={() => setLimit(value => value + 8)}>Show more discoveries</button>}
    {entities.length > 0 && <p className="insight-note">Your chosen references · colors and patterns observed in those looks.</p>}
  </section>;
}
