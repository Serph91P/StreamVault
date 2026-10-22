import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'
import { join, resolve } from 'node:path'
import { tmpdir } from 'node:os'
import { describe, expect, it } from 'vitest'

const frontendRoot = resolve(import.meta.dirname, '..', '..')
const captureNames = [
  'foundation-mobile-dark.png',
  'foundation-mobile-light.png',
  'foundation-desktop-dark.png',
  'foundation-desktop-light.png',
]

function run(script: string, args: string[]) {
  return spawnSync(process.execPath, [resolve(frontendRoot, script), ...args], {
    cwd: frontendRoot,
    encoding: 'utf8',
  })
}

function failWorkflow(message: string): never {
  throw new Error(`frontend capture workflow is not fail-closed: ${message}`)
}

function indentation(line: string) {
  return line.match(/^ */)?.[0].length ?? 0
}

function blockFrom(lines: string[], start: number, indent: number, nextPattern: RegExp) {
  if (start < 0) failWorkflow('required block is missing')
  let end = start + 1
  while (end < lines.length) {
    const line = lines[end]
    if (line.trim() && !line.trimStart().startsWith('#') && indentation(line) === indent && nextPattern.test(line)) break
    end += 1
  }
  return lines.slice(start, end)
}

function activeProperty(lines: string[], indent: number, name: string) {
  const prefix = ' '.repeat(indent)
  const line = lines.find((candidate) => candidate.startsWith(`${prefix}${name}:`))
  return line?.slice(line.indexOf(':') + 1).trim()
}

function jobFrom(lines: string[], name: string) {
  return blockFrom(lines, lines.findIndex((line) => line === `  ${name}:`), 2, /^  [A-Za-z0-9_-]+:\s*$/)
}

function stepFrom(job: string[], name: string) {
  return blockFrom(job, job.findIndex((line) => line === `      - name: ${name}`), 6, /^      - /)
}

function assertNonSkippable(job: string[], name: string) {
  if (activeProperty(job, 4, 'if') !== undefined) failWorkflow(`${name} job may be skipped`)
  const value = activeProperty(job, 4, 'continue-on-error')
  if (value !== undefined && value !== 'false') failWorkflow(`${name} job is non-blocking`)
}

function assertCaptureIntegrationIsBlocking(workflow: string, integrationFlow: string, playwrightConfig: string, websocketConfig: string) {
  const lines = workflow.split('\n')
  const aggregate = jobFrom(lines, 'frontend-build')
  const core = jobFrom(lines, 'frontend-core')
  const browser = jobFrom(lines, 'frontend-browser')

  if (activeProperty(aggregate, 4, 'name') !== 'Frontend Build & Lint') failWorkflow('required frontend aggregate was renamed')
  if (activeProperty(aggregate, 4, 'needs') !== '[frontend-core, frontend-browser]') failWorkflow('aggregate does not require both frontend workers')
  if (activeProperty(aggregate, 4, 'if') !== 'always()') failWorkflow('aggregate does not run after failed, skipped, or cancelled workers')
  if (activeProperty(aggregate, 4, 'timeout-minutes') !== '1') failWorkflow('aggregate timeout is not bounded to one minute')
  const aggregateContinueOnError = activeProperty(aggregate, 4, 'continue-on-error')
  if (aggregateContinueOnError !== undefined && aggregateContinueOnError !== 'false') failWorkflow('frontend-build job is non-blocking')
  const aggregateText = aggregate.join('\n')
  if (!aggregateText.includes('test "${{ needs.frontend-core.result }}" = success') || !aggregateText.includes('test "${{ needs.frontend-browser.result }}" = success')) {
    failWorkflow('aggregate does not explicitly fail unless both worker results succeed')
  }

  const artifactNames: string[] = []
  for (const [name, job] of [['frontend-core', core], ['frontend-browser', browser]] as const) {
    assertNonSkippable(job, name)
    if (activeProperty(job, 4, 'timeout-minutes') !== '12') failWorkflow(`${name} timeout is not capped at twelve minutes`)
    const text = job.join('\n')
    if (!text.includes('app/frontend/test-results/') || !text.includes('app/frontend/foundation-test-results/')) failWorkflow(`${name} failure artifacts are missing`)
    const upload = text.match(/uses:\s*actions\/upload-artifact[^\n]*(?:\n(?!\s{6}-)[^\n]*)*?\n\s+name:\s*([^\n]+)/)
    if (!upload) failWorkflow(`${name} does not upload failure artifacts`)
    artifactNames.push(upload[1].trim())
  }
  if (new Set(artifactNames).size !== artifactNames.length) failWorkflow('worker failure artifact names must be unique')

  const websocketStep = stepFrom(core, 'Run real-build WebSocket transition test')
  if (activeProperty(websocketStep, 8, 'if') !== undefined || (activeProperty(websocketStep, 8, 'continue-on-error') ?? 'false') !== 'false') failWorkflow('WebSocket test step may be skipped or made non-blocking')
  const coreText = core.join('\n')
  const chromium = coreText.indexOf('npx playwright install --with-deps chromium')
  const realBuild = coreText.indexOf('node scripts/build-artifact-provenance.mjs build --mode real')
  const websocket = coreText.indexOf('STREAMVAULT_REUSE_VERIFIED_REAL_BUILD=true npx playwright test --config tests/e2e/websocket-setup-transition.playwright.config.ts')
  const issue894 = coreText.indexOf('tests/fixtures/issue894-player.config.ts')
  const issue896 = coreText.indexOf('tests/fixtures/issue896-player.config.ts')
  const deterministic = coreText.indexOf('npm run test:build-output')
  if (chromium < 0 || realBuild <= chromium || websocket <= realBuild || issue894 <= websocket || issue896 <= issue894 || deterministic <= issue896) {
    failWorkflow('core worker does not preserve real-build browser ordering')
  }
  if (!coreText.includes('npm run lint:check') || !coreText.includes('npm run lint:tokens') || !coreText.includes('npm run check:foundation') || !coreText.includes('npm run type-check') || !coreText.includes('npm run test:unit') || !coreText.includes('npm run test:foundation-gates') || !coreText.includes('npm run test:output-budgets')) {
    failWorkflow('core worker lost a required gate')
  }

  const browserStep = stepFrom(browser, 'Run frontend browser tests')
  if (activeProperty(browserStep, 8, 'if') !== undefined || (activeProperty(browserStep, 8, 'continue-on-error') ?? 'false') !== 'false') failWorkflow('browser test step may be skipped or made non-blocking')
  const browserText = browser.join('\n')
  const allBrowsers = browserText.indexOf('npx playwright install --with-deps')
  const mockBuild = browserText.indexOf('node scripts/build-artifact-provenance.mjs build --mode mock')
  const browserTests = browserText.indexOf('STREAMVAULT_REUSE_VERIFIED_MOCK_BUILD=true npx playwright test')
  const integration = browserText.indexOf('STREAMVAULT_REUSE_VERIFIED_MOCK_BUILD=true npm run test:foundation-capture-integration')
  if (allBrowsers < 0 || browserText.includes('npx playwright install --with-deps chromium') || mockBuild <= allBrowsers || browserTests <= mockBuild || integration <= browserTests) {
    failWorkflow('browser worker does not build and consume the verified mock output in order')
  }
  if (!browserText.includes('      - name: Build verified mock frontend') || !browserText.includes('      - name: Run frontend browser tests')) failWorkflow('browser worker steps were renamed or removed')
  if (!browserText.includes('app/frontend/test-results/') || !browserText.includes('app/frontend/foundation-test-results/')) failWorkflow('browser failure artifacts are missing')
  if (/\|\|\s*true(?:\s|$)/.test(browserText)) failWorkflow('browser command has a success fallback')

  const firstFoundation = integrationFlow.indexOf("run('npm', ['run', 'test:foundation-browser'])")
  const pwa = integrationFlow.indexOf("run('npm', ['run', 'test:e2e', '--', 'tests/e2e/pwa-manifest.spec.ts', '--project', 'desktop'])")
  const packageCaptures = integrationFlow.indexOf("run(process.execPath, ['scripts/package-foundation-evidence.mjs'")
  const firstManifest = integrationFlow.indexOf('await verifyManifest()')
  const secondFoundation = integrationFlow.indexOf("run('npm', ['run', 'test:foundation-browser'])", firstFoundation + 1)
  const secondManifest = integrationFlow.indexOf('await verifyManifest()', firstManifest + 1)
  if (firstFoundation < 0 || pwa <= firstFoundation || packageCaptures <= pwa || firstManifest <= packageCaptures || secondFoundation <= firstManifest || secondManifest <= secondFoundation || integrationFlow.indexOf("run('npm', ['run', 'test:foundation-browser'])", secondFoundation + 1) >= 0) failWorkflow('capture integration does not preserve exactly two foundation runs and manifest checks')
  if (!integrationFlow.includes('if (result.status !== 0) process.exit(result.status ?? 1)')) failWorkflow('capture integration does not propagate child failures')
  if (!playwrightConfig.includes("process.env.STREAMVAULT_REUSE_VERIFIED_MOCK_BUILD === 'true'") || !playwrightConfig.includes("'node scripts/build-artifact-provenance.mjs verify --mode mock && npm run preview -- --host 127.0.0.1 --port 4180'")) failWorkflow('capture integration cannot reuse the verified mock build')
  if (!websocketConfig.includes("process.env.STREAMVAULT_REUSE_VERIFIED_REAL_BUILD === 'true'") || !websocketConfig.includes("'cd ../.. && node scripts/build-artifact-provenance.mjs verify --mode real && npm run preview -- --host 127.0.0.1 --port 4181'")) failWorkflow('WebSocket suite cannot reuse the verified real build')
}

describe('foundation gates fail closed', () => {
  it('rejects circular design-token references with a useful error', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'streamvault-token-cycle-'))
    const source = join(directory, 'tokens.json')
    await writeFile(source, JSON.stringify({ foundation: { a: '{foundation.b}', b: '{foundation.a}' } }))

    const result = run('scripts/generate-responsive-tokens.mjs', ['--design-source', source, '--design-output', join(directory, 'out.scss')])

    expect(result.status).toBe(1)
    expect(result.stderr).toContain('circular token reference')
  })

  it('rejects generated design-token drift in check mode', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'streamvault-token-drift-'))
    const source = join(directory, 'tokens.json')
    const output = join(directory, 'out.scss')
    await writeFile(source, JSON.stringify({ foundation: { color: { ink: '#101820' } }, semantic: { text: '{foundation.color.ink}' } }))
    await writeFile(output, 'stale\n')

    const result = run('scripts/generate-responsive-tokens.mjs', ['--design-source', source, '--design-output', output, '--check'])

    expect(result.status).toBe(1)
    expect(result.stderr).toContain('design generated output is stale')
  })

  it('rejects forbidden raw colors in a strict foundation fixture', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'streamvault-token-lint-'))
    await mkdir(join(directory, 'components'), { recursive: true })
    await writeFile(join(directory, 'components', 'Broken.vue'), '<template><button>Broken</button></template>\n<style scoped>.broken { color: #ff00ff; }</style>\n')

    const result = run('scripts/check-design-tokens.cjs', ['--root', directory, '--strict'])

    expect(result.status).toBe(1)
    expect(result.stderr).toContain('hex')
  })

  it('keeps emitted app custom properties in the theme stylesheet', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'streamvault-token-owner-'))
    await mkdir(join(directory, 'styles'), { recursive: true })
    await writeFile(join(directory, 'styles', '_theme.scss'), ':root {\n  --control-target-min: 44px;\n}\n')
    await writeFile(join(directory, 'styles', '_variables.scss'), '$control-target-min: 44px;\n')

    const valid = run('scripts/check-design-tokens.cjs', ['--root', directory, '--strict'])
    expect(valid.status).toBe(0)

    await writeFile(join(directory, 'styles', '_variables.scss'), ':root {\n  --control-target-min: 44px;\n}\n')
    const invalid = run('scripts/check-design-tokens.cjs', ['--root', directory, '--strict'])
    expect(invalid.status).toBe(1)
    expect(invalid.stderr).toContain('custom-property-definition')
  })

  it('keeps routine browser captures inside the Playwright run output', async () => {
    const source = await readFile(resolve(frontendRoot, 'tests/e2e/foundation.spec.ts'), 'utf8')
    const config = await readFile(resolve(frontendRoot, 'tests/fixtures/foundation.playwright.config.ts'), 'utf8')

    expect(source).toContain('testInfo.outputPath(`foundation-${label}-${theme}.png`)')
    expect(source).not.toMatch(/\/opt\/|streamvault-ux03-delivery|FOUNDATION_CAPTURE_DIR/)
    expect(config).toContain("outputDir: '../../foundation-test-results'")
    expect(config).not.toContain("outputDir: '../../test-results")
  })

  it('requires the parallel workers and keeps every frontend gate fail-closed', async () => {
    const workflow = await readFile(resolve(frontendRoot, '..', '..', '.github/workflows/test.yml'), 'utf8')
    const integrationFlow = await readFile(resolve(frontendRoot, 'scripts/test-foundation-evidence-flow.mjs'), 'utf8')
    const playwrightConfig = await readFile(resolve(frontendRoot, 'playwright.config.ts'), 'utf8')
    const websocketConfig = await readFile(resolve(frontendRoot, 'tests/e2e/websocket-setup-transition.playwright.config.ts'), 'utf8')

    // c787's serial job is intentionally the RED control for the split topology.
    expect(() => assertCaptureIntegrationIsBlocking(workflow, integrationFlow, playwrightConfig, websocketConfig)).toThrow()

    const topology = `jobs:
  frontend-build:
    name: Frontend Build & Lint
    needs: [frontend-core, frontend-browser]
    if: always()
    timeout-minutes: 1
    steps:
      - run: |
          test "${'${{ needs.frontend-core.result }}'}" = success
          test "${'${{ needs.frontend-browser.result }}'}" = success
  frontend-core:
    timeout-minutes: 12
    steps:
      - run: npm run lint:check
      - run: npm run lint:tokens && npm run check:foundation
      - run: npm run type-check
      - run: npm run test:unit && npm run test:foundation-gates
      - run: npx playwright install --with-deps chromium
      - run: node scripts/build-artifact-provenance.mjs build --mode real
      - name: Run real-build WebSocket transition test
        run: STREAMVAULT_REUSE_VERIFIED_REAL_BUILD=true npx playwright test --config tests/e2e/websocket-setup-transition.playwright.config.ts
      - run: npx playwright test --config tests/fixtures/issue894-player.config.ts
      - run: npx playwright test --config tests/fixtures/issue896-player.config.ts
      - run: npm run test:build-output && npm run test:output-budgets
      - if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: frontend-core-failure-evidence
          path: app/frontend/test-results/ app/frontend/foundation-test-results/
  frontend-browser:
    timeout-minutes: 12
    steps:
      - run: npx playwright install --with-deps
      - name: Build verified mock frontend
        run: node scripts/build-artifact-provenance.mjs build --mode mock
      - name: Run frontend browser tests
        run: |
          STREAMVAULT_REUSE_VERIFIED_MOCK_BUILD=true npx playwright test
          STREAMVAULT_REUSE_VERIFIED_MOCK_BUILD=true npm run test:foundation-capture-integration
      - if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: frontend-browser-failure-evidence
          path: app/frontend/test-results/ app/frontend/foundation-test-results/`
    expect(() => assertCaptureIntegrationIsBlocking(topology, integrationFlow, playwrightConfig, websocketConfig)).not.toThrow()

    const mutants = [
      topology.replace('needs: [frontend-core, frontend-browser]', 'needs: [frontend-core]'),
      topology.replace('if: always()', 'if: success()'),
      topology.replace('timeout-minutes: 1', 'timeout-minutes: 12'),
      topology.replace('test "${{ needs.frontend-core.result }}" = success', 'true'),
      topology.replace('    timeout-minutes: 12\n    steps:', '    if: false\n    timeout-minutes: 12\n    steps:'),
      topology.replace('npx playwright install --with-deps chromium', 'npx playwright install --with-deps'),
      topology.replace('node scripts/build-artifact-provenance.mjs build --mode real', 'npm run build'),
      topology.replace('      - name: Run real-build WebSocket transition test\n        run:', '      - name: Run real-build WebSocket transition test\n        if: false\n        run:'),
      topology.replace('tests/fixtures/issue896-player.config.ts', 'tests/fixtures/removed.config.ts'),
      topology.replace('Build verified mock frontend', 'Build mock frontend'),
      topology.replace('node scripts/build-artifact-provenance.mjs build --mode mock', '# mock build removed'),
      topology.replace('      - name: Run frontend browser tests\n        run:', '      - name: Run frontend browser tests\n        if: false\n        run:'),
      topology.replace('STREAMVAULT_REUSE_VERIFIED_MOCK_BUILD=true npm run test:foundation-capture-integration', '# capture integration removed'),
      topology.replace('npx playwright install --with-deps\n      - name: Build', 'npx playwright install --with-deps chromium\n      - name: Build'),
      topology.replace('  frontend-browser:\n    timeout-minutes: 12', '  frontend-browser:\n    continue-on-error: true\n    timeout-minutes: 12'),
    ]
    for (const mutant of mutants) expect(() => assertCaptureIntegrationIsBlocking(mutant, integrationFlow, playwrightConfig, websocketConfig)).toThrow()

    for (const mutant of [
      integrationFlow.replace("run('npm', ['run', 'test:foundation-browser'])", '// foundation run removed'),
      integrationFlow.replace('if (result.status !== 0) process.exit(result.status ?? 1)', '// child failure ignored'),
    ]) expect(() => assertCaptureIntegrationIsBlocking(topology, mutant, playwrightConfig, websocketConfig)).toThrow()
    expect(() => assertCaptureIntegrationIsBlocking(topology, integrationFlow, playwrightConfig.replace('verify --mode mock', 'verify --mode real'), websocketConfig)).toThrow()
    expect(() => assertCaptureIntegrationIsBlocking(topology, integrationFlow, playwrightConfig, websocketConfig.replace('verify --mode real', 'verify --mode mock'))).toThrow()
  })

  it('packages foundation evidence only through an explicit source and destination', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'streamvault-foundation-capture-'))
    const source = join(directory, 'playwright-results', 'nested-run')
    const output = join(directory, 'delivery')
    await mkdir(source, { recursive: true })
    for (const name of captureNames) await writeFile(join(source, name), `fresh-${name}`)

    const missingArguments = run('scripts/package-foundation-evidence.mjs', [])
    expect(missingArguments.status).toBe(1)
    expect(missingArguments.stderr).toContain('--source and --output are required')

    const result = run('scripts/package-foundation-evidence.mjs', ['--source', join(directory, 'playwright-results'), '--output', output])
    expect(result.status).toBe(0)
    for (const name of captureNames) {
      expect(await readFile(join(output, name), 'utf8')).toBe(`fresh-${name}`)
    }
    const manifest = await readFile(join(output, 'FOUNDATION-SHA256SUMS'), 'utf8')
    for (const name of captureNames) expect(manifest).toContain(`  ${name}\n`)
  })
})
