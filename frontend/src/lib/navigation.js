export function navigate(destination, replace = false) {
  window.history[replace ? 'replaceState' : 'pushState']({}, '', destination);
  window.dispatchEvent(new PopStateEvent('popstate'));
  if (!window.location.hash) window.scrollTo?.(0, 0);
}

export function openTasteTest() {
  try {
    const destination = sessionStorage.getItem('muselly-explore-return');
    sessionStorage.removeItem('muselly-explore-return');
    if (destination && /^\/(?:explore|shop)(?:[?#]|$)/.test(destination)) {
      navigate(destination, true);
      return;
    }
  } catch { /* Fall back to onboarding when storage is unavailable. */ }
  navigate('/taste-test', true);
}

export function openStylePlaceholder() { navigate('/dashboard'); }
