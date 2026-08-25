import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const pkg = JSON.parse(
  readFileSync(new URL('./package.json', import.meta.url), 'utf8')
) as { version?: string }

const tauri = Boolean(process.env.TAURI_ENV_PLATFORM || process.env.TAURI_PLATFORM)
const apiProxy = {
  '/v1': {
    target: process.env.SANDWALK_API_URL || 'http://127.0.0.1:8787',
    changeOrigin: true,
    ws: true
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Tauri loads from a custom protocol — relative asset URLs are required.
  base: tauri ? './' : '/',
  define: {
    __UI_VERSION__: JSON.stringify(pkg.version || '0.0.0')
  },
  clearScreen: false,
  server: {
    host: '127.0.0.1',
    // Menubar Vite uses 8969; Tauri `beforeDevCommand` uses 1420.
    port: Number(process.env.VITE_PORT || (tauri ? 1420 : 8969)),
    strictPort: true,
    // Same-origin /v1/* would otherwise return index.html (JSON parse '<').
    proxy: apiProxy
  },
  preview: {
    host: '127.0.0.1',
    port: 8969,
    strictPort: true,
    proxy: apiProxy
  },
  envPrefix: ['VITE_', 'TAURI_'],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  }
})
