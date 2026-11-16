import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dev server proxies API calls so the browser talks to one origin (first-party cookies).
const backend = process.env.VITE_DEV_BACKEND ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: backend, changeOrigin: false },
      '/health': { target: backend, changeOrigin: false },
    },
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: { react: ['react', 'react-dom'], icons: ['lucide-react'] },
      },
    },
  },
})
