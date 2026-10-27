// Account-scoped, durable feedback. A local commit advances the deck; network
// acknowledgements only remove events, never replace the user's current card.
export function createDiscoveryStore(factory) {
  let connection;
  function database() {
    if (!connection) connection = new Promise((resolve, reject) => {
      const idb = factory || globalThis.indexedDB;
      if (!idb) { reject(new Error('Browser storage is unavailable. Enable site storage to save your choices.')); return; }
      const request = idb.open('muselly-discovery-v1', 1);
      request.onupgradeneeded = () => {
        request.result.createObjectStore('decks', { keyPath: 'owner_id' });
        const events = request.result.createObjectStore('events', { keyPath: 'sequence', autoIncrement: true });
        events.createIndex('owner', 'owner_id');
        events.createIndex('event', 'event_id', { unique: true });
      };
      request.onerror = () => { connection = null; reject(request.error); };
      request.onblocked = () => { connection = null; reject(new Error('Close other Muselly tabs to enable local saving.')); };
      request.onsuccess = () => { const db = request.result; db.onversionchange = () => { db.close(); connection = null; }; resolve(db); };
    });
    return connection;
  }
  async function change(owner, operation = () => {}) {
    if (!owner) throw new Error('Sign in before saving discoveries.');
    const db = await database();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(['decks', 'events'], 'readwrite');
      const decks = tx.objectStore('decks'), events = tx.objectStore('events');
      const readDeck = decks.get(owner), readEvents = events.index('owner').getAll(owner);
      let ready = 0, state, failure;
      const loaded = () => {
        if (++ready !== 2) return;
        state = { deck: readDeck.result || null, events: readEvents.result.sort((a, b) => a.sequence - b.sequence) };
        const original = state.deck;
        try {
          operation(state, {
            append(value) { const record = { ...value, owner_id: owner }; events.add(record); state.events.push(record); },
            remove(value) { events.delete(value.sequence); state.events = state.events.filter(row => row.event_id !== value.event_id); },
          });
          if (state.deck && state.deck !== original) decks.put(state.deck);
        } catch (error) { failure = error; tx.abort(); }
      };
      readDeck.onsuccess = loaded; readEvents.onsuccess = loaded;
      tx.oncomplete = () => resolve({ run: state.deck?.run || null, lastChoice: state.deck?.lastChoice || null, pending: state.events });
      tx.onerror = () => reject(failure || tx.error || new Error('Couldn’t save locally. Your card has not advanced.'));
      tx.onabort = () => reject(failure || tx.error || new Error('Local saving was interrupted. Try again.'));
    });
  }
  function session(deck) { return deck?.run?.session; }
  return {
    load: owner => change(owner),
    async accept(owner, run) {
      if (!run || typeof run !== 'object') throw new Error('Couldn’t load discoveries. Please retry.');
      return change(owner, state => {
        const same = Boolean(run.session?.id && session(state.deck)?.id === run.session.id);
        const consumed = new Set(same ? state.deck.consumed : []);
        let queue = (run.session?.queue || []).filter(item => !consumed.has(item.entity_id));
        for (const event of state.events.filter(row => row.session_id === run.session?.id)) {
          if (event.action === 'undo') { consumed.delete(event.entity_id); queue = [event.card, ...queue.filter(item => item.entity_id !== event.entity_id)]; }
          else if (event.action !== 'shown') { consumed.add(event.entity_id); queue = queue.filter(item => item.entity_id !== event.entity_id); }
        }
        // Refills can finish after several rapid local choices. Preserve the
        // card actually being viewed now, rather than the request's old anchor.
        const visible = same ? session(state.deck)?.queue[0] : null;
        if (visible && !consumed.has(visible.entity_id)) queue = [visible, ...queue.filter(item => item.entity_id !== visible.entity_id)];
        state.deck = { owner_id: owner, run: { ...run, ...(run.session ? { session: { ...run.session, queue } } : {}) },
          consumed: [...consumed], shown: same ? state.deck.shown : [], lastChoice: same ? state.deck.lastChoice : null };
      });
    },
    async shown(owner, card) {
      return change(owner, (state, ops) => {
        const current = session(state.deck);
        if (!current || !current.queue.some(item => item.entity_id === card.entity_id)) return;
        if ((state.deck.shown || []).includes(card.entity_id)) return;
        ops.append({ event_id: crypto.randomUUID(), session_id: current.id, entity_id: card.entity_id, action: 'shown', card });
        state.deck = { ...state.deck, shown: [...(state.deck.shown || []), card.entity_id] };
      });
    },
    async choose(owner, card, action, referenceImageIds) {
      return change(owner, (state, ops) => {
        const current = session(state.deck);
        if (!current || !current.queue.some(item => item.entity_id === card.entity_id)) throw new Error('This card changed in another tab. Reload your discoveries.');
        const event = { event_id: crypto.randomUUID(), session_id: current.id, entity_id: card.entity_id, action, card,
          ...(referenceImageIds ? { reference_image_ids: referenceImageIds } : {}) };
        ops.append(event);
        const consumed = new Set(state.deck.consumed); consumed.add(card.entity_id);
        state.deck = { ...state.deck, consumed: [...consumed], lastChoice: event,
          run: { ...state.deck.run, session: { ...current, queue: current.queue.filter(item => item.entity_id !== card.entity_id),
            choices_since_refresh: (current.choices_since_refresh || 0) + (action !== 'skip' ? 1 : 0) } } };
      });
    },
    async undo(owner, expectedEvent) {
      return change(owner, (state, ops) => {
        const target = state.deck?.lastChoice, current = session(state.deck);
        if (!target || !current || target.session_id !== current.id) return;
        if (expectedEvent && target.event_id !== expectedEvent) throw new Error('Your latest choice changed in another tab. Reload before undoing.');
        ops.append({ event_id: crypto.randomUUID(), session_id: current.id, entity_id: target.entity_id,
          action: 'undo', target_id: target.event_id, card: target.card });
        state.deck = { ...state.deck, consumed: state.deck.consumed.filter(id => id !== target.entity_id), lastChoice: null,
          run: { ...state.deck.run, session: { ...current, queue: [target.card, ...current.queue.filter(item => item.entity_id !== target.entity_id)],
            choices_since_refresh: Math.max(0, (current.choices_since_refresh || 0) - (target.action !== 'skip' ? 1 : 0)) } } };
      });
    },
    async acknowledge(owner, ids) {
      const accepted = new Set(ids);
      return change(owner, (state, ops) => { for (const row of [...state.events]) if (accepted.has(row.event_id)) ops.remove(row); });
    },
  };
}

export const discoveryStore = createDiscoveryStore();

export function createOutboxSync({ owner, store = discoveryStore, send, onState = () => {}, onError = () => {} }) {
  let flight = null, stopped = false;
  return {
    stop() { stopped = true; },
    flush() {
      if (flight) return flight;
      flight = (async () => {
        let state = await store.load(owner);
        while (state.pending.length) {
          if (stopped) throw new Error('Synchronization paused.');
          const first = state.pending[0];
          const batch = [];
          for (const row of state.pending) {
            if (row.session_id !== first.session_id || batch.length === 50) break;
            batch.push(row);
          }
          const result = await send(first.session_id, batch.map(({ event_id, entity_id, action, target_id, reference_image_ids }) =>
            ({ event_id, entity_id, action, ...(target_id ? { target_id } : {}), ...(reference_image_ids ? { reference_image_ids } : {}) })));
          const acked = result?.acked || [];
          if (!batch.every(row => acked.includes(row.event_id))) throw new Error('Some choices were not acknowledged. They remain saved on this device.');
          state = await store.acknowledge(owner, acked);
          if (!stopped) onState(state);
        }
        return state;
      })().catch(error => { if (!stopped) onError(error); throw error; }).finally(() => { flight = null; });
      return flight;
    },
  };
}
