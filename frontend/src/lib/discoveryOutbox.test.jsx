import { IDBFactory } from 'fake-indexeddb';
import { beforeEach, expect, it, vi } from 'vitest';
import { createDiscoveryStore, createOutboxSync } from './discoveryOutbox';

const card = { entity_id: 'artist', domain: 'artist', name: 'Artist' };
const second = { entity_id: 'film', domain: 'movie', name: 'Film' };
const run = { session: { id: 's1', queue: [card, second], choices_since_refresh: 0 } };
let factory, store;
beforeEach(async () => { factory = new IDBFactory(); store = createDiscoveryStore(factory); await store.accept('owner', run); });

it('keeps confirmed reference selections through reload and batch delivery', async () => {
  await store.choose('owner', card, 'fashion', ['look-1', 'look-2']);
  const restored = createDiscoveryStore(factory);
  expect((await restored.load('owner')).pending[0].reference_image_ids).toEqual(['look-1', 'look-2']);
  const send = vi.fn(async (_, actions) => ({ acked: actions.map(row => row.event_id) }));
  await createOutboxSync({ owner: 'owner', store: restored, send }).flush();
  expect(send.mock.calls[0][1][0].reference_image_ids).toEqual(['look-1', 'look-2']);
});

it('persists choices and the next card across storage instances without a network', async () => {
  await store.choose('owner', card, 'like');
  const restored = await createDiscoveryStore(factory).load('owner');
  expect(restored.run.session.queue).toEqual([second]);
  expect(restored.pending[0].action).toBe('like');
  expect(restored.lastChoice.card).toEqual(card);
  expect((await store.load('other-owner')).pending).toEqual([]);
  expect((await store.load('other-owner')).run).toBeNull();
});
it('does not resurrect acknowledged cards from stale server responses', async () => {
  const state = await store.choose('owner', card, 'like');
  await store.acknowledge('owner', [state.pending[0].event_id]);
  const result = await store.accept('owner', run);
  expect(result.run.session.queue).toEqual([second]);
});
it('preserves the currently visible card when a delayed refill arrives', async () => {
  await store.choose('owner', card, 'like');
  const arrival = { entity_id: 'new-artist', domain: 'artist', name: 'New artist' };
  const result = await store.accept('owner', { session: { ...run.session, queue: [arrival, second] } });
  expect(result.run.session.queue).toEqual([second, arrival]);
});
it('persists ordered undo for both pending and already acknowledged choices', async () => {
  let state = await store.choose('owner', card, 'fashion');
  await store.undo('owner', state.lastChoice.event_id);
  state = await store.load('owner');
  expect(state.pending.map(row => row.action)).toEqual(['fashion', 'undo']);
  expect(state.pending[1].target_id).toBe(state.pending[0].event_id);
  expect(state.run.session.queue[0]).toEqual(card);
  await store.acknowledge('owner', state.pending.map(row => row.event_id));
  state = await store.choose('owner', card, 'like');
  await store.acknowledge('owner', state.pending.map(row => row.event_id));
  await store.undo('owner', state.lastChoice.event_id);
  expect((await store.load('owner')).pending[0].action).toBe('undo');
});
it('retains failed batches and retries with the original identifiers', async () => {
  await store.choose('owner', card, 'like');
  const send = vi.fn().mockRejectedValueOnce(new Error('Offline')).mockImplementation(async (_, actions) => ({ acked: actions.map(row => row.event_id) }));
  const worker = createOutboxSync({ owner: 'owner', store, send });
  await expect(worker.flush()).rejects.toThrow('Offline');
  expect((await store.load('owner')).pending).toHaveLength(1);
  await worker.flush();
  expect(send.mock.calls[0][1][0].event_id).toBe(send.mock.calls[1][1][0].event_id);
  expect((await store.load('owner')).pending).toHaveLength(0);
});
it('uses one flight and drains events added while a batch is in progress', async () => {
  await store.choose('owner', card, 'like');
  let release;
  const send = vi.fn().mockImplementationOnce((_, actions) => new Promise(resolve => { release = () => resolve({ acked: actions.map(row => row.event_id) }); }))
    .mockImplementation(async (_, actions) => ({ acked: actions.map(row => row.event_id) }));
  const worker = createOutboxSync({ owner: 'owner', store, send });
  const first = worker.flush();
  expect(worker.flush()).toBe(first);
  await vi.waitFor(() => expect(release).toBeTruthy());
  await store.choose('owner', second, 'known');
  release(); await first;
  expect(send).toHaveBeenCalledTimes(2);
  expect((await store.load('owner')).pending).toHaveLength(0);
});
it('does not acknowledge incomplete server replies or send another owner’s events', async () => {
  await store.choose('owner', card, 'like');
  const send = vi.fn(async () => ({ acked: [] }));
  const worker = createOutboxSync({ owner: 'owner', store, send });
  await expect(worker.flush()).rejects.toThrow('not acknowledged');
  expect((await store.load('owner')).pending).toHaveLength(1);
  const other = createOutboxSync({ owner: 'other', store, send });
  await other.flush();
  expect(send).toHaveBeenCalledTimes(1);
});
