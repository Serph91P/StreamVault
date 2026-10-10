import { defineConfig } from '@playwright/test'

declare const process: { env: Record<string, string | undefined> }

const realWebServerCommand = process.env.STREAMVAULT_REUSE_VERIFIED_REAL_BUILD === 'true'
  ? 'cd ../.. && node scripts/build-artifact-provenance.mjs verify --mode real && npm run preview -- --host 127.0.0.1 --port 4181'
  : 'cd ../.. && node scripts/build-artifact-provenance.mjs build --mode real && npm run preview -- --host 127.0.0.1 --port 4181'

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
    command: realWebServerCommand,
    url: 'http://127.0.0.1:4181',
    reuseExistingServer: false,
  },
})
