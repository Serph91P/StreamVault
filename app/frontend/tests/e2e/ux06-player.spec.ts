import { expect, test, type Page } from '@playwright/test'
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { tmpdir } from 'node:os'

declare global {
  interface Window {
    _uWorkerUrls: string[]
    _uWorkersAfterUnmount: number
    _uFailedWorkerUrls: string[]
    u: boolean | null
  }
}

let mediaDirectory = ''
const mediaFiles = new Map<string, Buffer>()

test.beforeAll(async () => {
  mediaDirectory = await mkdtemp(join(tmpdir(), 'streamvault-product-player-'))
  await mkdir(join(mediaDirectory, 'hls'))
  const source = join(mediaDirectory, 'source.mp4')
  const generated = spawnSync('ffmpeg', [
    '-hide_banner', '-loglevel', 'error', '-y',
    '-f', 'lavfi', '-i', 'testsrc=size=320x180:rate=24:duration=8',
    '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000:duration=8',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'ultrafast',
    '-c:a', 'aac', '-shortest', source,
  ], { encoding: 'utf8' })
  if (generated.status !== 0) throw new Error(`ffmpeg source generation failed: ${generated.stderr}`)

  const variants = [
    ['video', '-map', '0:v:0', '-c:v', 'copy', '-an'],
    ['audio-en', '-map', '0:a:0', '-c:a', 'copy', '-vn'],
    ['audio-commentary', '-map', '0:a:0', '-c:a', 'copy', '-vn'],
  ]
  for (const [name, ...mapping] of variants) {
    const converted = spawnSync('ffmpeg', [
      '-hide_banner', '-loglevel', 'error', '-y', '-i', source,
      ...mapping, '-hls_time', '2', '-hls_list_size', '0',
      '-hls_segment_filename', join(mediaDirectory, 'hls', `${name}-%03d.ts`),
      join(mediaDirectory, 'hls', `${name}.m3u8`),
    ], { encoding: 'utf8' })
    if (converted.status !== 0) throw new Error(`ffmpeg ${name} HLS generation failed: ${converted.stderr}`)
  }

  await writeFile(join(mediaDirectory, 'hls', 'subtitle-en.vtt'), 'WEBVTT\n\n00:00.000 --> 00:04.000\nSynthetic subtitle\n')
  await writeFile(join(mediaDirectory, 'hls', 'subtitle-en.m3u8'), '#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:4\n#EXT-X-MEDIA-SEQUENCE:0\n#EXTINF:4.000,\nsubtitle-en.vtt\n#EXT-X-ENDLIST\n')
  await writeFile(join(mediaDirectory, 'hls', 'playlist.m3u8'), `#EXTM3U
#EXT-X-VERSION:3
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="English",LANGUAGE="en",DEFAULT=YES,AUTOSELECT=YES,URI="audio-en.m3u8"
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="Commentary",LANGUAGE="en",DEFAULT=NO,AUTOSELECT=NO,URI="audio-commentary.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="English",LANGUAGE="en",DEFAULT=YES,AUTOSELECT=YES,FORCED=NO,URI="subtitle-en.m3u8"
#EXT-X-STREAM-INF:BANDWIDTH=900000,AVERAGE-BANDWIDTH=700000,CODECS="avc1.42c00d,mp4a.40.2",RESOLUTION=320x180,AUDIO="audio",SUBTITLES="subs"
video.m3u8
`)

  for (const name of await readdir(join(mediaDirectory, 'hls'))) {
    mediaFiles.set(name, await readFile(join(mediaDirectory, 'hls', name)))
  }
})

test.afterAll(async () => {
  if (mediaDirectory) await rm(mediaDirectory, { recursive: true, force: true })
})

async function serveSyntheticLiveMedia(page: Page) {
  let playlistRequests = 0
  const requests = new Map<string, number>()
  await page.route('**/api/live/stream/mock/**', async route => {
    const name = new URL(route.request().url()).pathname.split('/').pop() || ''
    requests.set(name, (requests.get(name) || 0) + 1)
    const body = mediaFiles.get(name)
    if (!body) return route.fulfill({ status: 404, body: 'missing synthetic media' })
    if (name === 'playlist.m3u8') playlistRequests += 1
    const contentType = name.endsWith('.m3u8')
      ? 'application/vnd.apple.mpegurl'
      : name.endsWith('.vtt') ? 'text/vtt' : 'video/mp2t'
    await route.fulfill({ status: 200, contentType, body })
  })
  return {
    playlistRequests: () => playlistRequests,
    requestsFor: (name: string) => requests.get(name) || 0,
  }
}

test('measures initial, playback and active-service-worker precache loads separately', async ({ page, context }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'one deterministic PWA network measurement is sufficient')
  await page.goto('/videos')
  const initial = await page.evaluate(() => {
    const resources = performance.getEntriesByType('resource') as PerformanceResourceTiming[]
    return {
      entries: resources.map(entry => new URL(entry.name).pathname),
      encodedBytes: resources.reduce((sum, entry) => sum + entry.encodedBodySize, 0),
      transferBytes: resources.reduce((sum, entry) => sum + entry.transferSize, 0),
    }
  })
  expect(initial.entries.some(url => /\/assets\/hls(?:\.worker)?-/.test(url))).toBe(false)

  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
    await new Promise<void>((resolve, reject) => {
      const deadline = Date.now() + 10_000
      const inspect = async () => {
        const keys = await caches.keys()
        const requests = (await Promise.all(keys.map(key => caches.open(key).then(cache => cache.keys())))).flat()
        if (requests.some(request => /\/assets\/hls-/.test(request.url)) && requests.some(request => /\/assets\/hls\.worker-/.test(request.url))) return resolve()
        if (Date.now() >= deadline) return reject(new Error('HLS fallback was not downloaded into the active service-worker precache'))
        window.setTimeout(inspect, 50)
      }
      void inspect()
    })
  })
  const precache = await page.evaluate(async () => {
    const keys = await caches.keys()
    const entries: Array<{ url: string; bytes: number }> = []
    for (const key of keys) {
      const cache = await caches.open(key)
      for (const request of await cache.keys()) {
        const response = await cache.match(request)
        entries.push({ url: new URL(request.url).pathname, bytes: response ? (await response.arrayBuffer()).byteLength : 0 })
      }
    }
    const hlsEntries = entries.filter(entry => /\/assets\/hls(?:\.worker)?-/.test(entry.url))
    return {
      entries: entries.length,
      bytes: entries.reduce((sum, entry) => sum + entry.bytes, 0),
      hlsEntries,
      hlsBytes: hlsEntries.reduce((sum, entry) => sum + entry.bytes, 0),
    }
  })
  expect(precache.hlsEntries).toHaveLength(2)
  expect(precache.hlsBytes).toBeGreaterThan(0)

  await serveSyntheticLiveMedia(page)
  await page.addInitScript(() => {
    const nativeCanPlayType = HTMLMediaElement.prototype.canPlayType
    HTMLMediaElement.prototype.canPlayType = function (type: string) {
      return /mpegurl/i.test(type) ? '' : nativeCanPlayType.call(this, type)
    }
  })
  const playbackRequests: string[] = []
  context.on('request', request => {
    const path = new URL(request.url()).pathname
    if (/\/assets\/hls(?:\.worker)?-/.test(path)) playbackRequests.push(path)
  })
  await page.goto('/live/product-player')
  await expect.poll(() => page.locator('video.video-element').evaluate(element => (element as HTMLVideoElement).currentTime), { timeout: 15_000 }).toBeGreaterThan(0)
  await expect.poll(() => new Set(playbackRequests).size).toBe(2)
  const playback = await page.evaluate(() => {
    const entries = (performance.getEntriesByType('resource') as PerformanceResourceTiming[])
      .filter(entry => /\/assets\/hls(?:\.worker)?-/.test(new URL(entry.name).pathname))
    return {
      entries: entries.map(entry => new URL(entry.name).pathname),
      encodedBytes: entries.reduce((sum, entry) => sum + entry.encodedBodySize, 0),
      transferBytes: entries.reduce((sum, entry) => sum + entry.transferSize, 0),
    }
  })
  expect(new Set(playback.entries).size).toBe(2)
  const measurement = { initial, playback, precache }
  console.log(`UX06_PWA_MEASUREMENT ${JSON.stringify(measurement)}`)
  if (process.env.UX06_ARTIFACT_DIR) {
    await writeFile(join(process.env.UX06_ARTIFACT_DIR, 'ux06-pwa-load-measurement.json'), JSON.stringify(measurement, null, 2))
  }
  await testInfo.attach('ux06-pwa-load-measurement.json', {
    body: Buffer.from(JSON.stringify(measurement, null, 2)),
    contentType: 'application/json',
  })
})

test('built live player requests its same-origin worker and plays synthetic HLS', async ({ page }, testInfo) => {
  const media = await serveSyntheticLiveMedia(page)
  await page.addInitScript((theme: string) => {
    localStorage.setItem('streamvault-theme', theme)
    const nativeCanPlayType = HTMLMediaElement.prototype.canPlayType
    HTMLMediaElement.prototype.canPlayType = function (type: string) {
      return /mpegurl/i.test(type) ? '' : nativeCanPlayType.call(this, type)
    }
    const NativeWorker = window.Worker
    window._uWorkerUrls = []
    window.Worker = class extends NativeWorker {
      constructor(url: string | URL, options?: WorkerOptions) {
        window._uWorkerUrls.push(String(url))
        super(url, options)
      }
    }
  }, testInfo.project.name === 'mobile' ? 'light' : 'dark')

  await page.goto('/live/product-player?t=1')
  const video = page.locator('video.video-element')
  await expect(video).toBeVisible()
  await expect.poll(() => page.evaluate(() => window._uWorkerUrls.length)).toBe(1)
  await expect.poll(() => page.evaluate(() => window._uWorkerUrls[0])).toMatch(/\/assets\/hls\.worker-[\w-]+\.js$/)
  await expect.poll(() => video.evaluate(element => (element as HTMLVideoElement).currentTime), { timeout: 15_000 }).toBeGreaterThan(0)
  await expect.poll(media.playlistRequests).toBeGreaterThan(0)
  await expect(video).toHaveAttribute('data-audio-tracks', '2')
  await expect(video).toHaveAttribute('data-subtitle-tracks', '1')
  const playbackBeforeTrackSwitch = await video.evaluate(element => (element as HTMLVideoElement).currentTime)
  await video.evaluate(element => {
    ;(element as HTMLVideoElement & { u: (audio: number, subtitle: number) => void }).u(1, 0)
  })
  await expect.poll(() => media.requestsFor('audio-commentary.m3u8')).toBeGreaterThan(0)
  await expect.poll(() => media.requestsFor('audio-commentary-000.ts')).toBeGreaterThan(0)
  await expect.poll(() => media.requestsFor('subtitle-en.m3u8')).toBeGreaterThan(0)
  await expect.poll(() => media.requestsFor('subtitle-en.vtt')).toBeGreaterThan(0)
  await expect.poll(() => video.evaluate(element => Array.from((element as HTMLVideoElement).textTracks)
    .some(track => Array.from(track.cues || []).some(cue => (cue as VTTCue).text === 'Synthetic subtitle')))).toBe(true)
  await expect.poll(() => video.evaluate(element => (element as HTMLVideoElement).currentTime)).toBeGreaterThan(playbackBeforeTrackSwitch)
  await expect(page.getByText('Codecs').locator('..').getByText('h264')).toBeVisible()
  const screenshotPath = process.env.UX06_ARTIFACT_DIR
    ? join(process.env.UX06_ARTIFACT_DIR, `ux06-live-player-${testInfo.project.name}.png`)
    : testInfo.outputPath('ux06-live-player.png')
  await page.screenshot({ path: screenshotPath, fullPage: true })

  await page.getByRole('link', { name: 'Library' }).click()
  await expect(page).toHaveURL(/\/videos$/)
  await expect(video).toHaveCount(0)
})

test.describe('delayed fallback lifecycle', () => {
  test.use({ serviceWorkers: 'block' })

  test('SPA unmount during delayed fallback import creates no worker or media request', async ({ page }) => {
  let releaseHlsChunk!: () => void
  const hlsChunkReleased = new Promise<void>(resolve => { releaseHlsChunk = resolve })
  let hlsChunkRequests = 0
  let playlistRequests = 0
  let workerRequests = 0
  await page.route('**/assets/hls-*.js', async route => {
    hlsChunkRequests += 1
    await hlsChunkReleased
    await route.continue()
  })
  await page.route('**/assets/hls.worker-*.js', async route => {
    workerRequests += 1
    await route.continue()
  })
  await page.route('**/api/live/stream/mock/**', async route => {
    playlistRequests += 1
    await route.abort()
  })
  await page.addInitScript(() => {
    const nativeCanPlayType = HTMLMediaElement.prototype.canPlayType
    HTMLMediaElement.prototype.canPlayType = function (type: string) {
      return /mpegurl/i.test(type) ? '' : nativeCanPlayType.call(this, type)
    }
    window._uWorkersAfterUnmount = 0
    window.u = null
    const NativeWorker = window.Worker
    window.Worker = class extends NativeWorker {
      constructor(url: string | URL, options?: WorkerOptions) {
        window._uWorkersAfterUnmount += 1
        super(url, options)
      }
    }
  })

  await page.goto('/live/product-player?t=1')
  await expect(page.locator('video.video-element')).toBeVisible()
  await expect.poll(() => hlsChunkRequests, { timeout: 10_000 }).toBe(1)
  await page.getByRole('link', { name: 'Library' }).click()
  await expect(page).toHaveURL(/\/videos$/)
  await expect(page.locator('video.video-element')).toHaveCount(0)
  releaseHlsChunk()
  await expect.poll(() => page.evaluate(() => window.u), { timeout: 10_000 }).toBe(false)
  expect(workerRequests).toBe(0)
  expect(playlistRequests).toBe(0)
  await expect.poll(() => page.evaluate(() => window._uWorkersAfterUnmount)).toBe(0)
  })
})

test('mobile actions stay scrollable, focusable and touch reachable above bottom navigation', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'mobile reachability proof')
  await serveSyntheticLiveMedia(page)
  await page.addInitScript(() => {
    const nativeCanPlayType = HTMLMediaElement.prototype.canPlayType
    HTMLMediaElement.prototype.canPlayType = function (type: string) {
      return /mpegurl/i.test(type) ? '' : nativeCanPlayType.call(this, type)
    }
  })
  await page.goto('/live/product-player')
  const title = page.getByRole('heading', { name: 'product-player' })
  await expect(title).toBeVisible()
  const titleBox = await title.boundingBox()
  expect(titleBox?.x).toBeGreaterThanOrEqual(0)

  const stop = page.getByRole('button', { name: 'Stop Stream' })
  await stop.scrollIntoViewIfNeeded()
  await stop.focus()
  await expect(stop).toBeFocused()
  const stopBox = await stop.boundingBox()
  const navBox = await page.locator('.bottom-nav').boundingBox()
  expect(stopBox).not.toBeNull()
  expect(navBox).not.toBeNull()
  expect((stopBox?.y || 0) + (stopBox?.height || 0)).toBeLessThanOrEqual(navBox?.y || 0)
  await stop.tap()
  await expect(page.getByText('Stream Stopped')).toBeVisible()
})

test('unsupported HEVC selection falls back to H264 before real playback', async ({ page }) => {
  await serveSyntheticLiveMedia(page)
  await page.addInitScript(() => {
    const nativeCanPlayType = HTMLMediaElement.prototype.canPlayType
    HTMLMediaElement.prototype.canPlayType = function (type: string) {
      if (/mpegurl|hvc1|hev1/i.test(type)) return ''
      return nativeCanPlayType.call(this, type)
    }
  })
  await page.goto('/live/product-player?codec=hevc')
  await expect(page.getByText('HEVC live playback needs native HLS support')).toBeVisible()
  await expect(page.getByText('Codecs').locator('..').getByText('h264')).toBeVisible()
  await expect.poll(() => page.locator('video.video-element').evaluate(element => (element as HTMLVideoElement).currentTime), { timeout: 15_000 }).toBeGreaterThan(0)
})

test('built live player falls back to the main thread when the worker cannot load', async ({ page }) => {
  await serveSyntheticLiveMedia(page)
  await page.addInitScript(() => {
    const nativeCanPlayType = HTMLMediaElement.prototype.canPlayType
    HTMLMediaElement.prototype.canPlayType = function (type: string) {
      return /mpegurl/i.test(type) ? '' : nativeCanPlayType.call(this, type)
    }
    window._uFailedWorkerUrls = []
    window.Worker = class {
      constructor(url: string | URL) {
        window._uFailedWorkerUrls.push(String(url))
        throw new Error('synthetic worker load failure')
      }
    } as unknown as typeof Worker
  })

  await page.goto('/live/product-player')
  const video = page.locator('video.video-element')
  await expect(video).toBeVisible()
  await expect.poll(() => page.evaluate(() => window._uFailedWorkerUrls.length)).toBeGreaterThan(0)
  await expect.poll(() => page.evaluate(() => new Set(window._uFailedWorkerUrls).size)).toBe(1)
  await expect.poll(() => video.evaluate(element => (element as HTMLVideoElement).currentTime), { timeout: 15_000 }).toBeGreaterThan(0)
  await expect(page.getByText('Stream playback failed')).toHaveCount(0)
})

for (const { status, message } of [
  { status: 401, message: 'Your playback session expired' },
  { status: 403, message: 'You do not have permission to play this stream' },
  { status: 404, message: 'The live stream media is unavailable' },
]) {
  test(`built live player presents HTTP ${status} without an endless reconnect`, async ({ page }) => {
    await page.addInitScript(() => {
      const nativeCanPlayType = HTMLMediaElement.prototype.canPlayType
      HTMLMediaElement.prototype.canPlayType = function (type: string) {
        return /mpegurl/i.test(type) ? '' : nativeCanPlayType.call(this, type)
      }
    })
    await page.route('**/api/live/stream/mock/playlist.m3u8', route => route.fulfill({ status, body: 'synthetic media failure' }))

    await page.goto('/live/product-player')
    await expect(page.getByText(message)).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('Reconnecting...')).toHaveCount(0)
  })
}

test('built live player treats HTTP 410 as an ended live session', async ({ page }) => {
  await page.addInitScript(() => {
    const nativeCanPlayType = HTMLMediaElement.prototype.canPlayType
    HTMLMediaElement.prototype.canPlayType = function (type: string) {
      return /mpegurl/i.test(type) ? '' : nativeCanPlayType.call(this, type)
    }
  })
  await page.route('**/api/live/stream/mock/playlist.m3u8', route => route.fulfill({ status: 410, body: 'stopped' }))

  await page.goto('/live/product-player')
  await expect(page.getByText('Stream Stopped')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('Reconnecting...')).toHaveCount(0)
})
