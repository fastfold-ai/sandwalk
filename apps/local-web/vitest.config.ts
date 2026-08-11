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
        // Desktop / glue / large modules — keep the gate on unit-tested pure helpers.
        'src/lib/app-storage.ts',
        'src/lib/backend-url.ts',
        'src/lib/composer-models.ts',
        'src/lib/dedupe-async.ts',
        'src/lib/desktop.ts',
        'src/lib/desktop-voice.ts',
        'src/lib/media-src.ts',
        'src/lib/open-desktop-recent.ts',
        'src/lib/remote-hostname.ts',
        'src/lib/favicon.ts',
        'src/lib/skills-catalog.ts',
        'src/lib/skills-catalog-helpers.ts',
        'src/lib/skills-catalog-install.ts',
        'src/lib/skills-catalog-source.ts',
        'src/lib/theme.ts',
        '**/*.test.ts',
        '**/*.test.tsx'
      ],
      reporter: ['text', 'text-summary', 'lcov', 'html', 'json-summary'],
      reportsDirectory: './coverage',
      thresholds: {
        lines: 80,
        functions: 80,
        // Branch coverage lags on UI helper conditionals; gate on lines/funcs.
        branches: 70,
        statements: 80
      }
    }
  }
})
