import { defineConfig, devices } from '@playwright/test'

import { resolveE2EEnv } from './e2e/fixtures/env'

/**
 * Sandwalk UI e2e + perf harness.
 *
 * Runs the real SPA (Vite dev server, same one `tauri:dev` uses) against a
 * real `sandwalk serve`. Both are reused when already listening; the Vite
 * server is started on demand, the API is not (it needs your keys/config).
 *
 *   pnpm e2e            # functional specs (e2e/tests)
 *   pnpm e2e:bench      # benchmarks (e2e/bench) → e2e/results/*.json
 *   pnpm e2e:compare a.json b.json
 *
 * Env: SANDWALK_WEB_URL, SANDWALK_API_URL, SANDWALK_API_KEY (or read from
 * the Sandwalk settings.json), SANDWALK_E2E_PANES (bench grid size).
 */
const env = resolveE2EEnv()

export default defineConfig({
  testDir: './e2e',
  testMatch: /.*\.spec\.ts$/,
  outputDir: './e2e/.artifacts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [['list'], ['html', { open: 'never', outputFolder: './e2e/.report' }]],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: env.webUrl,
    viewport: { width: 1600, height: 1000 },
    trace: 'retain-on-failure',
    video: 'off'
  },
  projects: [
    { name: 'e2e', testDir: './e2e/tests' },
    { name: 'bench', testDir: './e2e/bench', timeout: 180_000 }
  ],
  webServer: {
    command: `pnpm dev --port ${env.webPort} --strictPort`,
    url: env.webUrl,
    reuseExistingServer: true,
    timeout: 60_000,
    env: { SANDWALK_API_URL: env.apiUrl }
  }
})
