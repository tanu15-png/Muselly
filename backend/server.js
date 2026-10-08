import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const defaultPublicDirectory = fileURLToPath(new URL('../frontend/dist/', import.meta.url));
const contentTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
};
const appRoutes = new Set(['/', '/taste-test', '/sign-in']);

/** Phase 1 serves the React build. Future account APIs belong under /api. */
export function createRequestHandler({ publicDirectory = defaultPublicDirectory } = {}) {
  const publicRoot = resolve(publicDirectory);
  return async (request, response) => {
    response.setHeader('X-Content-Type-Options', 'nosniff');
    response.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
    response.setHeader('X-Frame-Options', 'DENY');
    if (!['GET', 'HEAD'].includes(request.method)) {
      response.writeHead(405, { Allow: 'GET, HEAD' });
      response.end('Method not allowed');
      return;
    }
    let pathname;
    try {
      pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    } catch {
      response.writeHead(400);
      response.end('Invalid URL');
      return;
    }
    if (pathname === '/api/health') {
      response.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      response.end(request.method === 'HEAD' ? undefined : JSON.stringify({ status: 'ok', phase: 1 }));
      return;
    }
    const normalizedRoute = pathname.replace(/\/$/, '') || '/';
    const isAppRoute = appRoutes.has(normalizedRoute);
    const target = resolve(publicRoot, isAppRoute ? 'index.html' : `.${pathname}`);
    if (!target.startsWith(publicRoot + sep) || pathname.includes('\0') || pathname.includes('\\')) {
      response.writeHead(403);
      response.end('Forbidden');
      return;
    }
    try {
      const file = await readFile(target);
      response.writeHead(200, {
        'Content-Type': contentTypes[extname(target)] || 'application/octet-stream',
        'Cache-Control': isAppRoute ? 'no-cache' : 'public, max-age=3600',
      });
      response.end(request.method === 'HEAD' ? undefined : file);
    } catch (error) {
      if (error.code === 'ENOENT' && isAppRoute) {
        response.writeHead(503, { 'Content-Type': 'text/plain; charset=utf-8' });
        response.end('Frontend build not found. Run npm run build in frontend first.');
      } else {
        response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        response.end('Not found');
      }
    }
  };
}

export function createApp(options) {
  return createServer(createRequestHandler(options));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT || 3000);
  const server = createApp();
  server.listen(port, '0.0.0.0', () => console.log(`Muselly is running at http://localhost:${port}`));
}
