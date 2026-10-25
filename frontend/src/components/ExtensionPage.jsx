import { useEffect, useState } from 'react';
import { ArrowLeft, Download, Sparkles } from 'lucide-react';
import { Brand, Button, Card, Eyebrow } from './ui';
import { useAuth } from './AuthProvider';
import { supabase } from '../lib/supabase';
import SignIn from './SignIn';
import '../styles/explore.css';

export default function ExtensionPage({ connect = false }) {
  const { status, user } = useAuth();
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [connected, setConnected] = useState(false);
  const params = new URLSearchParams(window.location.search);
  const extensionId = params.get('extension_id') || '', nonce = params.get('nonce') || '';
  const valid = /^[a-p]{32}$/.test(extensionId) && /^[a-f0-9]{64}$/.test(nonce);
  useEffect(() => {
    document.title = connect ? 'Connect extension — Muselly' : 'Get the Muselly extension';
    if (connect && valid && status === 'signed-out') {
      try { sessionStorage.setItem('muselly-explore-return', window.location.pathname + window.location.search); } catch { /* Sign in can continue on the current page. */ }
    }
  }, [connect, valid, status]);
  const header = <header className="entry-header container"><Brand /><a className="back-link" href="/"><ArrowLeft size={16} /> Back to Muselly</a></header>;
  async function pair() {
    setBusy(true); setError('');
    try {
      if (!valid || !window.chrome?.runtime?.sendMessage) throw new Error('Open Connect Muselly from your installed extension in Chrome or Edge.');
      const { data, error: sessionError } = await supabase.auth.getSession();
      if (sessionError || !data.session) throw new Error('Sign in again to connect the extension.');
      const result = await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('The extension did not respond. Start Connect again from its side panel.')), 20000);
        window.chrome.runtime.sendMessage(extensionId, { type: 'MUSELLY_CONNECT', nonce, accessToken: data.session.access_token, expiresAt: data.session.expires_at }, response => {
          clearTimeout(timer);
          if (window.chrome.runtime.lastError) reject(new Error('Extension not found or connection expired. Start Connect again in its side panel.'));
          else resolve(response);
        });
      });
      if (!result?.ok) throw new Error(result?.error || 'The extension could not connect.');
      setConnected(true);
      try { sessionStorage.removeItem('muselly-explore-return'); } catch { /* Optional storage. */ }
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  if (connect && status === 'signed-out') return <>{header}<div className="container"><p>Sign in to connect your Muselly profile to the extension.</p></div><SignIn /></>;
  return <>{header}<main id="main-content" className="section container extension-setup"><Card className="discover-entry-card"><div><Eyebrow>Your taste, beyond this tab</Eyebrow><h1>{connect ? 'Connect your\nstyle companion.' : 'Shop with a little\nmore you.'}</h1><p>Keep your taste test, inspirations, and Qloo brands on Muselly. Search and rank products while browsing your favorite stores with the extension.</p></div><div>{connect ? <>
    {connected ? <><h2>Connected to Muselly.</h2><p role="status">Return to the extension side panel. Your profile is ready for product ranking, snapshots, and saved finds.</p></> : <><h2>Connect your account</h2><p>This shares your current Muselly access session with the installed extension so it can rank products and save inspirations on your behalf. It does not share your password or a refresh token.</p>{user && <p>Signed in as {user.email}</p>}<Button disabled={!valid || status !== 'signed-in' || busy} onClick={pair}><Sparkles size={16} />{busy ? 'Connecting…' : 'Connect extension'}</Button>{!valid && <p role="alert">Start Connect Muselly from the installed extension to create a valid connection request.</p>}</>}
    {error && <p role="alert">{error}</p>}
    </> : <><Button href="/api/extension/download" download="muselly-extension.zip"><Download size={18} /> Get Extension</Button><p>Chrome / Edge development package · ZIP download</p><ol><li>Extract the ZIP into a folder.</li><li>Open <code>chrome://extensions</code> (or <code>edge://extensions</code>) and turn on Developer mode.</li><li>Choose <strong>Load unpacked</strong> and select the extracted folder.</li><li>Pin Muselly, click its icon, then choose <strong>Connect Muselly</strong>.</li></ol><p>Downloading does not install the extension automatically. A one-click store install requires a published Chrome Web Store listing.</p></>}
    </div></Card>{!connect && <Card className="extension-guide"><h2>Discover your style. Refine every find.</h2><ol><li>Write a prompt such as <strong>midi dress under 2000</strong> and discover Qloo brands and open a suggested retailer.</li><li>Click the Muselly toolbar icon on that shopping tab, then <strong>Find my favorites on this page</strong>. Scroll and rank again to consider more loaded products.</li><li><strong>Take snapshot</strong> or upload an image. Preview and crop it, then choose <strong>Save inspiration to Muselly</strong> to keep it in your private library.</li><li><strong>Save to Muselly</strong> keeps product bookmarks in Saved finds, or snapshots in your private inspiration library.</li></ol><p>Prices and attributes come from readable page content. Store layouts can change; stock and sizes need confirmation. Snapshots are used only to save inspirations. Correct recommendations with More like this, Not my style, Too expensive, Wrong shape, or Wrong color.</p><Button href="/explore" variant="secondary">Explore Qloo brands</Button></Card>}</main></>;
}
