import { useEffect, useState } from 'react';
import { navigate } from './navigation';

const routes = new Set(['/', '/dashboard', '/explore', '/extension', '/extension/connect', '/taste-test', '/sign-in', '/auth/callback']);

export function useNavigation() {
  const [location, setLocation] = useState(() => window.location.href);
  useEffect(() => {
    const changed = () => setLocation(window.location.href);
    const click = event => {
      if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const link = event.target.closest?.('a[href]');
      if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin || !routes.has(url.pathname)) return;
      if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) return;
      event.preventDefault();
      navigate(url.pathname + url.search + url.hash);
    };
    const submit = event => {
      const form = event.target;
      if (event.defaultPrevented || !form.matches?.('form[data-client-navigation]')) return;
      event.preventDefault();
      navigate(`${form.getAttribute('action')}?${new URLSearchParams(new FormData(form))}`);
    };
    window.addEventListener('popstate', changed);
    document.addEventListener('click', click);
    document.addEventListener('submit', submit);
    return () => {
      window.removeEventListener('popstate', changed);
      document.removeEventListener('click', click);
      document.removeEventListener('submit', submit);
    };
  }, []);
  return new URL(location);
}
