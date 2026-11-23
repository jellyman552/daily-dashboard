import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Backend runs on 8420 (see backend/app/main.py + deploy/systemd).
      '/api': 'http://localhost:8420',
    },
  },
})
