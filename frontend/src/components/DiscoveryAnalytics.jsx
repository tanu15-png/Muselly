import { useEffect, useState } from 'react';
import { ArrowUpRight } from 'lucide-react';
import FashionDirectionBoard from './FashionDirectionBoard';
import { apiRequest } from '../lib/supabase';

const labels = { artist: 'Music', movie: 'Films', tv_show: 'Shows', book: 'Books' };
const swatches = { cream: '#eee4cd', ivory: '#f3efdf', white: '#fff', black: '#252525', blue: '#8ca9c2', 'light blue': '#bfdaeb', navy: '#293750', pink: '#dfaabb', red: '#ae4141', burgundy: '#733440', green: '#72917d', sage: '#a8b9a0', brown: '#86674f', beige: '#c9b69c', grey: '#a2a1a0', gray: '#a2a1a0', yellow: '#e5ca6d', purple: '#a18bb6' };
function Bars({ rows, denominator, onEvidence, color = false }) {
  const maximum = denominator || Math.max(1, ...rows.map(row => row.count));
  return rows.length ? <div className="insight-bars">{rows.slice(0, 10).map(row => <div className="insight-bar" key={row.label}><div className="insight-bar-label">{color && <i style={{ background: swatches[row.label.toLowerCase()] || '#b7a6ad' }} aria-hidden="true" />}{row.image_ids?.length ? <button type="button" onClick={() => onEvidence(row.image_ids)}>{row.label}<ArrowUpRight size={12} /></button> : <span>{row.label}</span>}<small>{row.count}{denominator ? ` / ${denominator}` : ''}</small></div><div className="insight-track"><span style={{ width: `${Math.min(100, row.count / maximum * 100)}%` }} /></div></div>)}</div> : <p className="insight-empty">More choices will bring this into focus.</p>;
}
export default function DiscoveryAnalytics({ revision, onEvidence, ownerId, images = [], selectedTab, onTabChange }) {
  const [data, setData] = useState(null);
  const [localTab, setLocalTab] = useState('visual');
  const tab = selectedTab || localTab;
  function setTab(value) { setLocalTab(value); onTabChange?.(value); }
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    apiRequest('/api/onboarding/culture/analytics', { signal: controller.signal, expectedOwner: ownerId }).then(result => {
      if (!controller.signal.aborted) { setData(result); setError(''); }
    }).catch(() => { if (!controller.signal.aborted) setError('Couldn’t load analytics. Your choices are saved.'); });
    return () => controller.abort();
  }, [revision, retry, ownerId]);
  const visual = data?.visual;
  const cultural = data?.cultural;
  const combined = data?.combined;
  return <div className="discovery-analytics">{error && <p role="alert">{error} <button className="culture-text-button" onClick={() => setRetry(value => value + 1)}>Retry</button></p>}
    <div className="culture-tabs insight-tabs" aria-label="Analytics views">{[['visual', 'Colors & patterns'], ['cultural', 'Cultural taste'], ['combined', 'Your direction']].map(([id, label]) => <button key={id} aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>)}</div>
    {!data ? <p role="status">Opening your taste insights…</p> : <>
      {tab === 'visual' && visual && <><div className="insight-section-heading"><h2>Your visual signature</h2><span>{visual.analyzed_images} of {visual.saved_images} inspirations analyzed</span></div>{visual.stale && <p className="insight-note">Your inputs changed. Only matching, unchanged images are counted. Refresh discoveries to update image analysis.</p>}
        <div className="insight-grid"><section className="insight-panel"><h3>Your color palette</h3><p>Images containing each color · approximate swatches</p><Bars rows={visual.colors} denominator={visual.analyzed_images} onEvidence={onEvidence} color /></section><section className="insight-panel"><h3>Patterns you save</h3><p>Images containing each pattern</p><Bars rows={visual.patterns} denominator={visual.analyzed_images} onEvidence={onEvidence} /></section></div>
        <div className="insight-selected"><span>You selected in your questionnaire</span><div className="profile-chips">{visual.stated_colors.length ? visual.stated_colors.map(value => <span key={value}>{value}</span>) : <span>No color preference shared</span>}</div></div><p className="insight-note">AI observations from your reference images. Each attribute counts once per image; one image may contain several colors or patterns. Select a label to see the evidence.</p></>}
      {tab === 'cultural' && cultural && <><div className="insight-section-heading"><h2>Your cultural taste</h2><span>{cultural.sessions} discovery sessions viewed</span></div><div className="insight-metrics">{[['shown', 'Seen'], ['liked', 'Liked'], ['disliked', 'Not for me'], ['known', 'Already know'], ['fashion', 'Fashion saves']].map(([key, label]) => <div key={key}><strong>{cultural.totals[key]}</strong><span>{label}</span></div>)}</div>
        <div className="insight-grid"><section className="insight-panel"><h3>What resonates</h3><p>Likes ÷ likes and dislikes · familiarity excluded</p><div className="insight-bars">{cultural.domains.map(domain => <div className="insight-bar" key={domain.id}><div className="insight-bar-label"><span>{labels[domain.id]}</span><small>{domain.like_rate === null ? 'Not rated' : `${domain.like_rate}% · ${domain.rated} rated`}</small></div><div className="insight-track"><span style={{ width: `${domain.like_rate || 0}%` }} /></div><small className="insight-domain-detail">{domain.shown} seen · {domain.liked} liked · {domain.disliked} disliked · {domain.known} familiar · {domain.fashion} fashion saves</small></div>)}</div></section><section className="insight-panel"><h3>Themes in your likes</h3><p>Qloo tags attached to liked entities</p><Bars rows={cultural.themes} onEvidence={onEvidence} /></section></div>
        <section className="insight-panel insight-history"><h3>Your discovery rhythm</h3><p>Saved choices by UTC date · undone choices excluded</p>{cultural.history.length ? <div className="insight-history-chart">{cultural.history.map(point => { const sum = point.like + point.dislike + point.known + point.fashion; const max = Math.max(1, ...cultural.history.map(row => row.like + row.dislike + row.known + row.fashion)); return <div key={point.date}><strong>{sum}</strong><div className="history-column" role="img" aria-label={`${point.date}: ${point.like} likes, ${point.dislike} dislikes, ${point.known} familiar, ${point.fashion} fashion saves`}>{['fashion', 'known', 'dislike', 'like'].map(key => <i key={key} className={`history-${key}`} style={{ height: `${point[key] / max * 100}%` }} />)}</div><small>{point.date.slice(5)}</small></div>; })}</div> : <p className="insight-empty">Your next choices will start this timeline.</p>}<div className="history-legend">{[['like', 'Liked'], ['dislike', 'Not for me'], ['known', 'Familiar'], ['fashion', 'Fashion']].map(([key, label]) => <span key={key}><i className={`history-${key}`} />{label}</span>)}</div></section><p className="insight-note">Seen counts track distinct cards actually displayed since session tracking began. Earlier saved preferences remain in totals; past views cannot be reconstructed.</p></>}
      {tab === 'combined' && combined && <FashionDirectionBoard entities={combined.fashion_entities} images={images} ownerId={ownerId} onEvidence={onEvidence} onChange={(id, fashion, ids) => {
        setData(current => ({ ...current, combined: { ...current.combined, fashion_entities: current.combined.fashion_entities.filter(entity => fashion || entity.entity_id !== id).map(entity => entity.entity_id === id ? { ...entity, reference_image_ids: ids, colors: [], patterns: [] } : entity) } }));
        setRetry(value => value + 1);
      }} />}

    </>}
  </div>;
}
