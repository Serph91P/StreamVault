import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  testDir: '.', testMatch: 'issue992-recording.spec.ts', workers: 1,
  timeout: 30_000, expect: { timeout: 10_000 }, reporter: 'list',
  outputDir: '../../test-results/issue992-recording',
  metadata: { useMockData: false, evidence: 'Built REAL UI and WebSocketManager; synthetic HTTP/auth and routed WebSocket peer, no recorder/provider/database writes' },
  use: { baseURL: 'http://127.0.0.1:4192', browserName: 'chromium', serviceWorkers: 'block', trace: 'retain-on-failure', reducedMotion: 'reduce' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'touch', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: 'node scripts/build-artifact-provenance.mjs verify --mode real && node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4192 --strictPort',
    url: 'http://127.0.0.1:4192', reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
