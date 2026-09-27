import { afterEach, describe, expect, it } from 'vitest'
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { measureUx06Loading } from '../check-ux06-loading.mjs'

const workspaces: string[] = []

async function fixture(index: string, urls: string[]) {
  const directory = await mkdtemp(join(tmpdir(), 'ux06-loading-'))
  workspaces.push(directory)
  await mkdir(join(directory, 'assets'))
  await writeFile(join(directory, 'index.html'), index)
  await writeFile(join(directory, 'sw.js'), urls.map(url => `{url:"${url}",revision:"test"}`).join(','))
  for (const url of urls) {
    await writeFile(join(directory, url), url.includes('worker') ? 'worker' : 'chunk')
  }
  return directory
}

afterEach(async () => {
  await Promise.all(workspaces.splice(0).map(directory => rm(directory, { recursive: true, force: true })))
})

describe('UX-06 initial/playback/precache load gate', () => {
  it('separates initial assets from lazy HLS while measuring the precached fallback', async () => {
    const directory = await fixture(
      '<script type="module" src="/assets/index-a.js"></script>',
      ['assets/index-a.js', 'assets/hls-a.js', 'assets/hls.worker-a.js'],
    )
    const result = await measureUx06Loading(directory)
    expect(result.initial.hlsFallbackEntries).toBe(0)
    expect(result.playback.entries).toEqual(['assets/hls-a.js', 'assets/hls.worker-a.js'])
    expect(result.serviceWorkerPrecache.hlsEntries).toEqual(result.playback.entries)
    expect(result.serviceWorkerPrecache.bytes).toBeGreaterThanOrEqual(result.playback.bytes)
  })

  it('fails closed when the fallback leaks into initial document assets', async () => {
    const directory = await fixture(
      '<script type="module" src="/assets/hls-a.js"></script>',
      ['assets/hls-a.js', 'assets/hls.worker-a.js'],
    )
    await expect(measureUx06Loading(directory)).rejects.toThrow('leaked into initial document assets')
  })

  it.each([
    ['missing worker', ['assets/index-a.js', 'assets/hls-a.js']],
    ['duplicate worker', ['assets/index-a.js', 'assets/hls-a.js', 'assets/hls.worker-a.js', 'assets/hls.worker-b.js']],
    ['missing hls chunk', ['assets/index-a.js', 'assets/hls.worker-a.js']],
  ])('fails closed for %s', async (_label, urls) => {
    const directory = await fixture('<script type="module" src="/assets/index-a.js"></script>', urls)
    await expect(measureUx06Loading(directory)).rejects.toThrow(/exactly one/)
  })
})
