import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const realWebServerCommand = process.env.STREAMVAULT_REUSE_VERIFIED_REAL_BUILD === 'true'
  ? 'node scripts/build-artifact-provenance.mjs verify --mode real && npm run preview -- --host 127.0.0.1 --port 4183 --strictPort'
  : 'node scripts/build-artifact-provenance.mjs build --mode real && npm run preview -- --host 127.0.0.1 --port 4183 --strictPort'

// Exercise the identical loader regression against the REAL production artifact.
// Only auth/API responses are synthetic; application modules are not replaced.
export default defineConfig({
  testDir: '../e2e',
  testMatch: 'settings-loader.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: 'list',
  metadata: { useMockData: false, evidence: 'synthetic HTTP / REAL frontend, not live backend' },
  use: { baseURL: 'http://127.0.0.1:4183', serviceWorkers: 'block', trace: 'retain-on-failure' },
  projects: [
    { name: 'real-desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'real-mobile', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: realWebServerCommand,
    url: 'http://127.0.0.1:4183',
    reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
