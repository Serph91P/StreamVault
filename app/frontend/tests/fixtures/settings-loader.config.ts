import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const mode = process.env.STREAMVAULT_SETTINGS_TEST_MODE ?? 'real'
if (mode !== 'real' && mode !== 'mock') throw new Error(`Unknown settings test mode: ${mode}`)

// Build each mode genuinely; only auth/API responses are synthetic.
// Keep this regression in its own job without expanding the shared browser job.
export default defineConfig({
  testDir: '.',
  testMatch: 'settings-loader.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: 'list',
  metadata: { useMockData: mode === 'mock', evidence: `synthetic HTTP / ${mode} frontend, not live backend` },
  use: { baseURL: 'http://127.0.0.1:4183', serviceWorkers: 'block', trace: 'retain-on-failure' },
  projects: [
    { name: `${mode}-desktop`, use: { viewport: { width: 1440, height: 900 } } },
    { name: `${mode}-mobile`, use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: `node scripts/build-artifact-provenance.mjs build --mode ${mode} && npm run preview -- --host 127.0.0.1 --port 4183 --strictPort`,
    url: 'http://127.0.0.1:4183',
    reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
