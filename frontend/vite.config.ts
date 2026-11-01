import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    server: {
      host: '0.0.0.0',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        '/docs': { target: apiTarget, changeOrigin: true },
        '/redoc': { target: apiTarget, changeOrigin: true },
        '/openapi.json': { target: apiTarget, changeOrigin: true },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      globals: true,
      css: true,
    },
  }
})
