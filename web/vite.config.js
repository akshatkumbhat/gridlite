import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development the React app runs on :5173 and sends every /api call to the
// Node gateway on :4000. It never talks to Flask directly.
const GATEWAY_URL = process.env.GATEWAY_URL || 'http://127.0.0.1:4000';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1', // no LAN exposure of unauthenticated development UI
    port: 5173,
    proxy: {
      '/api': GATEWAY_URL,
    },
  },
});
