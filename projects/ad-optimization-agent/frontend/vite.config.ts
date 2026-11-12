import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8030',
        rewrite: path => path.replace(/^\/api/, ''),
        timeout: 110_000, // 容纳规划、诊断和有限修订的完整后端等待时间。
      },
    },
  },
})
