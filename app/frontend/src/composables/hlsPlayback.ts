import hlsWorkerUrl from 'hls.js/dist/hls.worker.js?worker&url'
import type Hls from 'hls.js'
import type { HlsConfig } from 'hls.js'

export const HLS_WORKER_URL = hlsWorkerUrl

type HlsConstructor = typeof Hls
type HlsImporter = () => Promise<HlsConstructor>

export type HlsPlaybackEngine =
  | { mode: 'native' }
  | { mode: 'hls.js'; Hls: HlsConstructor }

export const loadFullHlsJs: HlsImporter = async () => {
  const module = await import('hls.js')
  return module.default
}

export function supportsNativeHls(video: HTMLVideoElement): boolean {
  return Boolean(
    video.canPlayType('application/vnd.apple.mpegurl') ||
    video.canPlayType('application/x-mpegURL')
  )
}

export async function selectHlsPlaybackEngine(
  video: HTMLVideoElement,
  importer: HlsImporter = loadFullHlsJs
): Promise<HlsPlaybackEngine> {
  if (supportsNativeHls(video)) {
    return { mode: 'native' }
  }

  const Hls = await importer()
  if (!Hls.isSupported()) {
    throw new Error('HLS is not supported in this browser')
  }

  return { mode: 'hls.js', Hls }
}

export function createHlsConfig(
  overrides: Partial<HlsConfig> = {}
): Partial<HlsConfig> {
  return {
    enableWorker: true,
    workerPath: HLS_WORKER_URL,
    lowLatencyMode: true,
    backBufferLength: 90,
    maxBufferLength: 30,
    liveSyncDurationCount: 3,
    liveMaxLatencyDurationCount: 5,
    ...overrides
  }
}
