import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const command = process.env.STREAMVAULT_REUSE_VERIFIED_REAL_BUILD === 'true' ? 'verify' : 'build'
export default defineConfig({
  testDir: '.',
  testMatch: 'issue902-artwork.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: 'list',
  metadata: { useMockData: false, evidence: 'REAL frontend; synthetic HTTP and local synthetic video/artwork only' },
  use: {
    baseURL: 'http://127.0.0.1:4182',
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
    browserName: 'chromium',
  },
  webServer: {
    command: `node scripts/build-artifact-provenance.mjs ${command} --mode real && node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4182 --strictPort`,
    url: 'http://127.0.0.1:4182',
    reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
