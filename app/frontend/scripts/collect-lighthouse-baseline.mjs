import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { spawn } from 'node:child_process'
import lighthouse from 'lighthouse'
import { launch } from 'chrome-launcher'
import { chromium } from 'playwright'
import { summarizeLighthouseReport } from './lighthouseSummary.mjs'
import { validateLighthouseChromePath } from './lighthouseChromePath.mjs'

const baseUrl = process.env.LIGHTHOUSE_BASE_URL ?? 'http://127.0.0.1:4180'
const outputDir = resolve(process.env.LIGHTHOUSE_OUTPUT_DIR ?? 'test-results/lighthouse')
const chromePath = await validateLighthouseChromePath(process.env.LIGHTHOUSE_CHROME_PATH ?? chromium.executablePath())

const scenarios = [
  { id: 'mobile-streamers', route: '/streamers', formFactor: 'mobile', viewport: { width: 390, height: 844 } },
  { id: 'desktop-home', route: '/', formFactor: 'desktop', viewport: { width: 1440, height: 900 } },
]

function startPreviewServer() {
  return spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '4180'], {
    env: { ...process.env },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
}

async function stopPreviewServer(server) {
  if (server.exitCode !== null) return
  const exited = new Promise((resolveExit, rejectExit) => {
    const timeout = setTimeout(() => rejectExit(new Error('preview did not stop after SIGTERM')), 5_000)
    server.once('exit', () => {
      clearTimeout(timeout)
      resolveExit()
    })
  })
  server.kill('SIGTERM')
  await exited
}

async function waitForPreview(server) {
  const startedAt = Date.now()
  let lastError = 'preview has not accepted a connection'
  while (Date.now() - startedAt < 30_000) {
    try {
      const response = await fetch(baseUrl)
      if (response.ok) return
      lastError = `preview returned HTTP ${response.status}`
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error)
    }
    await new Promise(resolveWait => setTimeout(resolveWait, 250))
  }
  server.kill('SIGTERM')
  throw new Error(`preview readiness failed: ${lastError}`)
}

function lighthouseFlags(port, scenario, cacheMode) {
  const isMobile = scenario.formFactor === 'mobile'
  return {
    port,
    logLevel: 'error',
    output: 'json',
    onlyCategories: ['performance'],
    formFactor: scenario.formFactor,
    screenEmulation: {
      mobile: isMobile,
      width: scenario.viewport.width,
      height: scenario.viewport.height,
      deviceScaleFactor: isMobile ? 2.625 : 1,
      disabled: false,
    },
    throttlingMethod: 'simulate',
    throttling: isMobile
      ? { rttMs: 150, throughputKbps: 1_638.4, requestLatencyMs: 150, downloadThroughputKbps: 1_638.4, uploadThroughputKbps: 750, cpuSlowdownMultiplier: 4 }
      : { rttMs: 40, throughputKbps: 10_240, requestLatencyMs: 40, downloadThroughputKbps: 10_240, uploadThroughputKbps: 3_000, cpuSlowdownMultiplier: 1 },
    disableStorageReset: true,
    maxWaitForLoad: 45_000,
    settings: { onlyCategories: ['performance'], disableStorageReset: true },
    cacheMode,
  }
}

async function collectScenario(scenario) {
  const userDataDir = await mkdtemp(join(tmpdir(), 'streamvault-lighthouse-'))
  const chrome = await launch({
    chromePath,
    userDataDir,
    chromeFlags: ['--headless=new', '--no-sandbox', '--disable-dev-shm-usage'],
  })
  try {
    const reports = []
    for (const cacheMode of ['cold', 'warm']) {
      const result = await lighthouse(`${baseUrl}${scenario.route}`, lighthouseFlags(chrome.port, scenario, cacheMode))
      if (!result?.lhr) throw new Error(`Lighthouse returned no LHR for ${scenario.id} ${cacheMode}`)
      const filename = `${scenario.id}-${cacheMode}.lhr.json`
      await writeFile(join(outputDir, filename), `${JSON.stringify(result.lhr, null, 2)}\n`)
      reports.push({
        file: filename,
        cacheMode,
        ...summarizeLighthouseReport(result.lhr),
      })
    }
    return {
      scenario: scenario.id,
      route: scenario.route,
      theme: 'application-default; theme-specific Lighthouse requires a later deterministic bootstrap hook',
      formFactor: scenario.formFactor,
      viewport: scenario.viewport,
      reports,
    }
  } finally {
    await chrome.kill()
    await rm(userDataDir, { recursive: true, force: true })
  }
}

await rm(outputDir, { recursive: true, force: true })
await mkdir(outputDir, { recursive: true })
const preview = startPreviewServer()
const previewOutput = []
preview.stdout.on('data', chunk => previewOutput.push(chunk.toString()))
preview.stderr.on('data', chunk => previewOutput.push(chunk.toString()))
try {
  await waitForPreview(preview)
  const results = []
  for (const scenario of scenarios) results.push(await collectScenario(scenario))
  await writeFile(join(outputDir, 'summary.json'), `${JSON.stringify({
    schemaVersion: 1,
    source: 'deterministic VITE_USE_MOCK_DATA=true Lighthouse collection',
    baseUrl,
    chromePath,
    lighthouseVersion: (await import('lighthouse/package.json', { with: { type: 'json' } })).default.version,
    network: 'loopback app server; external network must be disabled by the caller',
    scenarios: results,
  }, null, 2)}\n`)
} finally {
  await stopPreviewServer(preview)
  await writeFile(join(outputDir, 'preview.log'), previewOutput.join(''))
}
