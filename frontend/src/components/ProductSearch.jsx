import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Search, SlidersHorizontal } from 'lucide-react';
import { Button, Card, Eyebrow } from './ui';
import { apiRequest } from '../lib/supabase';
import { readCache, writeCache } from '../lib/sessionCache';
import { readSavedSearch, saveSearch } from '../lib/savedSearch';
import '../styles/search.css';

const initialFilters = { category: '', color: '', size: '', fit: '', occasion: '', min_price: '', max_price: '', currency: '', sort: 'personalized' };
const money = value => new Intl.NumberFormat(value.currency === 'INR' ? 'en-IN' : 'en-US', { style: 'currency', currency: value.currency }).format(Number(value.amount));
const categoryOptions = [['dresses','Dresses & gowns'],['tops','Tops'],['bottoms','Bottoms'],['outerwear','Outerwear'],['shoes','Shoes'],['bags','Bags'],['accessories','Accessories']];

function Select({ label, name, value, onChange, options, disabled }) {
  return <label className="search-field" htmlFor={`search-${name}`}><span>{label}</span><select id={`search-${name}`} name={name} value={value} disabled={disabled} onChange={onChange}>{options.map(([id, text]) => <option key={id} value={id}>{text}</option>)}</select></label>;
}

function Product({ item }) {
  const [brokenImage, setBrokenImage] = useState(false);
  useEffect(() => setBrokenImage(false), [item.image]);
  return <Card as="article" className="shopping-product">
    <a className="shopping-product-image" href={item.url} target="_blank" rel="noopener noreferrer" aria-label={`View ${item.title} at ${item.source_name} (opens in a new tab)`}>{brokenImage ? <span>Image unavailable</span> : <img src={item.image} alt={item.title} loading="lazy" referrerPolicy="no-referrer" onError={() => setBrokenImage(true)} />}</a>
    <div className="shopping-product-copy"><p className="shopping-product-source">{item.source_name}</p><h3>{item.title}</h3><p className="shopping-product-price">{item.price.estimated ? 'Approx. ' : ''}{money(item.price)}</p>{item.price.estimated && <p className="shopping-product-original">{money(item.original_price)} at the store</p>}
      <p className="shopping-product-options">{Object.values(item.selected_options).filter(value => value !== 'Default Title').join(' · ')}</p>
      <span className="profile-source-label">{item.match_label}</span>
      <details className="shopping-product-reasons"><summary>Why it matches</summary><ul>{item.why.map((reason, i) => <li key={i}>{reason}</li>)}</ul></details>
      <a className="text-link" href={item.url} target="_blank" rel="noopener noreferrer">View on {item.source_name} <ArrowUpRight size={15} /></a>
    </div>
  </Card>;
}

export default function ProductSearch({ initialQuery = '', ownerId }) {
  const cached = useRef(readCache(ownerId, 'sources'));
  const draft = useRef(readSavedSearch(ownerId));
  const sameQuery = !initialQuery || initialQuery === draft.current?.query || initialQuery === draft.current?.entryQuery;
  const [sources, setSources] = useState(cached.current?.value.sources || []);
  const [selected, setSelected] = useState(draft.current?.selected || cached.current?.value.default_source_ids || []);
  const [query, setQuery] = useState(sameQuery ? draft.current?.query || initialQuery : initialQuery);
  const [filters, setFilters] = useState(sameQuery ? draft.current?.filters || initialFilters : initialFilters);
  const [result, setResult] = useState(sameQuery ? draft.current?.result ?? null : null);
  const [restored, setRestored] = useState(Boolean(sameQuery && draft.current?.result));
  const [loading, setLoading] = useState(!cached.current);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const active = useRef(true);
  const pending = useRef(null);
  const resultsHeading = useRef(null);

  useEffect(() => { active.current = true; return () => { active.current = false; pending.current?.abort(); }; }, []);
  useEffect(() => {
    const controller = new AbortController();
    const entry = readCache(ownerId, 'sources');
    if (entry?.fresh && revision === 0) { setLoading(false); return; }
    setLoading(!entry); setError('');
    apiRequest('/api/search/sources', { signal: controller.signal }).then(data => {
      if (controller.signal.aborted || !active.current) return;
      if (!Array.isArray(data.sources)) throw new Error('Unable to load stores.');
      setSources(data.sources);
      setSelected(previous => draft.current ? previous.filter(id => data.sources.some(source => source.id === id)) : data.default_source_ids);
      writeCache(ownerId, 'sources', data);
    }).catch(failure => {
      if (!controller.signal.aborted && active.current) setError(failure.status === 401 ? 'Please sign in again to search your stores.' : 'We couldn’t load the shopping sources. Please try again.');
    }).finally(() => { if (!controller.signal.aborted && active.current) setLoading(false); });
    return () => controller.abort();
  }, [revision, ownerId]);
  useEffect(() => {
    if (!loading && (sameQuery || result)) saveSearch(ownerId, { query, filters, selected, result,
      entryQuery: window.location.pathname === '/explore' ? new URLSearchParams(window.location.search).get('q') || initialQuery : initialQuery });
  }, [ownerId, loading, query, filters, selected, result, initialQuery, sameQuery]);

  function change(event) { setFilters(previous => ({ ...previous, [event.target.name]: event.target.value })); }
  function toggle(id) { setSelected(previous => previous.includes(id) ? previous.filter(value => value !== id) : [...previous, id]); }
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    if (!selected.length) { setError('Choose at least one store.'); return; }
    setBusy(true); setError('');
    const controller = new AbortController();
    pending.current = controller;
    const timeout = setTimeout(() => controller.abort(), 35000);
    try {
      const data = await apiRequest('/api/search/products', { method: 'POST', signal: controller.signal,
        body: { query: query.trim(), source_ids: selected,
          ...filters, category: filters.category || null, occasion: filters.occasion || null, currency: filters.currency || null,
          min_price: filters.min_price === '' ? null : filters.min_price,
          max_price: filters.max_price === '' ? null : filters.max_price } });
      if (active.current && !controller.signal.aborted) {
        // Persist before rendering so leaving immediately cannot lose this response.
        saveSearch(ownerId, { query: query.trim(), filters, selected, result: data, entryQuery: query.trim() });
        if (window.location.pathname === '/explore') {
          const url = new URL(window.location.href);
          url.searchParams.set('q', query.trim());
          window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
        }
        setQuery(query.trim()); setResult(data); setRestored(false);
        queueMicrotask(() => resultsHeading.current?.focus({ preventScroll: true }));
      }
    } catch (failure) {
      if (active.current) setError(failure.name === 'AbortError' ? 'Search took too long. Please try again.' : failure.status === 429 ? 'Please wait a moment before searching again.' : failure.message || 'Search is temporarily unavailable. Please try again.');
    } finally { clearTimeout(timeout); if (active.current) setBusy(false); }
  }

  const applied = result?.applied_filters;
  const failedSources = result?.source_statuses.filter(source => source.status !== 'ok') || [];
  return <section id="shopping-search" className="profile-section shopping-search" aria-labelledby="shopping-title">
    <div className="profile-section-heading"><div><Eyebrow>From inspiration to your next outfit</Eyebrow><h2 id="shopping-title">Find your next favorite.</h2><p>Search real products and bring your own taste to the results.</p></div></div>
    <Card className="shopping-search-form"><form onSubmit={submit}>
      <label htmlFor="shopping-query" className="search-query-label">What are you looking for?</label>
      <div className="shopping-query-row"><input id="shopping-query" name="query" value={query} onChange={event => setQuery(event.target.value)} placeholder="A midi dress for an evening party" minLength={2} maxLength={300} required disabled={busy || loading} /><Button type="submit" disabled={loading || busy || !sources.length}><Search size={17} />{busy ? 'Searching stores…' : 'Find products'}</Button></div>
      <details className="shopping-filters"><summary><SlidersHorizontal size={16} /> Refine your search</summary><p>Optional filters override details in your request. Occasion guides ranking; size, color, fit, and budget filter products.</p><div className="shopping-filter-grid">
        <Select label="Category" name="category" value={filters.category} onChange={change} disabled={busy} options={[[ '', 'From my request'],['all','Any category'],...categoryOptions]} />
        <Select label="Color" name="color" value={filters.color} onChange={change} disabled={busy} options={[[ '', 'From my request'],['any','Any color'],...['black','white','cream','blue','pink','red','green','purple','brown','beige','grey','yellow','orange','pastels','neutrals'].map(c => [c,c.charAt(0).toUpperCase()+c.slice(1)])]} />
        <label className="search-field" htmlFor="search-size"><span>Size, as listed by the store</span><input id="search-size" name="size" value={filters.size} onChange={change} maxLength={30} placeholder="e.g. M or 8" disabled={busy} /></label>
        <Select label="Fit" name="fit" value={filters.fit} onChange={change} disabled={busy} options={[[ '', 'From my request'],...['relaxed','fitted','oversized','tailored','bodycon','a-line','wide-leg','slim','straight'].map(f => [f,f])]} />
        <Select label="Occasion" name="occasion" value={filters.occasion} onChange={change} disabled={busy} options={[[ '', 'From my request'],...['party','wedding','work','casual','active'].map(o => [o,o])]} />
        <Select label="Currency" name="currency" value={filters.currency} onChange={change} disabled={busy} options={[[ '', 'From request, otherwise INR'],['INR','INR (₹)'],['USD','USD ($)']]} />
        <label className="search-field" htmlFor="search-min-price"><span>Minimum price</span><input id="search-min-price" name="min_price" type="number" min="0" max="10000000" step="0.01" value={filters.min_price} onChange={change} placeholder="From request" disabled={busy} /></label>
        <label className="search-field" htmlFor="search-max-price"><span>Maximum price</span><input id="search-max-price" name="max_price" type="number" min="0.01" max="10000000" step="0.01" value={filters.max_price} onChange={change} placeholder="From request" disabled={busy} /></label>
        <Select label="Ranking" name="sort" value={filters.sort} onChange={change} disabled={busy} options={[[ 'personalized','My taste'],['relevance','Search relevance'],['price_asc','Price: low to high'],['price_desc','Price: high to low']]} />
      </div><button type="button" className="sign-out-link" disabled={busy} onClick={() => setFilters(initialFilters)}>Reset filters</button></details>
      <fieldset className="shopping-source-picker" disabled={busy || loading}><legend>Connected brand stores · live product results</legend><div>{sources.filter(source => source.mode === 'catalog').map(source => <label key={source.id}><input type="checkbox" checked={selected.includes(source.id)} onChange={() => toggle(source.id)} />{source.name}{source.qloo_affinity && <span className="profile-source-label">Qloo affinity</span>}</label>)}</div></fieldset>
      <details className="shopping-retailer-picker"><summary>Search your retailer websites</summary><p>These stores open in a new tab. Use the store’s own filters for budget, size, and color.</p><fieldset disabled={busy || loading}><legend className="sr-only">Retailer website searches</legend><div>{sources.filter(source => source.mode === 'website').map(source => <label key={source.id}><input type="checkbox" checked={selected.includes(source.id)} onChange={() => toggle(source.id)} />{source.name}</label>)}</div></fieldset></details>
      {loading && <p role="status">Loading your shopping sources…</p>}
      {busy && <p role="status">Checking current products and available variants…</p>}
      {error && <p className="search-error" role="alert">{error}</p>}
      {!loading && !sources.length && <Button type="button" onClick={() => setRevision(v => v + 1)}>Reload stores</Button>}
    </form></Card>
    {result && <div className="shopping-results" aria-busy={busy}>
      {restored && <p className="shopping-conversion" role="status">Saved search from {new Date(result.searched_at).toLocaleString()}. Search again to update prices, availability, and taste matches.</p>}
      <div className="profile-section-heading"><div><h3 ref={resultsHeading} tabIndex={-1}>Your search results.</h3><p role="status">{result.products.length} matching product{result.products.length === 1 ? '' : 's'}{applied.sort === 'personalized' ? ', ranked for your taste' : ''}.</p></div></div>
      <div className="profile-chips shopping-applied">{[applied.category, applied.color, applied.size && `Size ${applied.size}`, applied.fit, applied.occasion, applied.min_price && `From ${money({ amount:applied.min_price,currency:applied.currency })}`, applied.max_price && `Up to ${money({amount:applied.max_price,currency:applied.currency})}`].filter(Boolean).map(text => <span key={text}>{text}</span>)}</div>
      {result.exchange && <p className="shopping-conversion">Converted prices are estimates using {result.exchange.source} rates dated {result.exchange.date}. Original store prices are shown on each product.</p>}
      {failedSources.length > 0 && <p className="search-error" role="status">Some stores couldn’t respond: {failedSources.map(source => source.name).join(', ')}. Results from the other selected stores are shown.</p>}
      {!result.products.length && <Card className="shopping-empty"><h3>{result.status === 'external_only' ? 'Continue your search on a retailer website.' : 'No products matched these filters.'}</h3><p>{result.status === 'external_only' ? 'Select a connected brand store above to see product cards here, or open a retailer below.' : 'Try a broader request, a different store, size, or budget. Your saved dislikes are also applied.'}</p>{result.status !== 'external_only' && <a className="text-link" href="/taste-test?edit=1&question=q15">Review preferences <ArrowUpRight size={14} /></a>}</Card>}
      <div className="shopping-products">{result.products.map(item => <Product key={item.id} item={item} />)}</div>
      {result.products.length > 0 && <p className="profile-meta">Availability checked {new Date(result.searched_at).toLocaleString()}. Showing a limited selection from each connected store.</p>}
      {result.retailer_links.length > 0 && <Card className="shopping-retailer-links"><h3>Continue on your retailers.</h3><p>Open the same product search on your selected shopping sites.</p><div>{result.retailer_links.map(link => <a className="button button--secondary" key={link.id} href={link.url} target="_blank" rel="noopener noreferrer">Search {link.name} <ArrowUpRight size={15} /></a>)}</div></Card>}
    </div>}
  </section>;
}
