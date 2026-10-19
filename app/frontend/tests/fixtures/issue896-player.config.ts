import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  testDir: '.',
  testMatch: 'issue896-player.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: 'list',
  metadata: {
    useMockData: false,
    evidence: 'REAL frontend with synthetic HTTP/media; not a physical Pixel',
  },
  use: {
    baseURL: 'http://127.0.0.1:4182',
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
    browserName: 'chromium',
    isMobile: true,
    hasTouch: true,
    deviceScaleFactor: 3,
  },
  webServer: {
    command:
      'node scripts/build-artifact-provenance.mjs verify --mode real && node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4182 --strictPort',
    url: 'http://127.0.0.1:4182',
    reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
