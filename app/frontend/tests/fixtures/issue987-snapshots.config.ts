import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  testDir: '.', testMatch: 'issue987-snapshots.spec.ts', workers: 1,
  timeout: 30_000, expect: { timeout: 10_000 }, reporter: 'list',
  outputDir: '../../test-results/issue987-snapshots',
  metadata: { useMockData: false, evidence: 'REAL production bundle and registered manager/replay; synthetic read-only HTTP/auth/WS peers, no backend/provider/DB writes; Chromium desktop and native touch emulation, not physical hardware' },
  use: { baseURL: 'http://127.0.0.1:4187', browserName: 'chromium', serviceWorkers: 'block', trace: 'retain-on-failure', reducedMotion: 'reduce' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'touch', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: 'node scripts/build-artifact-provenance.mjs verify --mode real && node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4187 --strictPort',
    url: 'http://127.0.0.1:4187', reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
