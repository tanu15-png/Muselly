import { useEffect, useState } from 'react';
import { ArrowUpRight, BarChart3, RefreshCw, Sparkles } from 'lucide-react';
import { apiRequest } from '../lib/supabase';
import { matchingObservations, observedAttributes } from '../lib/tasteProfile';
import { Card, Eyebrow } from './ui';
import { PrivateImage } from './InspirationUploader';

const dimensions = [['possible_aesthetics', 'Aesthetics'], ['silhouettes', 'Fits & shapes'], ['patterns', 'Patterns'], ['garments', 'Garments']];
const feedbackLabels = {more_like_this: 'More like this', not_my_style: 'Not my style', too_expensive: 'Too expensive', wrong_shape: 'Wrong shape', wrong_color: 'Wrong color'};
const inputLabels = {brand: 'Brands', artist: 'Artists', inspiration: 'Named inspirations', tag: 'Cultural tags', other: 'Other interests'};
const colors = {cream:'--palette-cream',ivory:'--palette-cream',white:'--surface',beige:'--palette-sand',tan:'--palette-sand',brown:'--palette-brown',black:'--ink',grey:'--muted',gray:'--muted',silver:'--muted',navy:'--color-navy',blue:'--palette-blue',pink:'--accent',blush:'--accent',green:'--success',sage:'--success',red:'--danger',burgundy:'--palette-burgundy',purple:'--color-lavender',lavender:'--color-lavender',yellow:'--color-yellow',gold:'--color-gold',peach:'--color-peach',orange:'--color-orange'};

function swatch(label) {
  const words = label.toLowerCase().split(/\s+/);
  const name = words.findLast(word => colors[word]);
  return `var(${colors[name] || '--muted'})`;
}

export function inspirationAnalytics(analysis, images) {
  const observations = [...matchingObservations(analysis, images).values()].filter(Boolean);
  return {observations, colors: observedAttributes(observations, 'colors')};
}

function Bars({rows, maximum, onSelect, unit = 'looks'}) {
  return <div className="taste-bars">{rows.map(row => {
    const count = row.count ?? row.evidence_image_ids?.length ?? 0;
    const contents = <><span className="taste-bar-label">{row.attribute}<strong>{count}<small> {count===1 ? unit.slice(0,-1) : unit}</small></strong></span><span className="taste-bar-track" aria-hidden="true"><span style={{width:`${maximum ? count / maximum * 100 : 0}%`}} /></span></>;
    return onSelect ? <button className="taste-bar-row" key={row.attribute} onClick={() => onSelect(row.evidence_image_ids)} aria-label={`${row.attribute}: ${count} of ${maximum} analyzed looks. View supporting inspirations.`}>{contents}</button> : <div className="taste-bar-row" key={row.attribute}>{contents}</div>;
  })}<div className="taste-chart-axis"><span>0</span><span>{unit === 'looks' ? 'Analyzed looks (count)' : 'Products (count)'}</span><span>{maximum}</span></div></div>;
}

function ColorChart({rows, onSelect}) {
  const shown = rows.slice(0, 5);
  if (rows.length > 5) shown.push({attribute:'Other colors', count:rows.slice(5).reduce((sum,row)=>sum+row.evidence_image_ids.length,0), evidence_image_ids:[...new Set(rows.slice(5).flatMap(row=>row.evidence_image_ids))]});
  const total = rows.reduce((sum,row)=>sum+row.evidence_image_ids.length,0);
  let offset = 0;
  return <><div className="taste-color-layout"><div className="taste-donut"><svg viewBox="0 0 180 180" role="img" aria-label={`Color observations: ${shown.map(row=>`${row.attribute} ${row.count ?? row.evidence_image_ids.length}`).join(', ')}`}>
    <circle cx="90" cy="90" r="70" fill="none" className="taste-donut-track" strokeWidth="18" />
    {shown.map(row=>{
      const count = row.count ?? row.evidence_image_ids.length;
      const start = offset; offset += count / total * 100;
      return <circle key={row.attribute} cx="90" cy="90" r="70" pathLength="100" fill="none" stroke={swatch(row.attribute)} strokeWidth="18" strokeDasharray={`${count / total * 100} ${100-count / total*100}`} strokeDashoffset={-start} transform="rotate(-90 90 90)"><title>{row.attribute}: {count} color observations</title></circle>;
    })}
    <text x="90" y="88" textAnchor="middle" className="taste-donut-number">{total}</text><text x="90" y="108" textAnchor="middle" className="taste-donut-caption">observations</text>
  </svg></div><div className="taste-color-legend">{shown.map(row=><button key={row.attribute} onClick={()=>onSelect(row.evidence_image_ids)} aria-label={`${row.attribute}: ${row.count ?? row.evidence_image_ids.length} color observations. View inspirations.`}><span style={{background:swatch(row.attribute)}} aria-hidden="true" /><span>{row.attribute}</span><strong>{row.count ?? row.evidence_image_ids.length}</strong></button>)}</div></div><p className="taste-chart-note">One observation per color per look. A look can contain several colors; swatches are approximate.</p></>;
}

function QlooChart({data}) {
  const [selected, setSelected] = useState(null);
  const groups = Object.entries(data.input_counts).filter(([, count])=>count>0);
  const maximum = Math.max(1,...groups.map(([,count])=>count));
  const inputs = data.inputs.filter(row=>!selected || row.kind===selected);
  return <Card className="taste-chart taste-qloo"><div className="taste-chart-heading"><Eyebrow>Powered by Qloo</Eyebrow><Sparkles size={18} /></div><h3>Your cultural connections.</h3>
    {data.status === 'not_generated' ? <div className="taste-chart-start"><p>Connect your favorite brands, artists and cultural interests to discover fashion brands through Qloo.</p><a href="/explore#brand-affinities">Discover my connections <ArrowUpRight size={15} /></a></div> : <>
      <p className="taste-qloo-state">{data.stale ? 'Earlier Qloo run · refresh to use your current taste' : 'Saved Qloo discoveries'}{data.completed_at ? ` · ${new Date(data.completed_at).toLocaleDateString(undefined,{month:'short',day:'numeric'})}` : ''}</p>
      {groups.length>0 && <><div className="taste-qloo-bars" aria-label="Resolved interests used in the saved Qloo run">{groups.map(([kind,count])=><button key={kind} onClick={()=>setSelected(selected===kind?null:kind)} aria-pressed={selected===kind}><span>{inputLabels[kind] || kind}<strong>{count}</strong></span><span className="taste-bar-track" aria-hidden="true"><span style={{width:`${count/maximum*100}%`}} /></span></button>)}</div><div className="taste-chart-axis"><span>0</span><span>Resolved interests (count)</span><span>{maximum}</span></div><div className="taste-input-chips" aria-label="Saved Qloo input interests">{inputs.map((input,index)=><span key={`${input.kind}-${index}`}>{input.label}</span>)}</div><p className="taste-chart-note">Resolved input counts, not influence scores. Select a group to see its interests.</p></>}
      {data.unresolved_count>0 && <p className="taste-chart-note">{data.unresolved_count} input{data.unresolved_count===1?'':'s'} could not be resolved or were deferred in this run.</p>}
      {data.brands.length>0 && <div className="taste-brand-list"><span>Brand discoveries · saved Qloo order</span>{data.brands.slice(0,3).map(brand=><div key={brand.entity_id}><span>#{brand.rank}</span><strong>{brand.name}</strong></div>)}</div>}
      <a className="taste-chart-link" href="/explore#brand-affinities">{data.stale ? 'Refresh Qloo discoveries' : 'Explore your discoveries'} <ArrowUpRight size={15} /></a>
    </>}
  </Card>;
}

export default function TasteAnalytics({profile, analysis, onSelect}) {
  const [field,setField] = useState('possible_aesthetics');
  const [data,setData] = useState(null);
  const [error,setError] = useState(false);
  const [revision,setRevision] = useState(0);
  useEffect(()=>{
    const controller=new AbortController(); setError(false); setData(null);
    apiRequest('/api/onboarding/analytics',{signal:controller.signal}).then(value=>{
      if(!value?.qloo || !value?.shopping) throw new Error('Missing analytics');
      if(!controller.signal.aborted) setData(value);
    }).catch(()=>{if(!controller.signal.aborted)setError(true);});
    return ()=>controller.abort();
  },[revision,analysis?.id,profile.updated_at]);
  const visual = inspirationAnalytics(analysis,profile.images);
  const rows = observedAttributes(visual.observations,field).slice(0,5);
  const supporting = rows.length ? profile.images.filter(image=>rows[0].evidence_image_ids.includes(image.id)).slice(0,3) : [];
  const corrections = Object.entries(feedbackLabels).map(([kind,attribute])=>({attribute,count:data?.shopping.feedback_counts[kind] || 0})).filter(row=>row.count>0);
  const stats = [
    [profile.images.length,'Saved inspirations','Your private moodboard'],
    [visual.observations.length,'Analyzed looks',`of ${profile.images.length} saved inspirations`],
    [data ? data.qloo.brands.length : '—','Qloo brand discoveries',data?.qloo.stale ? 'Earlier run · update needed' : data ? 'In your saved Qloo run' : error ? 'Could not load' : 'Loading saved counts'],
    [data ? data.shopping.refined_products : '—','Products refined',data ? `${data.shopping.saved_products} saved product bookmarks` : error ? 'Could not load' : 'Loading saved counts'],
  ];
  return <section id="taste-analytics" className="taste-analytics profile-section" aria-labelledby="taste-analytics-title"><div className="profile-section-heading"><div><Eyebrow>Your taste, at a glance</Eyebrow><h2 id="taste-analytics-title">See the patterns in you.</h2><p>Explore the looks you save, the connections Qloo finds, and the feedback shaping your next discoveries.</p></div><BarChart3 size={24} aria-hidden="true" /></div>
    <div className="taste-stat-strip">{stats.map(([value,label,note])=><div key={label}><strong>{value}</strong><span>{label}</span><small>{note}</small></div>)}</div>
    {error && <div className="taste-analytics-error" role="status"><p>Shopping and Qloo counts couldn’t load. Your inspiration charts are still available.</p><button onClick={()=>setRevision(value=>value+1)}><RefreshCw size={14} /> Retry analytics</button></div>}
    <div className="taste-chart-grid">
      <Card className="taste-chart"><div className="taste-chart-heading"><Eyebrow>From your inspiration images</Eyebrow><span className="profile-source-label">AI observations</span></div><h3>Your inspiration mix.</h3><div className="taste-chart-tabs" role="group" aria-label="Choose inspiration chart">{dimensions.map(([value,label])=><button key={value} aria-pressed={field===value} onClick={()=>setField(value)}>{label}</button>)}</div>
        {rows.length>0 ? <><Bars rows={rows} maximum={visual.observations.length} onSelect={onSelect} /><p className="taste-chart-note">Each bar counts distinct analyzed looks. A look can appear in several bars. Select a bar to view its inspirations.</p></> : <div className="taste-chart-start"><p>{visual.observations.length ? 'No attributes were identified for this category in the current image observations.' : 'Generate or update your style analysis to reveal patterns in your saved looks.'}</p><a href="#style-overview">Go to style analysis <ArrowUpRight size={15} /></a></div>}
        {supporting.length>0 && <div className="taste-supporting"><span>Behind “{rows[0].attribute}”</span><div>{supporting.map(image=><button key={image.id} aria-label={`View ${image.filename} in supporting inspirations`} onClick={()=>onSelect(rows[0].evidence_image_ids)}><PrivateImage image={image} retryable={false} /></button>)}</div></div>}
        {analysis?.completed_at && <p className="taste-chart-source">Source: saved Gemini image observations · {new Date(analysis.completed_at).toLocaleDateString()}{analysis.stale ? ' · earlier analysis; only unchanged images counted' : ''}</p>}
      </Card>
      {data && <QlooChart data={data.qloo} />}
      {visual.colors.length>0 && <Card className="taste-chart"><div className="taste-chart-heading"><Eyebrow>The shades you save</Eyebrow><span className="profile-source-label">AI observations</span></div><h3>Your color balance.</h3><ColorChart rows={visual.colors} onSelect={onSelect} /><p className="taste-chart-source">Source: {visual.observations.length} unchanged, analyzed inspiration images · saved analysis</p></Card>}
      {data && <Card className="taste-chart"><div className="taste-chart-heading"><Eyebrow>Learning from your shopping</Eyebrow><span className="profile-source-label">You selected</span></div><h3>How you’re refining your taste.</h3>{corrections.length ? <><Bars rows={corrections} maximum={data.shopping.refined_products} unit="products" /><p className="taste-chart-note">Latest correction per product, across your saved feedback. These are preference counts, not clicks or purchase history.</p><p className="taste-chart-source">Source: your extension feedback{data.shopping.last_feedback_at ? ` · last updated ${new Date(data.shopping.last_feedback_at).toLocaleDateString()}` : ''}</p></> : <div className="taste-chart-start"><span className="taste-start-icon"><BarChart3 size={26} /></span><p>Your first correction starts the story. Tell Muselly “More like this” or what feels off while shopping.</p><a href="/extension">Open the extension guide <ArrowUpRight size={15} /></a></div>}</Card>}
    </div>
  </section>;
}
