import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const pkg = JSON.parse(
  readFileSync(new URL('./package.json', import.meta.url), 'utf8')
) as { version?: string }

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    __UI_VERSION__: JSON.stringify(pkg.version || '0.0.0')
  },
  server: {
    host: '127.0.0.1',
    port: 8969,
    strictPort: true
  },
  preview: {
    host: '127.0.0.1',
    port: 8969,
    strictPort: true
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  }
})
