import { useEffect } from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { Brand, Button, Eyebrow } from './ui';
import { useAuth } from './AuthProvider';
import SignIn from './SignIn';
import EnrichmentPanel from './EnrichmentPanel';
import '../styles/dashboard.css';
import '../styles/explore.css';

export default function ExplorePage() {
  const { status, user, error, retry } = useAuth();
  useEffect(() => {
    document.title = 'Explore brands — Muselly';
    try {
      if (status === 'signed-out') sessionStorage.setItem('muselly-explore-return', `/explore${window.location.search}${window.location.hash}`);
      if (status === 'signed-in') sessionStorage.removeItem('muselly-explore-return');
    } catch { /* Discovery still works when browser storage is unavailable. */ }
  }, [status]);
  useEffect(() => {
    if (status === 'signed-in' && window.location.hash === '#brand-affinities') {
      document.getElementById('brand-affinities')?.scrollIntoView?.();
    }
  }, [status]);
  const header = <header className="dashboard-header"><div className="container dashboard-nav"><Brand /><nav aria-label="Discovery navigation"><a href="/">Home</a><a href="#brand-affinities">Explore brands</a></nav><Button href="/dashboard" variant="secondary">My Style DNA <ArrowRight size={16} /></Button></div></header>;
  if (status === 'signed-out') return <>{header}<div className="container explore-sign-in-note"><p>Sign in to discover brands connected to your saved taste.</p></div><SignIn /></>;
  if (status !== 'signed-in' || !user) return <>{header}<main id="main-content" className="taste-page container"><p role="status">{status === 'error' ? error : status === 'unconfigured' ? 'Sign-in is currently unavailable. Please try again later.' : 'Checking your sign-in…'}</p>{status === 'error' && <Button onClick={retry}>Try again</Button>}<a className="text-link" href="/">Back to home <ArrowLeft size={16} /></a></main></>;
  return <>{header}<main id="main-content" className="dashboard container explore-page"><div className="explore-intro"><Eyebrow>A little discovery. A little more you.</Eyebrow><h1>Find the brands<br /><em>that feel like you.</em></h1><p>Explore Qloo connections shaped by your favorite brands and cultural interests. Save the connections that resonate with you.</p></div><section id="brand-affinities" className="explore-brands" aria-label="Brand discovery"><EnrichmentPanel key={user.id} ownerId={user.id} /></section><footer className="profile-footer"><Brand /><a className="text-link" href="/dashboard">Back to your Style DNA <ArrowRight size={16} /></a></footer></main></>;
}
