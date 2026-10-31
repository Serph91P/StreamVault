import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  testDir: '.', testMatch: 'auth-return-navigation.spec.ts', timeout: 30_000,
  expect: { timeout: 10_000 }, workers: 1, reporter: 'list',
  outputDir: '../../test-results/auth-return',
  metadata: { useMockData: false, evidence: 'REAL build / synthetic HTTP / current worker' },
  use: {
    baseURL: 'http://127.0.0.1:4190', serviceWorkers: 'allow', trace: 'retain-on-failure',
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH },
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    cwd: fileURLToPath(new URL('../..', import.meta.url)),
    command: 'node scripts/build-artifact-provenance.mjs verify --mode real && npm run preview -- --host 127.0.0.1 --port 4190 --strictPort',
    url: 'http://127.0.0.1:4190', reuseExistingServer: false,
  },
})
