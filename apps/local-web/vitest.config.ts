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
    // Playwright specs live in e2e/ and run with `pnpm e2e`, not vitest.
    exclude: ['**/node_modules/**', '**/dist/**', 'e2e/**'],
    coverage: {
      provider: 'v8',
      // `src/lib/**` and the pure agent helpers carry the 80% gate. Hooks,
      // the app-shell model, and the terminal layer are measured with
      // their own (lower) floors so regressions show up without blocking
      // on UI code that is exercised by the Playwright harness instead
      // (see apps/local-web/e2e/).
      include: [
        'src/components/agents/transcript.ts',
        'src/components/agents/composer-parts.ts',
        'src/components/agents/skill-examples.ts',
        'src/components/agents/terminal-layer/**',
        'src/components/app/**',
        'src/hooks/**',
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
        'src/lib/workspace-download.ts',
        '**/*.test.ts',
        '**/*.test.tsx'
      ],
      reporter: ['text', 'text-summary', 'lcov', 'html', 'json-summary'],
      reportsDirectory: './coverage',
      thresholds: {
        // Global floor over everything in `include` (measured 58% when the
        // hooks / app / terminal-layer globs were added).
        lines: 55,
        functions: 60,
        branches: 50,
        statements: 52,
        // Pure helpers keep the strict gate.
        'src/lib/**': {
          lines: 80,
          functions: 80,
          // Branch coverage lags on UI helper conditionals; gate on lines/funcs.
          branches: 70,
          statements: 80
        },
        'src/components/agents/transcript.ts': { lines: 75, functions: 70 },
        'src/components/agents/composer-parts.ts': { lines: 75, functions: 70 },
        'src/components/agents/skill-examples.ts': { lines: 75, functions: 70 },
        // Floors for UI-heavy code — raise as unit tests land.
        'src/hooks/**': { lines: 25, functions: 30 },
        'src/components/app/**': { lines: 40, functions: 50 },
        'src/components/agents/terminal-layer/**': { lines: 10, functions: 15 }
      }
    }
  }
})
