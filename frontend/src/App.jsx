import ResilientImage from './components/ResilientImage';
import { lazy, Suspense, useEffect, useState } from 'react';
import { ArrowRight, ArrowLeft, ArrowUpRight, Heart, Sparkles, Globe2, Images, SlidersHorizontal, Menu, X, Check, Plus, ShoppingBag, Search, MousePointer2, LockKeyhole, ChevronDown } from 'lucide-react';
import { Brand, Button, Card, Eyebrow, SectionHeading, TextLink } from './components/ui';
import { AuthProvider, useAuth } from './components/AuthProvider';
import SignIn from './components/SignIn';
import AuthCallback from './components/AuthCallback';
import TasteTest from './components/TasteTest';
import StylePreview from './components/StylePreview';
import './styles/explore.css';
import { useNavigation } from './lib/useNavigation';
import { navigate } from './lib/navigation';
const ExplorePage = lazy(() => import('./components/ExplorePage'));
const TasteDashboard = lazy(() => import('./components/TasteDashboard'));

const links = [['How it works', 'how-it-works'], ['FAQs', 'faqs']];

function Navigation() {
  const [open, setOpen] = useState(false);
  const { user } = useAuth();
  useEffect(() => {
    const close = event => { if (event.key === 'Escape') { setOpen(false); document.getElementById('menu-toggle')?.focus(); } };
    if (open) window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [open]);
  return <header className="site-header"><div className="container nav-bar"><Brand /><nav className="desktop-nav" aria-label="Main navigation">{links.map(([label, id]) => <a key={id} href={`#${id}`}>{label}</a>)}</nav><div className="nav-actions"><Button href={user ? "/dashboard" : "/sign-in"} variant="secondary" className="sign-in-button">{user ? 'My style' : 'Sign in'}</Button><button id="menu-toggle" className="icon-button mobile-toggle" aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open} aria-controls="mobile-navigation" onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button></div></div>{open && <nav id="mobile-navigation" className="mobile-nav" aria-label="Mobile navigation">{links.map(([label, id]) => <a key={id} href={`#${id}`} onClick={() => setOpen(false)}>{label}<ArrowUpRight size={16} /></a>)}<a href={user ? "/dashboard" : "/sign-in"}>{user ? 'My style' : 'Sign in'}<ArrowUpRight size={16} /></a></nav>}</header>;
}

function Doodle({ className = '' }) {
  return <svg className={`doodle ${className}`} viewBox="0 0 80 55" fill="none" aria-hidden="true"><path d="M73 5C44 0 22 9 26 26c2 13 19 10 15 0C37 17 14 27 6 47m0 0 16-5M6 47l-1-16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

function Hero() {
  return <section className="hero container" aria-labelledby="hero-title"><div className="hero-copy"><h1 id="hero-title">Discover fashion<br />that feels like <em>you.</em></h1><p className="hero-description">Your inspirations meet cultural discovery. Explore artists, films and books connected to your taste by Qloo.</p><div className="hero-action"><Button href="/sign-in" className="button--large">Get started <ArrowRight size={21} /></Button></div><div className="hero-benefits">{[[Globe2, 'Style that goes', 'where you go']].map(([Icon, line1, line2]) => <div key={line1}><span className="icon-tile"><Icon size={18} /></span><span>{line1}<br />{line2}</span></div>)}</div></div><div className="hero-art" aria-label="Fashion inspirations and an example Style DNA profile"><div className="art-wash" /><span className="handwritten inspiration-note">Turn your saved inspo…<Doodle /></span><div className="photo-frame photo-frame--one"><ResilientImage src="/images/soft-casual.png" alt="Relaxed blue cardigan and denim outfit inspiration" /></div><div className="photo-frame photo-frame--two"><ResilientImage src="/images/modern-classic.png" alt="Modern burgundy leather and tailored outfit inspiration" /></div><div className="photo-frame photo-frame--three"><ResilientImage src="/images/romantic-dress.png" alt="Romantic brown dress and cream blouse outfit inspiration" /><span className="photo-heart"><Heart size={15} /></span></div><span className="art-sparkle art-sparkle--one" aria-hidden="true">✧</span><span className="art-sparkle art-sparkle--two" aria-hidden="true">✧</span><StylePreview className="hero-style-preview" /><span className="handwritten dna-note">…into your own<br />style story<Doodle /></span><Card className="browse-note"><span className="icon-tile"><Sparkles size={23} /></span><div><strong>Your taste, always evolving.</strong><p>Discover more with every choice.</p><a href="/dashboard">Explore your direction <ArrowUpRight size={13} /></a></div></Card></div></section>;
}

function HowItWorks() {
  const steps = [
    { number: '01', Icon: Images, title: 'Show us what you love', text: 'Share your interests and a few saved inspirations.', kind: 'inspo' },
    { number: '02', Icon: Sparkles, title: 'Discover cultural connections', text: 'Explore artists, films and books connected by Qloo to your interests.', kind: 'dna' },
    { number: '03', Icon: ShoppingBag, title: 'Make it yours', text: 'Save the directions you love. Refine discoveries with your feedback.', kind: 'search' },
  ];
  return <section id="how-it-works" className="section container"><SectionHeading centered eyebrow="A little inspiration goes a long way" title={<>Your style. Three simple steps.</>}></SectionHeading><div className="steps-grid">{steps.map(({ number, Icon, title, text, kind }) => <Card className="step-card" key={number}><div className={`step-visual step-visual--${kind}`} aria-hidden="true">{kind === 'inspo' ? <><ResilientImage src="/images/city-chic.png" alt="" /><ResilientImage src="/images/romantic-dress.png" alt="" /><span className="floating-icon"><Heart size={20} /></span></> : kind === 'dna' ? <div className="mini-dna"><Sparkles size={21} /><span>Soft. Earthy. Timeless.</span><div className="mini-palette"><i /><i /><i /><i /></div><div className="mini-chips"><span>Romantic</span><span>Relaxed</span></div></div> : <div className="mini-search"><div><span>Keep what feels like you</span><ArrowRight size={16} /></div><ResilientImage src="/images/romantic-dress.png" alt="" /><ResilientImage src="/images/soft-casual.png" alt="" /></div>}</div><div className="step-card__copy"><div className="step-number"><span>{number}</span><Icon size={19} /></div><h3>{title}</h3><p>{text}</p></div></Card>)}</div></section>;
}

const faqs = [
  ['What is Muselly?', 'A personal taste companion that brings together your fashion inspirations and cultural interests. Explore new connections and refine your direction with every choice.'],
  ['How does Qloo help?', 'Qloo finds related artists, films, shows and books from your interests and saved choices. Cultural discoveries and clothing preferences stay distinct until you choose something as fashion inspiration.'],
  ['Can I use my saved outfit images?', 'Yes. Upload outfit photos or screenshots in your taste test. Your inspiration library keeps them accessible, with AI observations of colors, patterns and shapes.'],
  ['Are my choices saved?', 'Choices save on your device immediately and sync to your account in the background. Analytics waits for pending choices to sync before showing updated totals.'],
  ['Can I shop for outfits here?', 'Shopping is not available yet. For now, build your taste profile, discover cultural connections and save directions you want to explore.'],
];

function FAQs() {
  return <section id="faqs" className="section faq-section container"><SectionHeading eyebrow="Good to know" title={<>A little clarity.</>} /><div className="faq-list">{faqs.map(([question, answer]) => <details key={question}><summary>{question}<ChevronDown size={18} aria-hidden="true" /></summary><p>{answer}</p></details>)}</div></section>;
}

function Footer() {
  return <footer className="site-footer"><div className="container footer-main"><div><Brand /><p>Your taste. More to discover.</p></div><nav aria-label="Footer navigation">{links.map(([name, id]) => <a key={id} href={`/#${id}`}>{name}</a>)}</nav></div><div className="container footer-bottom"><span>© {new Date().getFullYear()} Muselly</span><span>Your style story, taking shape</span></div></footer>;
}

function Landing() {
  return <><Navigation /><main id="main-content"><Hero /><HowItWorks /><FAQs /></main><Footer /></>;
}

function EntryHeader() {
  return <header className="entry-header container"><Brand /><a className="back-link" href="/"><ArrowLeft size={16} /> Back to Muselly</a></header>;
}

export function TasteTestGate({ dashboard = false }) {
  const { status, user, error, retry } = useAuth();
  useEffect(() => {
    if (['signed-out', 'unconfigured'].includes(status)) navigate('/sign-in', true);
  }, [status]);
  if (status === 'signed-in' && user) return dashboard ? <Suspense fallback={<><EntryHeader /><main id="main-content" className="taste-page container"><p role="status">Opening your style profile…</p></main></>}><TasteDashboard key={user.id} user={user} /></Suspense> : <TasteTest key={user.id} header={<EntryHeader />} redirectCompleted />;
  return <><EntryHeader /><main id="main-content" className="taste-page container"><p role="status">{status === 'error' ? error : 'Checking your sign-in…'}</p>{status === 'error' && <div className="entry-actions"><Button onClick={retry}>Try again</Button><Button href="/sign-in" variant="secondary">Go to sign in</Button></div>}</main></>;
}

export default function App() {
  const location = useNavigation();
  const path = location.pathname.replace(/\/$/, '') || '/';
  return <AuthProvider><a className="skip-link" href="#main-content">Skip to content</a>{path === '/' ? <Landing /> : (path === '/taste-test' || path === '/dashboard') ? <TasteTestGate dashboard={path === '/dashboard'} /> : path === '/explore' ? <Suspense fallback={<><EntryHeader /><main id="main-content" className="taste-page container"><p role="status">Opening discovery…</p></main></>}><ExplorePage /></Suspense> : path === '/sign-in' ? <SignIn header={<EntryHeader />} /> : path === '/auth/callback' ? <AuthCallback header={<EntryHeader />} /> : <><EntryHeader /><main id="main-content" className="not-found container"><h1>This page is still on the moodboard.</h1><Button href="/">Back to Muselly <ArrowRight size={18} /></Button></main></>}</AuthProvider>;
}

