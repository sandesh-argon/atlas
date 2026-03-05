import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Base path — SPA lives at /explore/ on atlas.argonanalytics.org
  base: '/explore/',
  build: {
    outDir: 'dist/explore',
  },
  server: {
    port: 5174,
    host: true,
    watch: {
      usePolling: true,  // Required for hot reload over SSH
    },
  },
})
