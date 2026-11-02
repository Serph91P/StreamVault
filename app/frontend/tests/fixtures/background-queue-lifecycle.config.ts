import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  testDir: '../e2e',
  testMatch: 'background-queue-lifecycle.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: 'list',
  metadata: { useMockData: false, evidence: 'REAL production frontend with synthetic HTTP boundary' },
  use: { baseURL: 'http://127.0.0.1:4198', serviceWorkers: 'block', trace: 'retain-on-failure' },
  projects: [{ name: 'queue-real-chromium', use: { browserName: 'chromium' } }],
  webServer: {
    command: 'node scripts/build-artifact-provenance.mjs verify --mode real && npm run preview -- --host 127.0.0.1 --port 4198 --strictPort',
    url: 'http://127.0.0.1:4198',
    reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
