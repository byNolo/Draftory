import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  worker: { format: 'es' },
  build: {
    rolldownOptions: {
      input: {
        game: fileURLToPath(new URL('./index.html', import.meta.url)),
        diagnostics: fileURLToPath(
          new URL('./dev/index.html', import.meta.url),
        ),
      },
    },
  },
  server: {
    proxy: {
      '/api': process.env.DRAFTORY_API_TARGET ?? 'http://127.0.0.1:8787',
    },
  },
  preview: {
    proxy: {
      '/api': process.env.DRAFTORY_API_TARGET ?? 'http://127.0.0.1:8787',
    },
  },
});
