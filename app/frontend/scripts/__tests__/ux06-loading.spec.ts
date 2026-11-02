import { afterEach, describe, expect, it } from 'vitest'
import { mkdtemp, mkdir, rm, stat, writeFile } from 'node:fs/promises'
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

async function pwaFixture() {
  const urls = ['assets/index-a.js', 'assets/hls-a.js', 'assets/hls.worker-a.js']
  const directory = await fixture('<script src="/assets/index-a.js"></script><link href="/pwa/images/categories/default-category.svg">', urls)
  await mkdir(join(directory, 'images/categories'), { recursive: true })
  await writeFile(join(directory, 'push-sw.js'), 'actual public helper')
  await writeFile(join(directory, 'images/categories/default-category.svg'), '<svg/>')
  urls.push('pwa/push-sw.js', 'pwa/index.html', 'pwa/images/categories/default-category.svg')
  await writeFile(join(directory, 'sw.js'), urls.map(url => `{url:"${url}",revision:"test"}`).join(','))
  return { directory, urls }
}

afterEach(async () => {
  await Promise.all(workspaces.splice(0).map(directory => rm(directory, { recursive: true, force: true })))
})

describe('UX-06 initial/playback/precache load gate', () => {
  it('counts every aliased PWA resource from its actual build file', async () => {
    const { directory, urls } = await pwaFixture()
    const result = await measureUx06Loading(directory)
    const diskFiles = ['assets/index-a.js', 'assets/hls-a.js', 'assets/hls.worker-a.js', 'push-sw.js', 'index.html', 'images/categories/default-category.svg']
    const bytes = await Promise.all(diskFiles.map(async file => (await stat(join(directory, file))).size))
    expect(result.serviceWorkerPrecache.entries).toBe(urls.length)
    expect(result.serviceWorkerPrecache.bytes).toBe(bytes.reduce((sum, size) => sum + size, 0))
    expect(result.initial.entries).toContain('pwa/images/categories/default-category.svg')
    expect(result.initial.bytes).toBe(bytes[0]! + bytes[4]! + bytes[5]!)
    expect(result.playback.entries).toEqual(['assets/hls-a.js', 'assets/hls.worker-a.js'])
    expect(result.playback.bytes).toBe(bytes[1]! + bytes[2]!)
  })

  it.each(['push-sw.js', 'index.html', 'images/categories/default-category.svg'])(
    'fails closed when the actual aliased build file %s is missing', async missing => {
      const { directory } = await pwaFixture()
      await rm(join(directory, missing))
      await expect(measureUx06Loading(directory)).rejects.toMatchObject({ code: 'ENOENT', path: join(directory, missing) })
    },
  )

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
