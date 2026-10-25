// Self-contained because Chrome serializes this into the active page.
export function selectSnapshotRegion() {
  return new Promise(resolve => {
    const host = document.createElement('div');
    host.style.cssText = 'position:fixed;inset:0;z-index:2147483647;';
    const shadow = host.attachShadow({ mode: 'closed' });
    const cursor = `url("data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><path d="M4 3 28 8 18 14 15 27Z" fill="#fcfaf8" stroke="#a84265" stroke-width="2.5" stroke-linejoin="round"/></svg>')}") 4 3, crosshair`;
    const overlay = document.createElement('div');
    overlay.style.cssText = `position:absolute;inset:0;background:rgba(33,30,34,.25);touch-action:none;cursor:${cursor};`;
    const selection = document.createElement('div');
    selection.style.cssText = 'position:absolute;border:2px solid #e88ca4;box-sizing:border-box;box-shadow:0 0 0 100vmax rgba(33,30,34,.3);pointer-events:none;display:none;';
    const hint = document.createElement('div');
    hint.textContent = 'Drag around your inspiration · Esc to cancel';
    hint.style.cssText = 'position:absolute;top:24px;left:50%;transform:translateX(-50%);padding:14px 20px;border-radius:99px;background:#fcfaf8;color:#211e22;font:14px Arial,sans-serif;pointer-events:none;white-space:nowrap;';
    overlay.append(selection, hint); shadow.append(overlay); document.documentElement.append(host);
    let start, finished = false;
    const point = event => ({ x: Math.max(0, Math.min(innerWidth, event.clientX)), y: Math.max(0, Math.min(innerHeight, event.clientY)) });
    const region = end => ({ x: Math.min(start.x, end.x), y: Math.min(start.y, end.y), width: Math.abs(end.x - start.x), height: Math.abs(end.y - start.y), viewportWidth: innerWidth, viewportHeight: innerHeight });
    const finish = result => {
      if (finished) return; finished = true;
      window.removeEventListener('keydown', keydown, true);
      window.removeEventListener('pagehide', cancel);
      window.removeEventListener('resize', cancel);
      clearTimeout(timer); host.remove();
      // Wait for the page to paint without the selection before captureVisibleTab.
      requestAnimationFrame(() => requestAnimationFrame(() => resolve(result)));
    };
    const cancel = () => finish(null);
    const keydown = event => { if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); cancel(); } };
    window.addEventListener('keydown', keydown, true);
    window.addEventListener('pagehide', cancel);
    window.addEventListener('resize', cancel);
    const timer = setTimeout(cancel, 60000);
    overlay.onpointerdown = event => { if (event.button !== 0) return; event.preventDefault(); event.stopPropagation(); start = point(event); overlay.setPointerCapture(event.pointerId); };
    overlay.onpointermove = event => {
      if (!start) return;
      const rect = region(point(event));
      overlay.style.background = 'transparent'; selection.style.display = 'block';
      Object.assign(selection.style, { left: `${rect.x}px`, top: `${rect.y}px`, width: `${rect.width}px`, height: `${rect.height}px` });
    };
    overlay.onpointerup = event => {
      if (!start) return;
      const rect = region(point(event));
      if (rect.width < 12 || rect.height < 12) { start = null; hint.textContent = 'Drag a larger area · Esc to cancel'; return; }
      finish(rect);
    };
    overlay.onpointercancel = cancel;
  });
}
