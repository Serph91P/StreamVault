import { afterEach, describe, expect, it } from 'vitest'
import { mkdtemp, mkdir, rm, stat, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { tmpdir } from 'node:os'
import { measureUx06Loading } from '../check-ux06-loading.mjs'

const workspaces: string[] = []

async function fixture(index: string, urls: string[], files = Object.fromEntries(
  urls.map(url => [url, url.includes('worker') ? 'worker' : 'chunk']),
)) {
  const directory = await mkdtemp(join(tmpdir(), 'ux06-loading-'))
  workspaces.push(directory)
  await mkdir(join(directory, 'assets'))
  await writeFile(join(directory, 'index.html'), index)
  await writeFile(join(directory, 'sw.js'), urls.map(url => `{url:"${url}",revision:"test"}`).join(','))
  for (const [file, content] of Object.entries(files)) {
    await mkdir(dirname(join(directory, file)), { recursive: true })
    await writeFile(join(directory, file), content)
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

  it.each(['index.html', 'push-sw.js', 'images/logo.png'])(
    'measures canonical pwa/%s against the emitted file without changing resource identities', async (file) => {
      const publicUrl = `pwa/${file}`
      const index = file === 'index.html' ? '<main>app shell</main>' : `<link href="/${publicUrl}">`
      const files = { 'assets/hls-a.js': 'chunk', 'assets/hls.worker-a.js': 'worker' }
      const directory = await fixture(index, [publicUrl, ...Object.keys(files)], files)
      if (file !== 'index.html') {
        await mkdir(dirname(join(directory, file)), { recursive: true })
        await writeFile(join(directory, file), 'resource')
      }
      const resourceBytes = file === 'index.html' ? Buffer.byteLength(index) : 8
      const result = await measureUx06Loading(directory)
      expect(result).toEqual({
        initial: {
          entries: file === 'index.html' ? ['index.html'] : ['index.html', publicUrl],
          bytes: Buffer.byteLength(index) + (file === 'index.html' ? 0 : resourceBytes),
          hlsFallbackEntries: 0,
        },
        playback: { entries: Object.keys(files), bytes: 11 },
        serviceWorkerPrecache: { entries: 3, bytes: resourceBytes + 11, hlsEntries: Object.keys(files), hlsBytes: 11 },
      })
    },
  )

  it.each(['pwa/index.html', 'pwa/push-sw.js', 'pwa/images/missing.png', 'assets/missing.js'])(
    'fails closed for missing precached %s', async (url) => {
      const files = { 'assets/hls-a.js': 'chunk', 'assets/hls.worker-a.js': 'worker' }
      const directory = await fixture('', [url, ...Object.keys(files)], files)
      if (url === 'pwa/index.html') await rm(join(directory, 'index.html'))
      await expect(measureUx06Loading(directory)).rejects.toMatchObject({ code: 'ENOENT' })
    },
  )

  it('does not remap unknown PWA routes to existing root files', async () => {
    const files = { 'assets/hls-a.js': 'chunk', 'assets/hls.worker-a.js': 'worker', 'unknown.js': 'not a public PWA route' }
    const directory = await fixture('', ['pwa/unknown.js', 'assets/hls-a.js', 'assets/hls.worker-a.js'], files)
    await expect(measureUx06Loading(directory)).rejects.toMatchObject({ code: 'ENOENT' })
  })

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
    ['duplicate hls chunk', ['assets/index-a.js', 'assets/hls-a.js', 'assets/hls-b.js', 'assets/hls.worker-a.js']],
  ])('fails closed for %s', async (_label, urls) => {
    const directory = await fixture('<script type="module" src="/assets/index-a.js"></script>', urls)
    await expect(measureUx06Loading(directory)).rejects.toThrow(/exactly one/)
  })
})
