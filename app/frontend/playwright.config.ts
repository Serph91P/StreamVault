import { defineConfig, devices } from '@playwright/test'

export const requiredViewportMatrix = {
  smallPhone: [{ width: 320, height: 568 }, { width: 360, height: 640 }, { width: 375, height: 667 }],
  modernPhone: [{ width: 390, height: 844 }, { width: 393, height: 873 }, { width: 412, height: 915 }, { width: 430, height: 932 }],
  phoneLandscape: [{ width: 568, height: 320 }, { width: 667, height: 375 }, { width: 844, height: 390 }, { width: 915, height: 412 }, { width: 932, height: 430 }],
  tablet: [{ width: 600, height: 960 }, { width: 768, height: 1024 }, { width: 820, height: 1180 }, { width: 1024, height: 768 }, { width: 1180, height: 820 }],
  desktop: [{ width: 1024, height: 768 }, { width: 1280, height: 720 }, { width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }],
} as const

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: 'list',
  outputDir: 'test-results',
  use: {
    baseURL: 'http://127.0.0.1:4180',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', testIgnore: /frontend-baseline\.spec\.ts/, use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', testIgnore: /frontend-baseline\.spec\.ts/, use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
    { name: 'baseline-chromium', testMatch: /frontend-baseline\.spec\.ts/, use: { ...devices['Desktop Chrome'] } },
    { name: 'baseline-firefox', testMatch: /frontend-baseline\.spec\.ts/, use: { ...devices['Desktop Firefox'] } },
    { name: 'baseline-webkit', testMatch: /frontend-baseline\.spec\.ts/, use: { ...devices['Desktop Safari'] } },
  ],
  webServer: {
    command: 'VITE_USE_MOCK_DATA=true npm run build && VITE_USE_MOCK_DATA=true npm run preview -- --host 127.0.0.1 --port 4180',
    url: 'http://127.0.0.1:4180',
    reuseExistingServer: false,
  },
})
