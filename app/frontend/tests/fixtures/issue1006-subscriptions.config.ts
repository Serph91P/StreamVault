import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const command = process.env.STREAMVAULT_REUSE_VERIFIED_REAL_BUILD === 'true' ? 'verify' : 'build'

export default defineConfig({
  testDir: '.',
  testMatch: 'issue1006-subscriptions.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: 'list',
  metadata: { issue: '1006', evidence: 'REAL production frontend, synthetic HTTP/auth; no provider operations' },
  use: { baseURL: 'http://127.0.0.1:4196', serviceWorkers: 'block', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop-light', use: { browserName: 'chromium', viewport: { width: 1440, height: 900 }, colorScheme: 'light' } },
    { name: 'narrow-touch-dark', use: { browserName: 'chromium', viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, colorScheme: 'dark' } },
  ],
  webServer: {
    command: `node scripts/build-artifact-provenance.mjs ${command} --mode real && node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4196 --strictPort`,
    url: 'http://127.0.0.1:4196',
    reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
