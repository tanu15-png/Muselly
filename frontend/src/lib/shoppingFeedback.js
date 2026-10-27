// Small owner-scoped outbox. Acknowledging an older request never deletes a newer choice.
export function shoppingFeedbackStore(storage = () => window.localStorage) {
  const key = owner => `muselly-shopping-feedback:${owner}`;
  const load = owner => {
    if (!owner) throw new Error('Sign in to save choices.');
    const raw = storage().getItem(key(owner));
    return raw ? JSON.parse(raw) : { choices: {}, pending: {} };
  };
  function write(owner, state) { storage().setItem(key(owner), JSON.stringify(state)); return state; }
  return { load,
    choose(owner, productId, choice) {
      const state = load(owner);
      if (choice === 'clear') delete state.choices[productId]; else state.choices[productId] = choice;
      state.pending[productId] = { product_id: productId, choice, event_id: crypto.randomUUID() };
      return write(owner, state);
    },
    merge(owner, choices) {
      const state = load(owner); state.choices = { ...choices };
      for (const row of Object.values(state.pending)) {
        if (row.choice === 'clear') delete state.choices[row.product_id]; else state.choices[row.product_id] = row.choice;
      }
      return write(owner, state);
    },
    acknowledge(owner, event) {
      const state = load(owner);
      if (state.pending[event.product_id]?.event_id === event.event_id) delete state.pending[event.product_id];
      return write(owner, state);
    },
  };
}
