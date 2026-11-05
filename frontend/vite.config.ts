import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Listen on all IPv4 addresses
    port: 5173,
    strictPort: true,
    watch: {
      usePolling: true, // Required for file change detection inside WSL/Docker
    },
  },
});