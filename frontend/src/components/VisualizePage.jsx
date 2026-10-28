import { useEffect, useState } from 'react';
import { useAuth } from './AuthProvider';
import { Brand, Button, Eyebrow } from './ui';
import SignIn from './SignIn';
import OutfitPreview from './OutfitPreview';
import '../styles/dashboard.css';
import '../styles/visualize.css';

export default function VisualizePage() {
  const { status, user, error, retry } = useAuth();
  const [query, setQuery] = useState('');
  useEffect(() => {
    document.title = 'Visualize your outfit — Muselly';
    if (status === 'signed-out') {
      try { sessionStorage.setItem('muselly-explore-return', '/visualize'); } catch { /* Optional return destination. */ }
    }
  }, [status]);
  return <><header className="dashboard-header"><div className="container dashboard-nav"><Brand /><nav><a href="/dashboard">My fashion direction</a><a href="/shop">Shop your taste</a></nav></div></header>
    {status === 'signed-out' ? <SignIn /> : <main id="main-content" className="visualize-page container">
      {status === 'signed-in' && user ? <>
        <Eyebrow>Inspired by your Qloo taste</Eyebrow><h1>Picture your next outfit.</h1>
        <label htmlFor="visualize-request">What would you like to wear?</label>
        <textarea id="visualize-request" rows={2} maxLength={280} value={query} onChange={event => setQuery(event.target.value)} placeholder="A relaxed office outfit in soft colors" />
        <OutfitPreview key={user.id} ownerId={user.id} query={query} onSearch={text => { window.location.assign(`/shop?q=${encodeURIComponent(text)}`); }} />
      </> : <><p role="status">{error || 'Checking your sign-in…'}</p>{status === 'error' && <Button onClick={retry}>Retry</Button>}</>}
    </main>}
  </>;
}
