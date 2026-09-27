import { createServer } from 'node:http'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { createReadStream, existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import { join, normalize } from 'node:path'
import { chromium } from 'playwright'

const workspace = await mkdtemp(join(tmpdir(), 'streamvault-media-'))
const mp4Path = join(workspace, 'sample.mp4')
const hlsDir = join(workspace, 'hls')
let server
let browser
let live = true
const observedRanges = []

function generateMedia() {
  const result = spawnSync('ffmpeg', [
    '-hide_banner', '-loglevel', 'error', '-y',
    '-f', 'lavfi', '-i', 'testsrc=size=320x180:rate=24:duration=4',
    '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000:duration=4',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'ultrafast',
    '-c:a', 'aac', '-shortest', '-movflags', '+faststart', mp4Path
  ], { encoding: 'utf8' })
  if (result.status !== 0) throw new Error(`ffmpeg MP4 generation failed: ${result.stderr}`)

  const hls = spawnSync('ffmpeg', [
    '-hide_banner', '-loglevel', 'error', '-y', '-i', mp4Path,
    '-c', 'copy', '-hls_time', '1', '-hls_list_size', '0',
    '-hls_segment_filename', join(hlsDir, 'segment-%03d.ts'),
    join(hlsDir, 'playlist.m3u8')
  ], { encoding: 'utf8' })
  if (hls.status !== 0) throw new Error(`ffmpeg HLS generation failed: ${hls.stderr}`)
}

function sendFile(response, path, contentType) {
  response.writeHead(200, { 'content-type': contentType, 'cache-control': 'no-store' })
  createReadStream(path).pipe(response)
}

try {
  // ffmpeg creates the segment directory only when it already exists.
  await import('node:fs/promises').then(({ mkdir }) => mkdir(hlsDir))
  generateMedia()
  const mp4 = await readFile(mp4Path)
  const hlsBundle = join(process.cwd(), 'node_modules/hls.js/dist/hls.min.js')
  const hlsWorker = join(process.cwd(), 'node_modules/hls.js/dist/hls.worker.js')

  server = createServer((request, response) => {
    const url = new URL(request.url || '/', 'http://127.0.0.1')
    if (url.pathname === '/video.mp4') {
      if (url.searchParams.get('token') === 'expired') {
        response.writeHead(401).end('expired token')
        return
      }
      const range = request.headers.range
      if (range) {
        observedRanges.push(range)
        const match = /^bytes=(\d+)-(\d*)$/.exec(range)
        if (!match) {
          response.writeHead(416, { 'content-range': `bytes */${mp4.length}` }).end()
          return
        }
        const start = Number(match[1])
        const end = match[2] ? Number(match[2]) : mp4.length - 1
        if (start >= mp4.length || end < start || end >= mp4.length) {
          response.writeHead(416, { 'content-range': `bytes */${mp4.length}` }).end()
          return
        }
        response.writeHead(206, {
          'accept-ranges': 'bytes',
          'content-range': `bytes ${start}-${end}/${mp4.length}`,
          'content-length': String(end - start + 1),
          'content-type': 'video/mp4'
        })
        response.end(mp4.subarray(start, end + 1))
        return
      }
      response.writeHead(200, {
        'accept-ranges': 'bytes',
        'content-length': String(mp4.length),
        'content-type': 'video/mp4'
      })
      response.end(mp4)
      return
    }
    if (url.pathname === '/hls/playlist.m3u8') {
      if (url.searchParams.get('token') === 'expired') {
        response.writeHead(401).end('expired token')
        return
      }
      if (!live) {
        response.writeHead(410).end('live session stopped')
        return
      }
      sendFile(response, join(hlsDir, 'playlist.m3u8'), 'application/vnd.apple.mpegurl')
      return
    }
    if (url.pathname.startsWith('/hls/')) {
      const filename = normalize(url.pathname.slice('/hls/'.length))
      const path = join(hlsDir, filename)
      if (!filename.includes('..') && existsSync(path)) {
        sendFile(response, path, 'video/mp2t')
      } else {
        response.writeHead(404).end('missing media')
      }
      return
    }
    if (url.pathname === '/hls.js') {
      sendFile(response, hlsBundle, 'text/javascript')
      return
    }
    if (url.pathname === '/hls.worker.js') {
      sendFile(response, hlsWorker, 'text/javascript')
      return
    }
    if (url.pathname === '/control/stop') {
      live = false
      response.writeHead(204).end()
      return
    }
    if (url.pathname === '/control/start') {
      live = true
      response.writeHead(204).end()
      return
    }
    if (url.pathname === '/missing.mp4') {
      response.writeHead(404).end('missing media')
      return
    }
    response.writeHead(200, { 'content-type': 'text/html' }).end(`<!doctype html>
      <video id="player" muted playsinline></video><script src="/hls.js"></script>`)
  })

  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const address = server.address()
  const origin = `http://127.0.0.1:${address.port}`
  browser = await chromium.launch({ headless: true })
  const page = await browser.newPage()
  await page.goto(origin)

  const range206 = await page.evaluate(async () => {
    const response = await fetch('/video.mp4', { headers: { Range: 'bytes=16-127' } })
    return { status: response.status, range: response.headers.get('content-range'), bytes: (await response.arrayBuffer()).byteLength }
  })
  if (range206.status !== 206 || range206.bytes !== 112 || !range206.range?.startsWith('bytes 16-127/')) {
    throw new Error(`range 206 contract failed: ${JSON.stringify(range206)}`)
  }
  const range416 = await page.evaluate(async () => {
    const response = await fetch('/video.mp4', { headers: { Range: 'bytes=999999-' } })
    return { status: response.status, range: response.headers.get('content-range') }
  })
  if (range416.status !== 416 || !range416.range?.startsWith('bytes */')) {
    throw new Error(`range 416 contract failed: ${JSON.stringify(range416)}`)
  }

  const filePlayback = await page.evaluate(async () => {
    const video = document.querySelector('video')
    video.src = '/video.mp4?token=valid'
    await new Promise((resolve, reject) => {
      video.addEventListener('loadedmetadata', resolve, { once: true })
      video.addEventListener('error', () => reject(new Error('MP4 metadata error')), { once: true })
    })
    video.currentTime = 2
    await new Promise(resolve => video.addEventListener('seeked', resolve, { once: true }))
    await video.play()
    await new Promise(resolve => setTimeout(resolve, 250))
    video.pause()
    return { duration: video.duration, currentTime: video.currentTime, audioTracks: video.webkitAudioDecodedByteCount ?? null }
  })
  if (filePlayback.duration < 3 || filePlayback.currentTime < 2) {
    throw new Error(`file playback/seek failed: ${JSON.stringify(filePlayback)}`)
  }

  const hlsPlayback = await page.evaluate(async () => {
    const video = document.querySelector('video')
    video.removeAttribute('src')
    video.load()
    const hls = new window.Hls({ enableWorker: true, workerPath: '/hls.worker.js' })
    window.__hls = hls
    hls.loadSource('/hls/playlist.m3u8?token=valid')
    hls.attachMedia(video)
    await new Promise((resolve, reject) => {
      hls.on(window.Hls.Events.MANIFEST_PARSED, resolve)
      hls.on(window.Hls.Events.ERROR, (_event, data) => data.fatal && reject(new Error(`${data.type}:${data.details}`)))
    })
    await video.play()
    await new Promise(resolve => setTimeout(resolve, 500))
    return {
      currentTime: video.currentTime,
      decodedAudioBytes: video.webkitAudioDecodedByteCount ?? null,
      alternateAudioTracks: hls.audioTracks.length,
      subtitleTracks: hls.subtitleTracks.length
    }
  })
  if (hlsPlayback.currentTime <= 0 || hlsPlayback.decodedAudioBytes <= 0) {
    throw new Error(`HLS playback failed: ${JSON.stringify(hlsPlayback)}`)
  }

  const failures = await page.evaluate(async () => {
    window.__hls?.destroy()
    const expired = await fetch('/video.mp4?token=expired')
    const missing = await fetch('/missing.mp4')
    await fetch('/control/stop')
    const stopped = await fetch('/hls/playlist.m3u8?token=valid')
    await fetch('/control/start')
    const reconnected = await fetch('/hls/playlist.m3u8?token=valid&reconnect=1')
    return [expired.status, missing.status, stopped.status, reconnected.status]
  })
  if (failures.join(',') !== '401,404,410,200') {
    throw new Error(`media failure contracts failed: ${failures.join(',')}`)
  }

  console.log(JSON.stringify({
    range206,
    range416,
    filePlayback,
    hlsPlayback,
    failures: { expiredToken: 401, missingFile: 404, liveStopped: 410, reconnected: 200 },
    observedRanges
  }, null, 2))
} finally {
  if (browser) await browser.close()
  if (server) await new Promise(resolve => server.close(resolve))
  await rm(workspace, { recursive: true, force: true })
}
