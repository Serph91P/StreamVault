import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'
const command = process.env.STREAMVAULT_REUSE_VERIFIED_REAL_BUILD === 'true' ? 'verify' : 'build'
export default defineConfig({
  testDir: '.', testMatch: ['issue904-notifications.spec.ts', 'issue989-read-state.spec.ts'],
  timeout: 30_000, expect: { timeout: 10_000 }, workers: 1, reporter: 'list',
  outputDir: fileURLToPath(new URL('../../test-results/issue904-notifications', import.meta.url)),
  metadata: { useMockData: false, evidence: 'REAL frontend; synthetic HTTP/WebSocket protocol, no store injection' },
  use: { baseURL: 'http://127.0.0.1:4188', browserName: 'chromium', serviceWorkers: 'block', trace: 'retain-on-failure', timezoneId: 'UTC' },
  webServer: {
    command: `node scripts/build-artifact-provenance.mjs ${command} --mode real && node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4188 --strictPort`,
    url: 'http://127.0.0.1:4188', reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
