// Each item is a complete draft. While a write is running, keep only the
// newest pending snapshot: it already includes every earlier answer.
export function createDraftQueue(write, onStatus) {
  let pending = null;
  let running = null;

  function enqueue(snapshot) {
    pending = snapshot;
    onStatus('saving', snapshot);
    if (!running) {
      running = Promise.resolve().then(async () => {
        while (pending) {
          const current = pending;
          pending = null;
          try {
            await write(current);
          } catch (error) {
            if (pending) continue; // A newer complete draft can recover this save.
            pending = current;
            onStatus('error', current);
            throw error;
          }
          if (!pending) onStatus('saved', current);
        }
      }).finally(() => { running = null; });
    }
    return running;
  }

  return { enqueue, clear: () => { pending = null; } };
}
