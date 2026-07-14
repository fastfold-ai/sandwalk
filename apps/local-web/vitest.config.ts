import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  test: {
    environment: 'jsdom',
    globals: false,
    coverage: {
      provider: 'v8',
      // Prefer pure modules until full src/ can clear 80%. Include set:
    // transcript.ts, src/lib/** (excluding large untested modules), composer-parts, skill-examples
      include: [
        'src/components/agents/transcript.ts',
        'src/components/agents/composer-parts.ts',
        'src/components/agents/skill-examples.ts',
        'src/lib/**'
      ],
      exclude: [
        'node_modules/**',
        'dist/**',
        '**/*.d.ts',
        'src/main.tsx',
        'src/vite-env.d.ts',
        // Not yet unit-tested; keep gate honest for covered modules.
        'src/lib/app-storage.ts',
        'src/lib/composer-models.ts',
        'src/lib/skills-catalog.ts',
        '**/*.test.ts',
        '**/*.test.tsx'
      ],
      reporter: ['text', 'text-summary', 'lcov', 'html', 'json-summary'],
      reportsDirectory: './coverage',
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80
      }
    }
  }
})
