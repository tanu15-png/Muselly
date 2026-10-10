import { useEffect, useState } from 'react';
import { ArrowRight, ArrowLeft, ArrowUpRight, Heart, Sparkles, Globe2, Images, SlidersHorizontal, Menu, X, Check, Plus, ShoppingBag, MousePointer2, LockKeyhole, ChevronDown } from 'lucide-react';
import { Brand, Button, Card, Eyebrow, SectionHeading, TextLink } from './components/ui';
import StylePreview from './components/StylePreview';
import { AuthProvider, useAuth } from './components/AuthProvider';
import SignIn from './components/SignIn';
import AuthCallback from './components/AuthCallback';
import { apiRequest } from './lib/supabase';

const links = [['How it works', 'how-it-works'], ['For you', 'for-you'], ['Extension', 'extension'], ['FAQs', 'faqs']];
const tasteChoices = [
  { id: 'romantic', title: 'Soft & romantic', subtitle: 'Flowing shapes, delicate details', image: 'romantic-dress', alt: 'Brown flowing dress with soft cream sleeves' },
  { id: 'classic', title: 'Modern classic', subtitle: 'Clean lines, timeless layers', image: 'modern-classic', alt: 'Burgundy leather jacket with black tailored trousers' },
  { id: 'casual', title: 'Relaxed & effortless', subtitle: 'Easy denim, cozy layers', image: 'soft-casual', alt: 'Soft blue cardigan with relaxed wide-leg denim' },
  { id: 'chic', title: 'A little bold', subtitle: 'Statement shapes, city energy', image: 'city-chic', alt: 'Black fitted top, brown mini skirt, and tall boots' },
];

function Navigation() {
  const [open, setOpen] = useState(false);
  const { user } = useAuth();
  useEffect(() => {
    const close = event => { if (event.key === 'Escape') { setOpen(false); document.getElementById('menu-toggle')?.focus(); } };
    if (open) window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [open]);
  return <header className="site-header"><div className="container nav-bar"><Brand /><nav className="desktop-nav" aria-label="Main navigation">{links.map(([label, id]) => <a key={id} href={`#${id}`}>{label}</a>)}</nav><div className="nav-actions"><Button href="/sign-in" variant="secondary" className="sign-in-button">{user ? 'My style' : 'Sign in'}</Button><button id="menu-toggle" className="icon-button mobile-toggle" aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open} aria-controls="mobile-navigation" onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button></div></div>{open && <nav id="mobile-navigation" className="mobile-nav" aria-label="Mobile navigation">{links.map(([label, id]) => <a key={id} href={`#${id}`} onClick={() => setOpen(false)}>{label}<ArrowUpRight size={16} /></a>)}<a href="/sign-in">{user ? 'My style' : 'Sign in'}<ArrowUpRight size={16} /></a></nav>}</header>;
}

function Doodle({ className = '' }) {
  return <svg className={`doodle ${className}`} viewBox="0 0 80 55" fill="none" aria-hidden="true"><path d="M73 5C44 0 22 9 26 26c2 13 19 10 15 0C37 17 14 27 6 47m0 0 16-5M6 47l-1-16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

function Hero() {
  return <section className="hero container" aria-labelledby="hero-title"><div className="hero-copy"><h1 id="hero-title">Discover fashion<br />that feels like <em>you.</em></h1><p className="hero-description">Upload your inspirations, take a quick taste test, and let our AI understand your style. Get personalized outfit recommendations from your favorite shopping sites — anywhere on the web.</p><div className="hero-action"><Button href="/sign-in" className="button--large">Get started <ArrowRight size={21} /></Button><span className="handwritten cta-note">A little inspiration.<br />A whole lot of you.<Doodle /></span></div><div className="hero-benefits">{[[Globe2, 'Style that goes', 'where you go']].map(([Icon, line1, line2]) => <div key={line1}><span className="icon-tile"><Icon size={18} /></span><span>{line1}<br />{line2}</span></div>)}</div></div><div className="hero-art" aria-label="Fashion inspirations and an example Style DNA profile"><div className="art-wash" /><span className="handwritten inspiration-note">Turn your saved inspo…<Doodle /></span><div className="photo-frame photo-frame--one"><img src="/images/soft-casual.png" alt="Relaxed blue cardigan and denim outfit inspiration" /></div><div className="photo-frame photo-frame--two"><img src="/images/modern-classic.png" alt="Modern burgundy leather and tailored outfit inspiration" /></div><div className="photo-frame photo-frame--three"><img src="/images/romantic-dress.png" alt="Romantic brown dress and cream blouse outfit inspiration" /><span className="photo-heart"><Heart size={15} /></span></div><span className="art-sparkle art-sparkle--one" aria-hidden="true">✧</span><span className="art-sparkle art-sparkle--two" aria-hidden="true">✧</span><StylePreview className="hero-style-preview" /><span className="handwritten dna-note">…into your own<br />style story<Doodle /></span><Card className="browse-note"><span className="icon-tile"><Globe2 size={23} /></span><div><strong>Your taste, beyond this tab.</strong><p>A little style companion for your browser.</p><a href="#extension">Meet the extension <ArrowUpRight size={13} /></a></div></Card></div></section>;
}

function Retailers() {
  return <div className="retailer-band"><div className="container"><p>Inspiration from everywhere. A style that’s yours.</p><div className="retailer-names" aria-label="Retailers planned for future integrations">{['amazon', 'Flipkart', 'meesho', 'Myntra', 'AJIO', 'URBANIC', 'savana'].map(name => <span key={name}>{name}</span>)}</div><small>Retailer integrations are planned. Availability will depend on supported product sources.</small></div></div>;
}

function HowItWorks() {
  const steps = [
    { number: '01', Icon: Images, title: 'Show us what you love', text: 'Start with a visual taste test. Later, add the outfits and little details you’ve been saving.', kind: 'inspo' },
    { number: '02', Icon: Sparkles, title: 'Meet your Style DNA', text: 'Your colors, silhouettes, and aesthetics, brought together in a profile you can make your own.', kind: 'dna' },
    { number: '03', Icon: ShoppingBag, title: 'Find your next favorite', text: 'Describe what you’re looking for. Discover pieces that fit your taste, occasion, and budget.', kind: 'search' },
  ];
  return <section id="how-it-works" className="section container"><SectionHeading centered eyebrow="A little inspiration goes a long way" title={<>Your style. Three simple steps.</>}>Less endless scrolling. More “that’s so me.”</SectionHeading><div className="steps-grid">{steps.map(({ number, Icon, title, text, kind }) => <Card className="step-card" key={number}><div className={`step-visual step-visual--${kind}`} aria-hidden="true">{kind === 'inspo' ? <><img src="/images/city-chic.png" alt="" /><img src="/images/romantic-dress.png" alt="" /><span className="floating-icon"><Heart size={20} /></span></> : kind === 'dna' ? <div className="mini-dna"><Sparkles size={21} /><span>Soft. Earthy. Timeless.</span><div className="mini-palette"><i /><i /><i /><i /></div><div className="mini-chips"><span>Romantic</span><span>Relaxed</span></div></div> : <div className="mini-search"><div><span>Something for a café date</span><ArrowRight size={16} /></div><img src="/images/romantic-dress.png" alt="" /><img src="/images/soft-casual.png" alt="" /></div>}</div><div className="step-card__copy"><div className="step-number"><span>{number}</span><Icon size={19} /></div><h3>{title}</h3><p>{text}</p></div></Card>)}</div><p className="section-footnote">A look at what we’re building. Start with the taste-test preview today.</p></section>;
}

function ForYou() {
  return <section id="for-you" className="section for-you-section"><div className="container for-you-grid"><div className="editorial-images"><img className="editorial-main" src="/images/romantic-dress.png" alt="Romantic flowing dress outside a flower-filled café" loading="lazy" /><img className="editorial-detail" src="/images/burgundy-detail.png" alt="Delicate lace-up detail on a burgundy evening dress" loading="lazy" /><span className="editorial-caption">The details make it yours.</span><span className="editorial-stamp"><Heart size={18} /> A little more you</span></div><div className="for-you-copy"><SectionHeading eyebrow="For your very own kind of beautiful" title={<>Trends come and go.<br />Your taste is <em>personal.</em></>}>That outfit you screenshotted. The color you always reach for. The pieces that just feel right. They’re all part of your style story.</SectionHeading><div className="feature-list">{[[Heart, 'Beyond the trend', 'Recommendations shaped around your preferences, with room to change your mind.'], [SlidersHorizontal, 'You’re always the stylist', 'An editable taste profile, because nobody knows you better than you.'], [Sparkles, 'A reason behind every match', 'Understand the palette, cut, and details that make a piece feel like you.']].map(([Icon, title, body]) => <div key={title}><span className="icon-tile"><Icon size={20} /></span><div><h3>{title}</h3><p>{body}</p></div></div>)}</div></div></div></section>;
}

function Extension() {
  return <section id="extension" className="section container extension-section"><div className="extension-copy"><Eyebrow icon>Meet your browsing companion</Eyebrow><h2>Same taste.<br /><em>Every new tab.</em></h2><p>Your inspirations shouldn’t live in one place. Bring your Muselly style along while you browse supported shopping sites.</p><ul className="extension-features"><li><Check size={17} /> Save an image that catches your eye</li><li><Check size={17} /> Find pieces with a similar feel</li><li><Check size={17} /> See what fits your personal taste</li></ul><Button variant="secondary" disabled><Globe2 size={18} /> Get Extension <span className="coming-soon">Coming soon</span></Button><p className="extension-caption">For Chrome. Site support will vary.</p></div><div className="browser-preview" aria-label="Illustrative preview of the future Muselly extension"><div className="browser-top"><div className="browser-dots"><i /><i /><i /></div><span><LockKeyhole size={10} /> your-favorite-shop.com</span><Plus size={13} /></div><div className="browser-content"><div className="sample-shop"><div className="sample-shop-heading">A few new favorites <ShoppingBag size={17} /></div><div className="sample-shop-grid"><div><img src="/images/romantic-dress.png" alt="Flowing brown dress inspiration" loading="lazy" /><span>Soft silhouettes</span></div><div><img src="/images/evening-dress.png" alt="Burgundy evening dress inspiration" loading="lazy" /><span>Evening details</span></div></div><span className="preview-label">Illustrative shopping preview</span></div><Card className="extension-popup"><Brand /><span className="preview-label">Extension preview</span><h3>A little more your style.</h3><div className="popup-inspiration"><img src="/images/romantic-dress.png" alt="Example selected outfit" loading="lazy" /><div><span>Your current inspiration</span><strong>Soft shapes.<br />Warm, earthy tones.</strong></div></div><div className="popup-demo-control"><Sparkles size={16} /> Find similar <ArrowRight size={15} /></div><div className="popup-demo-control popup-demo-control--secondary"><Heart size={16} /> Save to Muselly</div><p>Your Style DNA, wherever you browse.</p></Card></div><span className="browser-cursor" aria-hidden="true"><MousePointer2 size={28} /></span></div></section>;
}

const faqs = [
  ['What is Muselly?', 'Muselly is a personal fashion discovery companion. We’re building a way to turn your visual inspirations and preferences into an editable Style DNA, then use it to find pieces that feel like you.'],
  ['How does the taste test work?', 'Sign in with email or Google, then choose the outfit aesthetics you’re drawn to. The full taste test will explore your colors, fits, occasions, and dislikes, with optional inspiration uploads. There are no right or wrong answers.'],
  ['Can I use my Pinterest inspirations?', 'Manual uploads and saving individual images through the extension are planned. Connecting a Pinterest account or board is a future enhancement and isn’t available yet.'],
  ['Which shopping sites will Muselly support?', 'We plan to start with one or two reliable product sources, then expand. The retailer names shown here are planned integrations, not a promise of live catalogs. Extension features will also depend on site-specific support.'],
  ['Is the Chrome extension available?', 'Not yet. The extension is coming soon. It will share your Muselly profile and help you save inspirations, find similar pieces, and evaluate products on supported pages.'],
  ['What happens to my taste-test answers?', 'Your selected aesthetics are saved to your signed-in account when you continue. You can return to the taste test to edit them. Image uploads and AI Style DNA are still being built.'],
];

function FAQs() {
  return <section id="faqs" className="section faq-section container"><SectionHeading eyebrow="A few things you might be wondering" title={<>Curiosity looks good<br />on <em>you.</em></>}>A little clarity before you get started.</SectionHeading><div className="faq-list">{faqs.map(([question, answer]) => <details key={question}><summary>{question}<ChevronDown size={18} aria-hidden="true" /></summary><p>{answer}</p></details>)}</div></section>;
}

function Footer() {
  return <footer className="site-footer"><div className="container footer-main"><div><Brand /><p>Your taste, everywhere you shop.</p></div><nav aria-label="Footer navigation">{links.map(([name, id]) => <a key={id} href={`/#${id}`}>{name}</a>)}</nav><span className="footer-note">Made for your kind of beautiful.</span></div><div className="container footer-bottom"><span>© {new Date().getFullYear()} Muselly</span><span>Phase 1 preview · A style story in the making</span></div></footer>;
}

function Landing() {
  return <><Navigation /><main id="main-content"><Hero /><Retailers /><HowItWorks /><ForYou /><Extension /><FAQs /><section className="final-cta"><div className="container"><Sparkles size={26} aria-hidden="true" /><h2>Find your style.<br />Fall in love with <em>your taste.</em></h2><p>Your next favorite starts with a little inspiration.</p></div></section></main><Footer /></>;
}

function EntryHeader() {
  return <header className="entry-header container"><Brand /><a className="back-link" href="/"><ArrowLeft size={16} /> Back to Muselly</a></header>;
}

function TasteTest() {
  const [selected, setSelected] = useState([]);
  const [complete, setComplete] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [loadFailed, setLoadFailed] = useState(false);
  useEffect(() => {
    document.title = 'Your taste test — Muselly';
    const controller = new AbortController();
    setLoading(true);
    setLoadFailed(false);
    setError('');
    apiRequest('/api/taste-test', { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setSelected(data.selected_styles); })
      .catch(failure => {
        if (!controller.signal.aborted) {
          setError(failure.message || 'Unable to load your taste test. Please try again.');
          setLoadFailed(true);
        }
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [revision]);
  async function saveChoices() {
    setSaving(true);
    setError('');
    try {
      await apiRequest('/api/taste-test', { method: 'PUT', body: { selected_styles: selected } });
      setComplete(true);
      window.scrollTo({ top: 0, behavior: 'instant' });
    } catch (failure) { setError(failure.message || 'Unable to save your choices. Please try again.'); }
    finally { setSaving(false); }
  }
  if (loading || loadFailed) return <><EntryHeader /><main id="main-content" className="taste-page container"><p role="status">{loading ? 'Loading your taste test…' : error}</p>{loadFailed && <div className="entry-actions"><Button onClick={() => setRevision(value => value + 1)}>Try again</Button><Button href="/sign-in" variant="secondary">Return to your account</Button></div>}</main></>;
  const toggle = id => setSelected(items => items.includes(id) ? items.filter(item => item !== id) : [...items, id]);
  return <><EntryHeader /><main id="main-content" className="taste-page container"><Eyebrow icon>Your style story starts here</Eyebrow>{complete ? <div className="taste-result"><span className="result-icon"><Check size={26} /></span><h1>A little glimpse of <em>you.</em></h1><p>You’re drawn to {selected.map(id => tasteChoices.find(choice => choice.id === id).title.toLowerCase()).join(' and ')}. This is just a starting point — your taste can be more than one thing.</p><div className="result-images">{tasteChoices.filter(choice => selected.includes(choice.id)).map(choice => <img key={choice.id} src={`/images/${choice.image}.png`} alt={choice.alt} />)}</div><Card className="entry-notice"><Sparkles size={20} /><div><strong>Your taste is saved.</strong><p>You can return and edit these choices anytime. Inspiration uploads and AI Style DNA are still being built.</p></div></Card><div className="entry-actions"><Button onClick={() => setComplete(false)} variant="secondary"><ArrowLeft size={16} /> Edit my choices</Button><Button href="/">Explore Muselly <ArrowRight size={17} /></Button></div></div> : <><div className="taste-title"><span className="step-pill">Taste-test preview</span><h1>Which looks feel like <em>you?</em></h1><p>Go with your first instinct. Choose one, or a few — your style doesn’t have to fit in a box.</p></div><fieldset className="taste-options" disabled={saving}><legend className="sr-only">Choose the styles you’re drawn to</legend>{tasteChoices.map(choice => <label className={`taste-choice ${selected.includes(choice.id) ? 'taste-choice--selected' : ''}`} key={choice.id}><input type="checkbox" checked={selected.includes(choice.id)} onChange={() => toggle(choice.id)} /><div className="taste-choice__photo"><img src={`/images/${choice.image}.png`} alt={choice.alt} /><span className="choice-check" aria-hidden="true">{selected.includes(choice.id) ? <Check size={18} /> : <Plus size={18} />}</span></div><div className="taste-choice__label"><h2>{choice.title}</h2><p>{choice.subtitle}</p></div></label>)}</fieldset><div className="taste-bottom"><div><p className="selection-status" role="status">{selected.length ? `${selected.length} ${selected.length === 1 ? 'look' : 'looks'} selected` : 'Choose at least one look to continue'}</p><span>Your choices are saved to your account when you continue.</span></div><Button disabled={!selected.length || saving} onClick={saveChoices}>{saving ? 'Saving…' : 'Continue'} <ArrowRight size={18} /></Button></div>{error && <p className="taste-error" role="alert">{error}</p>}</>}</main><footer className="entry-footer">Your taste is personal. There’s no wrong answer.</footer></>;
}

function TasteTestGate() {
  const { status, user, error, retry } = useAuth();
  useEffect(() => {
    if (['signed-out', 'unconfigured'].includes(status)) window.location.replace('/sign-in');
  }, [status]);
  if (status === 'signed-in' && user) return <TasteTest key={user.id} />;
  return <><EntryHeader /><main id="main-content" className="taste-page container"><p role="status">{status === 'error' ? error : 'Checking your sign-in…'}</p>{status === 'error' && <div className="entry-actions"><Button onClick={retry}>Try again</Button><Button href="/sign-in" variant="secondary">Go to sign in</Button></div>}</main></>;
}

export default function App() {
  const path = window.location.pathname.replace(/\/$/, '') || '/';
  return <AuthProvider><a className="skip-link" href="#main-content">Skip to content</a>{path === '/' ? <Landing /> : path === '/taste-test' ? <TasteTestGate /> : path === '/sign-in' ? <SignIn header={<EntryHeader />} /> : path === '/auth/callback' ? <AuthCallback header={<EntryHeader />} /> : <><EntryHeader /><main id="main-content" className="not-found container"><h1>This page is still on the moodboard.</h1><Button href="/">Back to Muselly <ArrowRight size={18} /></Button></main></>}</AuthProvider>;
}

