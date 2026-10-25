import { afterEach, expect, it, vi } from 'vitest';
vi.mock('./supabase', () => ({ apiRequest: vi.fn() }));
import { apiRequest } from './supabase';
import { acquirePrivateImage } from './privateImages';
afterEach(() => vi.restoreAllMocks());

it('shares a private download and keeps its object URL alive until the final viewer leaves', async () => {
  URL.createObjectURL = vi.fn(() => 'blob:preview');
  URL.revokeObjectURL = vi.fn();
  apiRequest.mockResolvedValue(new Blob(['image'], {type:'image/png'}));
  const a = acquirePrivateImage({id:'shared'}), b = acquirePrivateImage({id:'shared'});
  expect(await a.promise).toBe('blob:preview');
  expect(await b.promise).toBe('blob:preview');
  expect(apiRequest).toHaveBeenCalledTimes(1);
  a.release(); expect(URL.revokeObjectURL).not.toHaveBeenCalled();
  b.release(); expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:preview');
  b.release(); expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1);
});

it('does not keep an aborted request in the cache when a viewer remounts', async () => {
  apiRequest.mockClear();
  apiRequest.mockImplementation(async (_, {signal}) => {
    await Promise.resolve();
    if (signal.aborted) throw new DOMException('Aborted','AbortError');
    return new Blob(['image']);
  });
  const a = acquirePrivateImage({id:'remount'});
  const rejected = expect(a.promise).rejects.toMatchObject({name:'AbortError'});
  a.release();
  const b = acquirePrivateImage({id:'remount'});
  await rejected; await b.promise;
  expect(apiRequest).toHaveBeenCalledTimes(2);
  b.release();
});
