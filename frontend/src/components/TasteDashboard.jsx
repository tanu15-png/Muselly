import { useEffect, useRef, useState } from 'react';
import { Images, RefreshCw, SlidersHorizontal } from 'lucide-react';
import { Brand, Button } from './ui';
import { PrivateImage } from './InspirationUploader';
import { apiRequest } from '../lib/supabase';
import { matchingObservations } from '../lib/tasteProfile';
import CulturalDiscoveries from './CulturalDiscoveries';
import '../styles/dashboard.css';
import '../styles/culture.css';

const EDIT = '/taste-test?edit=1';
export default function TasteDashboard({ user }) {
  const [profile, setProfile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [openLibrary, setOpenLibrary] = useState(false);
  const [focusedIds, setFocusedIds] = useState(null);
  const library = useRef(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    document.title = 'Your cultural direction — Muselly';
    const controller = new AbortController();
    setLoading(true); setError('');
    Promise.all([apiRequest('/api/onboarding', { signal: controller.signal }), apiRequest('/api/onboarding/analysis', { signal: controller.signal }).catch(() => null)]).then(([data, insights]) => {
      if (!controller.signal.aborted) { setProfile(data); setAnalysis(insights); }
    }).catch(() => { if (!controller.signal.aborted) setError('Couldn’t open your profile. Try again.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => { mounted.current = false; controller.abort(); };
  }, [revision]);
  const visible = analysis?.status === 'succeeded' ? analysis : analysis?.previous_successful;
  const observations = matchingObservations(visible, profile?.images || []);
  async function prepareImages(signal) {
    if (analysis?.status === 'succeeded' && !analysis.stale) return;
    // A current image interpretation supplies grounded aesthetics for Qloo tag lookup.
    try {
      const data = await apiRequest(`/api/onboarding/analysis${visible ? '?force=true' : ''}`, { method: 'POST', signal });
      if (mounted.current) setAnalysis(data);
    } catch (failure) {
      if (signal.aborted || failure.status === 401) throw failure;
      // Cultural discovery remains useful from explicit interests without image analysis.
    }
  }
  function showEvidence(ids) {
    setFocusedIds(ids); setOpenLibrary(true);
    setTimeout(() => library.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
  }
  return <><header className="dashboard-header"><div className="container dashboard-nav"><Brand /><nav aria-label="Your taste navigation"><a href="#cultural-discoveries">Discoveries</a><a href="#taste-analytics">Analytics</a><a href="#your-inspirations" onClick={() => setOpenLibrary(true)}>Inspirations</a></nav><Button href={EDIT} variant="secondary"><SlidersHorizontal size={15} /> Edit taste</Button></div></header>
    <main id="main-content" className="dashboard culture-dashboard container">{loading ? <p role="status">Opening your taste profile…</p> : error ? <div className="culture-empty"><p role="alert">{error}</p><Button onClick={() => setRevision(value => value + 1)}>Try again <RefreshCw size={15} /></Button></div> : !profile?.completed_at ? <div className="culture-empty"><h1>Your taste starts here.</h1><Button href="/taste-test">Continue taste test</Button></div> : <>
      <CulturalDiscoveries key={user?.id} prepareImages={prepareImages} onEvidence={showEvidence} ownerId={user?.id} images={profile.images} />
      <section id="your-inspirations" ref={library} className="culture-library" aria-label="My inspirations"><details open={openLibrary} onToggle={event => setOpenLibrary(event.currentTarget.open)}><summary><span><Images size={18} /> My inspirations <small>{profile.images.length}</small></span><span>{openLibrary ? 'Close' : 'Open library'}</span></summary><div className="culture-library-tools"><Button href={`${EDIT}&step=inspirations`} variant="secondary">Manage inspirations ↗</Button>{focusedIds && <button className="culture-text-button" type="button" onClick={() => setFocusedIds(null)}>Show all inspirations</button>}</div><div className="culture-reference-grid">{profile.images.filter(image => !focusedIds || focusedIds.includes(image.id)).map(image => {
        const observation = observations.get(image.id);
        return <article className="culture-reference" key={image.id}><PrivateImage image={image} />{observation && <details><summary>Visual details</summary><p>{observation.description}</p><small>AI image interpretation</small></details>}</article>;
      })}</div></details></section>
    </>}</main></>;
}
