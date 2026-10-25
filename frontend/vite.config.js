import { fileURLToPath } from 'node:url';

export default {
  esbuild: { jsx: 'automatic' },
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8000' },
    fs: { allow: [fileURLToPath(new URL('.', import.meta.url)), fileURLToPath(new URL('../shared', import.meta.url))] },
  },
  preview: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  // VM workers start reliably on this Windows/WSL checkout, where ordinary
  // thread/fork workers time out while importing the test environment.
  test: { environment: 'jsdom', include: ['src/**/*.test.jsx'], pool: 'vmThreads', maxWorkers: 1 },
};
