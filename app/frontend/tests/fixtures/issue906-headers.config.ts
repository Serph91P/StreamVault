import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const realArtifactCommand = process.env.STREAMVAULT_REUSE_VERIFIED_REAL_BUILD === 'true' ? 'verify' : 'build'

// Issue 906 runs only against a provenance-checked REAL production artifact.
// Individual tests intercept HTTP at the browser boundary with synthetic data;
// they never inject router, store, auth, or component state.
export default defineConfig({
  testDir: '.',
  testMatch: 'issue906-headers.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: 'list',
  metadata: {
    useMockData: false,
    evidence: 'synthetic HTTP / REAL frontend production artifact; no app state injection',
    issue: '906',
  },
  use: {
    baseURL: 'http://127.0.0.1:4187',
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'issue906-real-chromium', use: { browserName: 'chromium' } }],
  webServer: {
    command: `node scripts/build-artifact-provenance.mjs ${realArtifactCommand} --mode real && node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4187 --strictPort`,
    url: 'http://127.0.0.1:4187',
    reuseExistingServer: false,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
  },
})
