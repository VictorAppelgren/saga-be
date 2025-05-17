import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    outDir: '../static/dist',
    manifest: true,
    rollupOptions: {
      input: {
        main: './src/main.js'
      }
    }
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
