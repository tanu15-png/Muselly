import { afterEach, expect, it, vi } from 'vitest';
import { selectSnapshotRegion } from '../../../extension/snapshot';

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); document.body.innerHTML = ''; });
function setup() {
  const original = Element.prototype.attachShadow;
  vi.spyOn(Element.prototype, 'attachShadow').mockImplementation(function () { return original.call(this, {mode:'open'}); });
  vi.stubGlobal('requestAnimationFrame', fn => { fn(); return 1; });
  const promise = selectSnapshotRegion();
  const host = [...document.documentElement.children].find(node => node.shadowRoot);
  const overlay = host.shadowRoot.firstChild;
  overlay.setPointerCapture = vi.fn();
  return { promise, host, overlay };
}

it('shows the pink selection cursor, tracks a backwards drag, and removes the overlay before capture', async () => {
  const {promise, host, overlay} = setup();
  expect(overlay.style.cursor).toContain('data:image/svg+xml');
  overlay.dispatchEvent(new MouseEvent('pointerdown', {clientX:400,clientY:350,button:0}));
  overlay.dispatchEvent(new MouseEvent('pointermove', {clientX:100,clientY:50}));
  expect(overlay.firstChild.style.width).toBe('300px');
  expect(overlay.firstChild.style.display).toBe('block');
  overlay.dispatchEvent(new MouseEvent('pointerup', {clientX:100,clientY:50}));
  expect(await promise).toMatchObject({x:100,y:50,width:300,height:300,viewportWidth:innerWidth,viewportHeight:innerHeight});
  expect(host.isConnected).toBe(false);
});

it('cancels with Escape without returning an image region', async () => {
  const {promise, host} = setup();
  window.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape'}));
  expect(await promise).toBeNull();
  expect(host.isConnected).toBe(false);
});
