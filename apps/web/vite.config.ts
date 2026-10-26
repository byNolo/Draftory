import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  worker: { format: 'es' },
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
