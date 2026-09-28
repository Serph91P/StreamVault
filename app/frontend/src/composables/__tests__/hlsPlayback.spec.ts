import { describe, expect, it, vi } from 'vitest'
import {
  HLS_WORKER_URL,
  createHlsConfig,
  selectHlsPlaybackEngine
} from '../hlsPlayback'

function videoWithNativeSupport(result: CanPlayTypeResult): HTMLVideoElement {
  const video = document.createElement('video')
  vi.spyOn(video, 'canPlayType').mockReturnValue(result)
  return video
}

describe('HLS playback strategy', () => {
  it('uses native HLS before importing hls.js', async () => {
    const importer = vi.fn()

    await expect(selectHlsPlaybackEngine(videoWithNativeSupport('maybe'), importer))
      .resolves.toEqual({ mode: 'native' })
    expect(importer).not.toHaveBeenCalled()
  })

  it('lazy-loads the complete hls.js build only as the fallback', async () => {
    class FakeHls {
      static isSupported = () => true
    }
    const importer = vi.fn().mockResolvedValue(FakeHls)

    await expect(selectHlsPlaybackEngine(videoWithNativeSupport(''), importer))
      .resolves.toEqual({ mode: 'hls.js', Hls: FakeHls })
    expect(importer).toHaveBeenCalledTimes(1)
  })

  it('reports unsupported playback without substituting a light build or CDN', async () => {
    class UnsupportedHls {
      static isSupported = () => false
    }

    await expect(selectHlsPlaybackEngine(
      videoWithNativeSupport(''),
      vi.fn().mockResolvedValue(UnsupportedHls)
    )).rejects.toThrow('HLS is not supported')
  })

  it('binds the version-matched worker asset to the same origin and keeps inline fallback enabled', () => {
    const config = createHlsConfig()
    const workerUrl = new URL(HLS_WORKER_URL, window.location.href)

    expect(workerUrl.origin).toBe(window.location.origin)
    expect(workerUrl.pathname).toMatch(/hls\.worker(?:-[\w]+)?\.js$/)
    expect(config).toMatchObject({
      enableWorker: true,
      workerPath: HLS_WORKER_URL
    })
  })
})
