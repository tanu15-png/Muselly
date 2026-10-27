import { ReadableStream } from 'node:stream/web';
import { TextDecoder, TextEncoder } from 'node:util';
globalThis.TextDecoder ??= TextDecoder;
import { expect, it, vi } from 'vitest';
import { readAgentEvents } from './shoppingAgent';
function response(chunks) {
  return { body: new ReadableStream({ start(controller) {
    chunks.forEach(chunk => controller.enqueue(new TextEncoder().encode(chunk))); controller.close();
  } }) };
}
it('handles split streamed progress and final result', async () => {
  const progress = vi.fn();
  const result = await readAgentEvents(response(['{"type":"progress","message":"Q', 'loo"}\n', '{"type":"result","result":{"total":2}}\n']), progress);
  expect(progress).toHaveBeenCalledWith('Qloo'); expect(result.total).toBe(2);
});
it('rejects an interrupted stream and surfaces server errors', async () => {
  await expect(readAgentEvents(response([]), vi.fn())).rejects.toThrow('interrupted');
  await expect(readAgentEvents(response(['{"type":"error","message":"Retry"}\n']), vi.fn())).rejects.toThrow('Retry');
});
