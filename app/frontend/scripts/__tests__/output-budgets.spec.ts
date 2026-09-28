import { mkdtemp, writeFile } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'
import { join, resolve } from 'node:path'
import { tmpdir } from 'node:os'
import { describe, expect, it } from 'vitest'
import { assertPrecacheIntegrity, assertSamePrecacheResources } from '../check-precache-integrity.mjs'

const frontendRoot = resolve(import.meta.dirname, '..', '..')
const script = resolve(frontendRoot, 'scripts/check-output-budgets.mjs')
const budgets = resolve(frontendRoot, 'scripts/build-output-budgets.json')

const compliant = {
  files: 84, jsBytes: 1192437, jsGzipBytes: 376335, cssBytes: 812601,
  cssGzipBytes: 119525, totalBytes: 2729765, precacheEntries: 91,
  largestJsBytes: 590144, largestCssBytes: 294607,
}

const compliantWithWorker = {
  ...compliant,
  files: 85,
  jsBytes: compliant.jsBytes + 116764,
  jsGzipBytes: compliant.jsGzipBytes + 40615,
  totalBytes: compliant.totalBytes + 116764,
  hlsWorker: {
    count: 1,
    path: 'assets/hls.worker-R6zLAL9a.js',
    bytes: 116764,
    gzipBytes: 40615,
    packageVersion: '1.7.3',
  },
}

describe('blocking build-output budgets', () => {
  it('rejects duplicate or missing static precache registrations', () => {
    const required = ['favicon.ico', 'icon-512x512.png']
    expect(() => assertPrecacheIntegrity(
      '{url:"favicon.ico",revision:"a"},{url:"favicon.ico",revision:"a"},{url:"icon-512x512.png",revision:"b"}',
      required,
    )).toThrow('Duplicate precache URLs: favicon.ico')
    expect(() => assertPrecacheIntegrity('{url:"favicon.ico",revision:"a"}', required))
      .toThrow('Missing required precache assets: icon-512x512.png')
  })

  it('accepts one registration for every required static asset', () => {
    const required = ['favicon.ico', 'icon-512x512.png']
    expect(assertPrecacheIntegrity(
      '{url:"favicon.ico",revision:"a"},{url:"icon-512x512.png",revision:"b"}',
      required,
    )).toEqual([
      { url: 'favicon.ico', revision: 'a' },
      { url: 'icon-512x512.png', revision: 'b' },
    ])
  })

  it('rejects changed or removed uniquely precached resources', () => {
    const baseline = '{url:"favicon.ico",revision:"a"},{url:"icon-512x512.png",revision:"b"}'
    expect(() => assertSamePrecacheResources(baseline, '{url:"favicon.ico",revision:"a"},{url:"icon-512x512.png",revision:"changed"}'))
      .toThrow('Precache resource changed or missing: icon-512x512.png')
  })

  it('accepts the measured baseline categories without a configured worker allowance', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'streamvault-budget-pass-'))
    const fixture = join(directory, 'metrics.json')
    const baselineBudget = join(directory, 'budget.json')
    await writeFile(fixture, JSON.stringify(compliant))
    await writeFile(baselineBudget, JSON.stringify({
      budgets: {
        jsBytes: 1196533,
        jsGzipBytes: 380431,
        cssBytes: 828985,
        cssGzipBytes: 123621,
        totalBytes: 2754341,
        precacheEntries: 91,
        largestJsBytes: 594240,
        largestCssBytes: 310991,
      },
    }))
    const result = spawnSync(process.execPath, [script, '--fixture', fixture, '--budget', baselineBudget], { encoding: 'utf8' })
    expect(result.status).toBe(0)
  })

  it('isolates one version-matched HLS worker while preserving the application budgets', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'streamvault-budget-worker-pass-'))
    const fixture = join(directory, 'metrics.json')
    await writeFile(fixture, JSON.stringify(compliantWithWorker))
    const result = spawnSync(process.execPath, [script, '--fixture', fixture, '--budget', budgets], { encoding: 'utf8' })
    expect(result.status).toBe(0)
    expect(result.stdout).toContain('applicationJsBytes')
    expect(result.stdout).toContain('hlsWorker')
    expect(result.stdout).toContain(`\"jsBytes\": ${compliantWithWorker.jsBytes}`)
  })

  it.each([
    ['oversized worker', { hlsWorker: { ...compliantWithWorker.hlsWorker, bytes: 116765 }, jsBytes: compliantWithWorker.jsBytes + 1, totalBytes: compliantWithWorker.totalBytes + 1 }],
    ['oversized worker gzip', { hlsWorker: { ...compliantWithWorker.hlsWorker, gzipBytes: 40616 }, jsGzipBytes: compliantWithWorker.jsGzipBytes + 1 }],
    ['duplicate worker', { hlsWorker: { ...compliantWithWorker.hlsWorker, count: 2 } }],
    ['missing worker', { hlsWorker: { ...compliantWithWorker.hlsWorker, count: 0, path: null, bytes: 0, gzipBytes: 0 } }],
    ['wrong package version', { hlsWorker: { ...compliantWithWorker.hlsWorker, packageVersion: '1.7.2' } }],
    ['missing worker metric', { hlsWorker: undefined }],
    ['oversized application despite allowed total', { jsBytes: compliantWithWorker.jsBytes + 4000, hlsWorker: { ...compliantWithWorker.hlsWorker, bytes: 116000 } }],
  ])('rejects %s', async (_name, changed) => {
    const directory = await mkdtemp(join(tmpdir(), 'streamvault-budget-worker-fail-'))
    const fixture = join(directory, 'metrics.json')
    await writeFile(fixture, JSON.stringify({ ...compliantWithWorker, ...changed }))
    const result = spawnSync(process.execPath, [script, '--fixture', fixture, '--budget', budgets], { encoding: 'utf8' })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain('HLS worker budget invalid')
  })

  it('rejects a synthetic CSS and precache regression', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'streamvault-budget-fail-'))
    const fixture = join(directory, 'metrics.json')
    await writeFile(fixture, JSON.stringify({ ...compliantWithWorker, cssBytes: 900000, precacheEntries: 92 }))
    const result = spawnSync(process.execPath, [script, '--fixture', fixture, '--budget', budgets], { encoding: 'utf8' })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain('cssBytes')
    expect(result.stderr).toContain('precacheEntries')
  })
})
