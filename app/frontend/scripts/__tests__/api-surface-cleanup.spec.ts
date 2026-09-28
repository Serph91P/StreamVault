import { readFileSync } from 'node:fs'
import { mkdtemp, readFile, readdir } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import { extname, join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const frontendRoot = resolve(import.meta.dirname, '..', '..')
const facadeSource = readFileSync(resolve(frontendRoot, 'src/services/api.ts'), 'utf8')
const realSource = readFileSync(resolve(frontendRoot, 'src/services/api-real.ts'), 'utf8')
const loggerSource = readFileSync(resolve(frontendRoot, 'src/utils/logger.ts'), 'utf8')
const forceRecordingSource = readFileSync(resolve(frontendRoot, 'src/composables/useForceRecording.ts'), 'utf8')
const forceRecordingDiagnostics = [
  {
    message: 'Live status check failed, API may be temporarily unavailable:',
    guardedSource: "if (import.meta.env.DEV) {\n          console.warn('Live status check failed, API may be temporarily unavailable:'",
  },
  {
    message: 'Cannot verify live status due to API failure, proceeding with backend validation',
    guardedSource: "if (import.meta.env.DEV) {\n          console.warn('Cannot verify live status due to API failure, proceeding with backend validation')",
  },
  {
    message: 'Streamer appears to be offline according to API, but continuing with force recording attempt',
    guardedSource: "if (import.meta.env.DEV) {\n          console.warn('Streamer appears to be offline according to API, but continuing with force recording attempt')",
  },
  {
    message: 'Error force starting recording:',
    guardedSource: "if (import.meta.env.DEV) {\n        console.error('Error force starting recording:'",
  },
]
const pwaSource = readFileSync(resolve(frontendRoot, 'src/composables/usePWA.ts'), 'utf8')

async function collectFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true })
  const paths = await Promise.all(entries.map(async entry => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? collectFiles(path) : [path]
  }))
  return paths.flat()
}
const settingsSources = [
  'FavoritesSettingsPanel.vue',
  'NotificationSettingsPanel.vue',
  'ProxySettingsPanel.vue',
  'PWAPanel.vue',
  'RecordingSettingsPanel.vue',
  'TwitchConnectionPanel.vue',
].map(file => readFileSync(resolve(frontendRoot, 'src/components/settings', file), 'utf8'))

const retiredFacadeSymbols = [
  'mockImagesApi',
  'export const imagesApi',
]

const retiredRealSymbols = [
  'export const streamerApi',
  'export const imagesApi',
]

const retiredMethods = [
  'add: (username:',
  'validate: (username:',
  'deleteStream:',
  'forceRecord:',
  'getById:',
  'regenerateMetadata:',
  'stop: (_streamerId:',
  'startRecording:',
  'getSettings:',
  'forceStopRecording:',
  'getDebugLiveStatus:',
  'getSubscriptions:',
  'deleteSubscriptions:',
  'deleteSubscription:',
  'getRecordingStatus:',
  'deleteRecording:',
  'getRecordingHistory:',
  'checkStreamerLiveStatus:',
  'getTask:',
  'enqueueTask:',
  'enqueueMetadataGeneration:',
  'enqueueThumbnailGeneration:',
  'enqueueFileCleanup:',
  'getHealth:',
  'getBackgroundQueueStatus:',
  'getStreamers: () =>',
  'testNotification:',
  'testWebSocketNotification:',
  'getByStreamerId:',
  'getByStreamerName:',
  'getByStreamerAndFilename:',
  'getByFilename:',
  'streamVideo:',
  'getThumbnail:',
  'getPublicVideo:',
  'getDebugInfo:',
  'getTestVideo:',
  'getDebugDatabase:',
  'getDebugRecordingsDirectory:',
  'checkRecordings:',
  'handleCallback:',
  'login: (_data:',
  'logout: () =>',
  'check: () =>',
  'setup: () =>',
  'getConnectionStatus:',
  'exchangeCode:',
  'disconnect: () =>',
  'importFollowedChannels:',
  'getAll: () => mockResponse([])',
  'getFavorites:',
  'addFavorite:',
  'removeFavorite:',
  'getImagesBatch:',
  'cleanupImages:',
  'getMissingImages:',
  'create: (data:',
  'update: (_id:',
  'getLiveStreamStatus:',
  'getActiveLiveStreams:',
  'getCacheStatus:',
  'refreshImages:',
]

describe('public API surface cleanup', () => {
  it('does not reintroduce retired facade aliases without a consumer', () => {
    for (const symbol of retiredFacadeSymbols) expect(facadeSource).not.toContain(symbol)
    for (const symbol of retiredRealSymbols) expect(realSource).not.toContain(symbol)
  })

  it('does not retain endpoint wrappers that have no frontend consumer', () => {
    for (const method of retiredMethods) {
      expect(facadeSource, method).not.toContain(method)
      expect(realSource, method).not.toContain(method)
    }
  })

  it('keeps the production logger free of the unused legacy class and levels', () => {
    for (const symbol of ['enum LogLevel', 'class Logger', 'logWarn', 'logInfo']) {
      expect(loggerSource).not.toContain(symbol)
    }
  })

  it('keeps API-mode diagnostics development-only so production bundles omit them', () => {
    expect(facadeSource).toContain('if (import.meta.env.DEV) {')
  })

  it('keeps every force-recording diagnostic development-only and out of production bundles', async () => {
    for (const diagnostic of forceRecordingDiagnostics) {
      expect(forceRecordingSource).toContain(diagnostic.guardedSource)
    }

    const outDir = await mkdtemp(join(tmpdir(), 'streamvault-force-recording-production-'))
    const result = spawnSync('npm', ['run', 'build-only', '--', '--outDir', outDir], {
      cwd: frontendRoot,
      encoding: 'utf8',
      env: { ...process.env, NODE_ENV: 'production', VITE_USE_MOCK_DATA: 'true' },
    })
    expect(result.status, result.stderr).toBe(0)

    const outputFiles = (await collectFiles(outDir)).filter(path => extname(path) === '.js')
    const output = (await Promise.all(outputFiles.map(path => readFile(path, 'utf8')))).join('\n')
    for (const diagnostic of forceRecordingDiagnostics) {
      expect(output).not.toContain(diagnostic.message)
    }
  }, 15_000)

  it('does not retain the unconsumed local notification wrapper', () => {
    expect(pwaSource).not.toContain('showNotification')
  })

  it('does not ship unreachable settings-panel helpers', () => {
    const source = settingsSources.join('\n')
    for (const symbol of [
      '_refreshImages',
      '_clearCache',
      '_formatImageUrl',
      '_getHealthBadgeClass',
      '_updateFilenameTemplate',
      '_previewFilename',
      '_toggleStreamerRecording',
      '_connectTwitch',
    ]) expect(source, symbol).not.toContain(symbol)
  })

  it('does not emit selectors for retired settings markup', () => {
    const source = settingsSources.join('\n')
    for (const selector of [
      '.notification-types',
      '.notification-type-card',
      '.pwa-status',
      '.status-card',
      '.install-instructions',
      '.pwa-features',
      '.token-setup-guide',
      '.quality-benefits',
      '.codec-selection',
      '.active-recordings-list',
      '.recording-item',
      '.streamer-table',
      '.proxy-configuration',
      '.modal-overlay',
      '.modal-card',
    ]) expect(source, selector).not.toContain(selector)
  })
})
