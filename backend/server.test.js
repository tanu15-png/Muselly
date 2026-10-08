import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRequestHandler } from './server.js';

// Exercise the server's actual request handler without binding a network port.
async function request(handler, url, method = 'GET') {
  const result = { status: 200, headers: {}, body: '' };
  await handler({ url, method }, {
    setHeader(name, value) { result.headers[name.toLowerCase()] = value; },
    writeHead(status, headers = {}) {
      result.status = status;
      for (const [name, value] of Object.entries(headers)) this.setHeader(name, value);
    },
    end(body) { result.body = body?.toString() || ''; },
  });
  return result;
}

test('serves React routes, assets and health while rejecting unsupported requests', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'muselly-server-'));
  await writeFile(join(directory, 'index.html'), '<main>Muselly</main>');
  await writeFile(join(directory, 'app.js'), 'export default "muselly";');
  const handler = createRequestHandler({ publicDirectory: directory });
  try {
    for (const path of ['/', '/taste-test', '/taste-test/', '/sign-in']) {
      const response = await request(handler, path);
      assert.equal(response.status, 200);
      assert.match(response.headers['content-type'], /text\/html/);
      assert.equal(response.body, '<main>Muselly</main>');
    }
    assert.deepEqual(JSON.parse((await request(handler, '/api/health')).body), { status: 'ok', phase: 1 });
    const script = await request(handler, '/app.js');
    assert.match(script.headers['content-type'], /text\/javascript/);
    assert.equal(script.headers['x-content-type-options'], 'nosniff');
    assert.equal((await request(handler, '/missing.png')).status, 404);
    assert.equal((await request(handler, '/api/unknown')).status, 404);
    assert.equal((await request(handler, '/api/health', 'POST')).status, 405);
    assert.equal((await request(handler, '/%E0%A4%A')).status, 400);
    assert.equal((await request(handler, '/..%2f..%2fREADME.md')).status, 403);
    const head = await request(handler, '/taste-test', 'HEAD');
    assert.equal(head.status, 200);
    assert.equal(head.body, '');
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('explains a missing frontend build without breaking health', async () => {
  const handler = createRequestHandler({ publicDirectory: join(tmpdir(), 'muselly-missing-build') });
  assert.equal((await request(handler, '/')).status, 503);
  assert.equal((await request(handler, '/api/health')).status, 200);
});
