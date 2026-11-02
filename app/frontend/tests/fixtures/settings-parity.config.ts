import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  testDir: '.', testMatch: ['settings-parity.spec.ts', 'ux-foundation.spec.ts'], workers: 1,
  timeout: 60_000, expect: { timeout: 10_000 }, reporter: 'list',
  outputDir: '../../test-results/settings-parity',
  metadata: { evidence: 'Real production frontend, synthetic stateful HTTP fixtures; not live backend or Twitch evidence' },
  use: {
    baseURL: 'http://127.0.0.1:4193', serviceWorkers: 'block', trace: 'retain-on-failure',
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH },
  },
  webServer: {
    command: 'node scripts/build-artifact-provenance.mjs build --mode real && npm run preview -- --host 127.0.0.1 --port 4193 --strictPort',
    url: 'http://127.0.0.1:4193', reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
