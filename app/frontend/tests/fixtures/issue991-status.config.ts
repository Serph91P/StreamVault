import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  testDir: '.', testMatch: 'issue991-status.spec.ts', workers: 1,
  timeout: 30_000, expect: { timeout: 10_000 }, reporter: 'list',
  outputDir: '../../test-results/issue991-status',
  metadata: { useMockData: false, evidence: 'Built REAL frontend, actual local HTTP journal, synthetic auth/DTO/WebSocket peers; no production/provider operations' },
  use: { baseURL: 'http://127.0.0.1:4189', browserName: 'chromium', serviceWorkers: 'block', trace: 'retain-on-failure', reducedMotion: 'reduce' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'touch', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: 'node scripts/build-artifact-provenance.mjs verify --mode real && node tests/fixtures/issue991-server.mjs',
    url: 'http://127.0.0.1:4189', reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
