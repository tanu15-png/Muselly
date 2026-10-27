import { beforeEach, expect, it } from 'vitest';
import { shoppingFeedbackStore } from './shoppingFeedback';
let store;
beforeEach(() => { localStorage.clear(); store = shoppingFeedbackStore(); });
it('persists feedback across instances and isolates accounts', () => {
  store.choose('a', '101', 'like');
  expect(shoppingFeedbackStore().load('a').choices).toEqual({ 101: 'like' });
  expect(store.load('b').choices).toEqual({});
});
it('does not acknowledge a newer local choice when an older save finishes', () => {
  const first = store.choose('a', '101', 'like').pending[101];
  store.choose('a', '101', 'dislike');
  const result = store.acknowledge('a', first);
  expect(result.pending[101].choice).toBe('dislike'); expect(result.choices[101]).toBe('dislike');
});
it('overlays unsynced choices over server feedback, including undo', () => {
  store.choose('a', '101', 'clear'); store.choose('a', '102', 'like');
  expect(store.merge('a', { 101: 'like', 103: 'dislike' }).choices).toEqual({ 102: 'like', 103: 'dislike' });
});
