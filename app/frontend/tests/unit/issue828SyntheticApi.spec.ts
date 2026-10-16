// @vitest-environment node
import { createServer } from 'node:http'
import { once } from 'node:events'
import { describe, expect, it } from 'vitest'
import { chapterVariants, syntheticChapters, syntheticReply, syntheticVideos } from '../fixtures/issue828SyntheticApi'

describe('issue 828 synthetic REAL HTTP fixture (not live backend evidence)', () => {
  it('serves real loopback HTTP contracts and closes its listener', async () => {
    let variant: typeof chapterVariants[number] = 'default'
    const server = createServer((request, response) => {
      const reply = syntheticReply(request.url!, request.method, variant)
      response.writeHead(reply.status, { 'Content-Type': 'application/json' })
      response.end(JSON.stringify(reply.body))
    })
    server.listen(0, '127.0.0.1')
    await once(server, 'listening')
    const address = server.address() as { port: number }
    const base = `http://127.0.0.1:${address.port}`
    try {
      expect(await (await fetch(`${base}/auth/setup`)).json()).toEqual({ setup_required: false, welcome_completed: true })
      expect(await (await fetch(`${base}/auth/check`)).json()).toEqual({ authenticated: true })
      expect(await (await fetch(`${base}/api/videos?q=alpha`)).json()).toEqual(syntheticVideos)
      expect(await (await fetch(`${base}/api/videos/1/chapters`)).json()).toEqual(syntheticChapters('default'))
      for (const selected of chapterVariants) {
        variant = selected
        expect(await (await fetch(`${base}/api/videos/40/chapters`)).json()).toEqual(syntheticChapters(selected))
      }
      expect(await (await fetch(`${base}/api/streamers/1/streams`)).json()).toEqual({ streams: syntheticVideos })
      expect(await (await fetch(`${base}/api/stream/1/has-recording`)).json()).toEqual({ has_recording: true })
      expect((await fetch(`${base}/api/unconfigured`)).status).toBe(501)
      expect((await fetch(`${base}/api/videos`, { method: 'DELETE' })).status).toBe(405)
    } finally {
      await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()))
    }
    expect(server.listening).toBe(false)
    await expect(fetch(`${base}/auth/check`)).rejects.toThrow()
  })

  it.each(chapterVariants)('%s preserves numeric backend times, catalog linkage and exact cardinality', variant => {
    const chapters = syntheticChapters(variant)
    expect(chapters).toHaveLength({ zero: 0, default: 1, one: 1, many: 6, long: 80 }[variant])
    expect(syntheticReply('/api/videos/40/chapters', 'GET', variant)).toEqual({ status: 200, body: chapters })
    for (const chapter of chapters) {
      expect(typeof chapter.start).toBe('number')
      expect(chapter.start).toBeGreaterThanOrEqual(0)
      expect(chapter.end).toBeGreaterThanOrEqual(chapter.start)
      expect(chapter.end).toBeLessThanOrEqual(12)
    }
    expect(syntheticVideos.every(video => video.streamer_id === 1 && video.duration === 12 && video.recording_path)).toBe(true)
    if (variant === 'default') expect(chapters[0]).toMatchObject({ title: '', start: 0 })
    if (variant === 'long') expect(chapters.at(-1)!.title.length).toBeGreaterThan(150)
  })
})
