import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  testDir: '.',
  testMatch: 'issue950-player.spec.ts',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  workers: 1,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:4182', serviceWorkers: 'block', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: {
    command: 'node scripts/build-artifact-provenance.mjs verify --mode real && node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4182 --strictPort',
    url: 'http://127.0.0.1:4182',
    reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
