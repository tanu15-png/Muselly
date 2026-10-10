import { fileURLToPath } from 'node:url';

export default {
  esbuild: { jsx: 'automatic' },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
    fs: { allow: [fileURLToPath(new URL('.', import.meta.url)), fileURLToPath(new URL('../shared', import.meta.url))] },
  },
  test: { environment: 'jsdom', include: ['src/**/*.test.jsx'] },
};
