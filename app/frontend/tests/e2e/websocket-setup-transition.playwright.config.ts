import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  testMatch: 'websocket-setup-transition.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: 'list',
  metadata: { useMockData: false },
  use: {
    baseURL: 'http://127.0.0.1:4181',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'VITE_USE_MOCK_DATA=false npm run build && npm run preview -- --host 127.0.0.1 --port 4181',
    url: 'http://127.0.0.1:4181',
    reuseExistingServer: false,
  },
})
