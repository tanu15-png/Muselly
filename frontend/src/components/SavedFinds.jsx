import ResilientImage from './ResilientImage';
import { useEffect, useState } from 'react';
import { apiRequest } from '../lib/supabase';
import { Button, Card, Eyebrow } from './ui';

export default function SavedFinds() {
  const [items, setItems] = useState([]), [loading, setLoading] = useState(true), [error, setError] = useState(''), [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    apiRequest('/api/extension/saved', { signal: controller.signal }).then(data => { if (!controller.signal.aborted) setItems(data.items); })
      .catch(() => { if (!controller.signal.aborted) setError('Saved finds could not be loaded. Please retry.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [revision]);
  return <section className="profile-section" aria-labelledby="saved-finds-title"><div className="profile-section-heading"><div><Eyebrow>Little discoveries worth keeping</Eyebrow><h2 id="saved-finds-title">Your saved finds.</h2><p>Product bookmarks saved from the Muselly extension.</p></div><Button variant="secondary" onClick={() => setRevision(v => v + 1)} disabled={loading}>Reload saved finds</Button></div>{loading && <p role="status">Loading saved finds…</p>}{error && <p role="alert">{error}</p>}{!loading && !error && !items.length && <Card className="extension-guide"><p>Save a product from the extension to keep its store link here. Save snapshots to see them in your Style DNA inspiration library.</p><a className="text-link" href="/extension">Get the extension</a></Card>}<div className="saved-finds-grid">{items.map(item => <Card key={item.id} as="article" className="saved-find">{item.image && <ResilientImage src={item.image} alt={item.title} loading="lazy" />}<h3>{item.title}</h3><a className="text-link" href={item.url} target="_blank" rel="noopener noreferrer">Open saved product ↗</a></Card>)}</div></section>;
}
