import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueJsx(), vueDevTools()],
  server: {
    allowedHosts: true,
    proxy: {
      '/api': {
        target: process.env.DEV_BACKEND ?? 'http://127.0.0.1:8090',
        changeOrigin: true,
      },
      '/ws': {
        target: (process.env.DEV_BACKEND ?? 'http://127.0.0.1:8090').replace(/^http/, 'ws'),
        ws: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
