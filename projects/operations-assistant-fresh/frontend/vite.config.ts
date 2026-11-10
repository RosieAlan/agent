import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8020', rewrite: path => path.replace(/^\/api/, '') },
      '/knowledge': { target: 'http://127.0.0.1:8020' },
    },
  },
})
