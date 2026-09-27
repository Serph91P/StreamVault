import { readFile, stat } from 'node:fs/promises'
import { resolve } from 'node:path'
import { precacheEntries } from './check-precache-integrity.mjs'

const localAssetPattern = /(?:src|href)="\/?([^"?#]+)"/g
const hlsChunkPattern = /^assets\/hls-(?!worker-)[\w-]+\.js$/
const hlsWorkerPattern = /^assets\/hls\.worker-[\w-]+\.js$/

export async function measureUx06Loading(distDirectory = resolve(process.cwd(), 'dist')) {
  const [indexSource, swSource] = await Promise.all([
    readFile(resolve(distDirectory, 'index.html'), 'utf8'),
    readFile(resolve(distDirectory, 'sw.js'), 'utf8'),
  ])
  const precache = precacheEntries(swSource)
  const urls = precache.map(entry => entry.url.replace(/^\//, ''))
  const hlsChunks = urls.filter(url => hlsChunkPattern.test(url))
  const workers = urls.filter(url => hlsWorkerPattern.test(url))
  if (hlsChunks.length !== 1) throw new Error(`Expected exactly one precached lazy hls.js chunk, found ${hlsChunks.length}`)
  if (workers.length !== 1) throw new Error(`Expected exactly one precached hls.js worker, found ${workers.length}`)

  const initialAssets = [...indexSource.matchAll(localAssetPattern)]
    .map(([, url]) => url)
    .filter(url => !url.startsWith('http') && !url.startsWith('data:'))
  const initialHls = initialAssets.filter(url => hlsChunkPattern.test(url) || hlsWorkerPattern.test(url))
  if (initialHls.length > 0) throw new Error(`HLS fallback leaked into initial document assets: ${initialHls.join(', ')}`)

  const fileBytes = async (url) => (await stat(resolve(distDirectory, url))).size
  const initialEntries = ['index.html', ...new Set(initialAssets)]
  const initialBytes = (await Promise.all(initialEntries.map(fileBytes))).reduce((sum, bytes) => sum + bytes, 0)
  const playbackEntries = [hlsChunks[0], workers[0]]
  const playbackBytes = (await Promise.all(playbackEntries.map(fileBytes))).reduce((sum, bytes) => sum + bytes, 0)
  const precacheBytes = (await Promise.all(urls.map(fileBytes))).reduce((sum, bytes) => sum + bytes, 0)
  const hlsPrecacheBytes = playbackBytes

  if (playbackBytes <= 0 || precacheBytes < playbackBytes) throw new Error('Invalid UX-06 load measurement')

  return {
    initial: { entries: initialEntries, bytes: initialBytes, hlsFallbackEntries: 0 },
    playback: { entries: playbackEntries, bytes: playbackBytes },
    serviceWorkerPrecache: { entries: urls.length, bytes: precacheBytes, hlsEntries: playbackEntries, hlsBytes: hlsPrecacheBytes },
  }
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  try {
    console.log(JSON.stringify(await measureUx06Loading(), null, 2))
  } catch (error) {
    console.error(error instanceof Error ? error.message : error)
    process.exitCode = 1
  }
}
