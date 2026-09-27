import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '../e2e',
  testMatch: /foundation\.spec\.ts/,
  outputDir: '../../foundation-test-results',
  timeout: 30_000,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:4181', viewport: { width: 390, height: 844 }, serviceWorkers: 'block' },
  projects: [{ name: 'foundation-chromium', use: { browserName: 'chromium' } }],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4181',
    url: 'http://127.0.0.1:4181/tests/fixtures/foundation-harness/',
    reuseExistingServer: false,
  },
})
