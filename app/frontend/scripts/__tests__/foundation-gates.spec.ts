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

function assertCaptureIntegrationIsBlocking(workflow: string) {
  const lines = workflow.split('\n')
  const jobStart = lines.findIndex((line) => line === '  frontend-build:')
  const job = blockFrom(lines, jobStart, 2, /^  [A-Za-z0-9_-]+:\s*$/)

  if (activeProperty(job, 4, 'if') !== undefined) failWorkflow('frontend-build job may be skipped')
  const jobContinueOnError = activeProperty(job, 4, 'continue-on-error')
  if (jobContinueOnError !== undefined && jobContinueOnError !== 'false') failWorkflow('frontend-build job is non-blocking')

  const installStart = job.findIndex((line) => line === '      - name: Install Playwright browsers')
  const browserStart = job.findIndex((line) => line === '      - name: Run frontend browser tests')
  if (installStart < 0 || browserStart <= installStart) failWorkflow('browser test step must follow browser installation')

  const browserStep = blockFrom(job, browserStart, 6, /^      - /)
  if (activeProperty(browserStep, 8, 'if') !== undefined) failWorkflow('browser test step may be skipped')
  const stepContinueOnError = activeProperty(browserStep, 8, 'continue-on-error')
  if (stepContinueOnError !== undefined && stepContinueOnError !== 'false') failWorkflow('browser test step is non-blocking')

  const runStart = browserStep.findIndex((line) => /^        run:\s*[|>]\s*$/.test(line))
  if (runStart < 0) failWorkflow('browser test step has no executable command block')
  const commands = browserStep
    .slice(runStart + 1)
    .filter((line) => indentation(line) > 8 && line.trim() && !line.trimStart().startsWith('#'))
    .map((line) => line.trim())
  const regularSuite = commands.indexOf('npx playwright test')
  const foundationSuite = commands.indexOf('npm run test:foundation-browser')
  const integration = commands.indexOf('npm run test:foundation-capture-integration')
  if (regularSuite < 0 || foundationSuite <= regularSuite || integration <= foundationSuite) {
    failWorkflow('active browser commands are missing or out of order')
  }
  if (commands.some((command) => /\|\|\s*true(?:\s|$)/.test(command))) failWorkflow('browser command has a success fallback')

  const jobText = job.join('\n')
  if (!jobText.includes('app/frontend/test-results/')) failWorkflow('regular browser failure artifacts are missing')
  if (!jobText.includes('app/frontend/foundation-test-results/')) failWorkflow('foundation failure artifacts are missing')
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

  it('keeps routine browser captures inside the Playwright run output', async () => {
    const source = await readFile(resolve(frontendRoot, 'tests/e2e/foundation.spec.ts'), 'utf8')
    const config = await readFile(resolve(frontendRoot, 'tests/fixtures/foundation.playwright.config.ts'), 'utf8')

    expect(source).toContain('testInfo.outputPath(`foundation-${label}-${theme}.png`)')
    expect(source).not.toMatch(/\/opt\/|streamvault-ux03-delivery|FOUNDATION_CAPTURE_DIR/)
    expect(config).toContain("outputDir: '../../foundation-test-results'")
    expect(config).not.toContain("outputDir: '../../test-results")
  })

  it('keeps the real capture integration fail-closed in frontend CI', async () => {
    const workflow = await readFile(resolve(frontendRoot, '..', '..', '.github/workflows/test.yml'), 'utf8')
    assertCaptureIntegrationIsBlocking(workflow)

    const mutants = [
      workflow.replace('          npm run test:foundation-capture-integration', '          # npm run test:foundation-capture-integration'),
      workflow.replace('- name: Run frontend browser tests', '- name: Run frontend browser tests\n        if: false'),
      workflow.replace('        working-directory: app/frontend\n        run: |\n          npx playwright test', '        working-directory: app/frontend\n        continue-on-error: true\n        run: |\n          npx playwright test'),
      workflow.replace('    name: Frontend Build & Lint', '    name: Frontend Build & Lint\n    continue-on-error: true'),
    ]

    for (const mutant of mutants) expect(() => assertCaptureIntegrationIsBlocking(mutant)).toThrow()
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
