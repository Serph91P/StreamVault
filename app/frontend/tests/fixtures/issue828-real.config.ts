import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

// Isolated config: never changes the canonical MOCK contracts or production auth.
// The genuine REAL artifact is verified before preview; API is intercepted solely
// by the per-test synthetic HTTP fixture. No external backend/provider is used.
export default defineConfig({
  testDir: '.',
  testMatch: 'issue828-real.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: 'list',
  metadata: { useMockData: false, evidence: 'synthetic HTTP / REAL frontend, not live backend' },
  use: { baseURL: 'http://127.0.0.1:4182', serviceWorkers: 'block', trace: 'retain-on-failure' },
  projects: [{ name: 'synthetic-real-chromium', use: { browserName: 'chromium' } }],
  webServer: {
    command: 'node scripts/build-artifact-provenance.mjs verify --mode real && node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4182 --strictPort',
    url: 'http://127.0.0.1:4182',
    reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
