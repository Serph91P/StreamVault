/**
 * API Wrapper - Conditional Mock/Real API
 * 
 * This file exports either mock or real API based on VITE_USE_MOCK_DATA
 * Import from this file instead of api.ts directly
 */

import {
  mockStreamers,
  mockVideos,
  mockActiveRecordings,
  mockQueueStats,
  mockActiveTasks,
  mockProxies
} from '../mocks/mockData'
import type {
  BestProxyResponse,
  ProxyAddRequest,
  ProxyAddResponse,
  ProxyConfigSettings,
  ProxyConfigUpdateResponse,
  ProxyHealthCheckResponse,
  ProxyListResponse,
  ProxySettings,
  ProxySuccessResponse,
  ProxyToggleResponse
} from '@/types/proxy'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'
import type { ApiKey, ApiKeyCreated } from '@/types/api-keys'

// Check if mock mode is enabled
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true'

// Simulate network delay for mock responses
const mockDelay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))
const mockResponse = async <T>(data: T): Promise<T> => {
  await mockDelay(200)  // Faster delay for better UX
  return data
}

// ============================================================================
// MOCK API IMPLEMENTATIONS
// ============================================================================

const mockStreamersApi = {
  getAll: () => mockResponse({ streamers: mockStreamers }),
  get: (id: number) => mockResponse(mockStreamers.find(s => s.id === id) || null),
  delete: async (_id: string | number, _deleteRecordings?: boolean): Promise<void> => {
    await mockResponse(undefined)
  },
  getStreams: (streamerId: number) => {
    const streamerVideos = mockVideos.filter(video => video.streamer_id === streamerId)
    // Map mock videos to stream format expected by StreamCard
    const streams = streamerVideos.map(video => {
      const startDate = new Date(video.recorded_at)
      const endDate = new Date(startDate.getTime() + (video.duration || 3600) * 1000)
      return {
        id: video.id,
        streamer_id: video.streamer_id,
        title: video.title,
        category_name: video.category_name,
        started_at: startDate.toISOString(),
        ended_at: endDate.toISOString(),
        recording_path: video.file_path,
        is_recording: false,
        is_live: false,
      }
    })
    return mockResponse({ streams })
  },
  deleteAllStreams: (streamerId: number) => mockResponse({ success: true, streamerId }),
  getStreamChapters: (_streamerId: number, _streamId: number) => mockResponse({ chapters: [] }),
  checkLiveStatus: (streamerId: number) => mockResponse({ streamer_id: streamerId, is_live: false }),
}

const mockVideoApi = {
  getAll: (_params: Record<string, any> = {}) => mockResponse(mockVideos),
  delete: (_id: number) => mockResponse({ success: true }),
  deleteMultiple: (ids: number[]) => mockResponse({ success: true, count: ids.length }),
  getVideoStreamUrl: (id: number): string => `/api/videos/${id}/stream`,
  getChapters: (_id: number) => mockResponse([
    { id: 1, title: 'Stream Start', start: 0, end: 600 }
  ]),
  createShareToken: (id: number, _data: Record<string, never> = {}) => mockResponse({
    success: true,
    share_url: `/api/videos/public/${id}?token=mock-share-token`,
    expires_in: '24 hours'
  })
}

const mockRecordingApi = {
  getActiveRecordings: () => mockResponse(mockActiveRecordings),
  stopRecording: (_streamerId: number) => mockResponse(undefined),
  forceStartRecording: (streamerId: number) => mockResponse({ success: true, streamerId }),
}

const mockBackgroundQueueApi = {
  getStats: () => mockResponse(mockQueueStats),
  getActiveTasks: () => mockResponse(mockActiveTasks),
  getRecentTasks: () => mockResponse([]),
  cancelStreamTasks: (_streamId: number) => mockResponse(undefined)
}

let mockGlobalSettings: NotificationSettings = {
  notification_url: '',
  notifications_enabled: true,
  apprise_docs_url: '',
  notify_online_global: true,
  notify_offline_global: true,
  notify_update_global: true
}
const mockStreamerSettings: StreamerNotificationSettings[] = []
const mockSettingsApi = {
  getGlobalSettings: () => mockResponse({ ...mockGlobalSettings }),
  updateGlobalSettings: (settings: Partial<NotificationSettings>) => {
    mockGlobalSettings = { ...mockGlobalSettings, ...settings }
    return mockResponse({ ...mockGlobalSettings })
  },
  getStreamerSettings: () => mockResponse([...mockStreamerSettings]),
  updateStreamerSettings: (streamerId: number, settings: Partial<StreamerNotificationSettings>) =>
    mockResponse({ streamer_id: streamerId, notify_online: true, notify_offline: true, notify_update: true, ...settings })
}

let mockApiKeys: ApiKey[] = []
const mockApiKeysApi = {
  getAll: () => mockResponse([...mockApiKeys]),
  create: (name: string): Promise<ApiKeyCreated> => {
    const key = { id: Date.now(), name, prefix: 'sv_mock', key: 'mock-key', created_at: new Date().toISOString(), last_used_at: null }
    mockApiKeys.push(key)
    return mockResponse(key)
  },
  revoke: (id: number) => {
    mockApiKeys = mockApiKeys.filter(key => key.id !== id)
    return mockResponse(undefined)
  }
}

const mockNotificationApi = {
  getState: () => mockResponse({ last_read: null, last_cleared: null }),
  markRead: (_timestamp?: string) => mockResponse({ success: true }),
  clear: () => mockResponse({ success: true })
}

let mockProxyConfig: ProxyConfigSettings = {
  enable_proxy: true,
  proxy_health_check_enabled: true,
  proxy_health_check_interval_seconds: 300,
  proxy_max_consecutive_failures: 3,
  fallback_to_direct_connection: true
}

const maskProxyUrl = (proxyUrl: string): string => {
  try {
    const parsed = new URL(proxyUrl)
    // URL.port drops explicit default ports (for example http://host:80), while
    // the backend's urllib serializer preserves every explicitly supplied port.
    const authority = proxyUrl.match(/^[A-Za-z][A-Za-z\d+.-]*:\/\/([^/?#]*)/)?.[1]
    const credentialSeparator = authority?.lastIndexOf('@') ?? -1
    const hostAndPort = authority?.slice(credentialSeparator + 1)
    const explicitPort = hostAndPort?.match(/:(\d+)$/)?.[1]
    const port = explicitPort === undefined ? '' : String(Number(explicitPort))
    return port ? `${parsed.hostname}:${port}` : parsed.hostname
  } catch {
    return '[REDACTED_PROXY_URL]'
  }
}

let mockProxyState: ProxySettings[] = mockProxies.map(proxy => {
  const maskedUrl = maskProxyUrl(proxy.proxy_url)
  return {
    ...proxy,
    proxy_url: maskedUrl,
    masked_url: maskedUrl
  }
})

const mockProxyApi = {
  getAll: (): Promise<ProxyListResponse> => mockResponse({
    proxies: mockProxyState.map(proxy => ({ ...proxy })),
    system_config: { ...mockProxyConfig }
  }),
  add: (request: ProxyAddRequest): Promise<ProxyAddResponse> => {
    const proxyId = Math.max(0, ...mockProxyState.map(proxy => proxy.id)) + 1
    const maskedUrl = maskProxyUrl(request.proxy_url)
    mockProxyState.push({
      id: proxyId,
      proxy_url: maskedUrl,
      masked_url: maskedUrl,
      priority: request.priority ?? 0,
      enabled: true,
      health_status: 'unknown',
      last_check: null,
      response_time_ms: null,
      consecutive_failures: 0,
      last_error: null,
      total_requests: 0,
      successful_requests: 0,
      failed_requests: 0,
      created_at: new Date().toISOString()
    })
    return mockResponse({
      success: true,
      proxy_id: proxyId,
      message: 'Proxy added successfully. Health check in progress.'
    })
  },
  delete: (proxyId: number): Promise<ProxySuccessResponse> => {
    mockProxyState = mockProxyState.filter(proxy => proxy.id !== proxyId)
    return mockResponse({ success: true, message: `Proxy ${proxyId} deleted successfully` })
  },
  toggle: (proxyId: number): Promise<ProxyToggleResponse> => {
    const proxy = mockProxyState.find(candidate => candidate.id === proxyId)
    if (proxy) proxy.enabled = !proxy.enabled
    return mockResponse({
      success: true,
      enabled: proxy?.enabled ?? false,
      message: 'Proxy toggled successfully'
    })
  },
  test: (proxyId: number): Promise<ProxyHealthCheckResponse> => mockResponse({
    success: true,
    result: {
      proxy_id: proxyId,
      health_status: 'healthy',
      response_time_ms: 123,
      consecutive_failures: 0,
      enabled: mockProxyState.find(candidate => candidate.id === proxyId)?.enabled ?? false,
      error: null
    }
  }),
  updatePriority: (proxyId: number, priority: number): Promise<ProxySuccessResponse> => {
    const proxy = mockProxyState.find(candidate => candidate.id === proxyId)
    if (proxy) proxy.priority = priority
    return mockResponse({ success: true, message: `Proxy priority updated to ${priority}` })
  },
  updateConfig: (config: Partial<ProxyConfigSettings>): Promise<ProxyConfigUpdateResponse> => {
    mockProxyConfig = { ...mockProxyConfig, ...config }
    return mockResponse({
      success: true,
      message: 'Proxy configuration updated successfully',
      config: { ...mockProxyConfig }
    })
  },
  getBest: (): Promise<BestProxyResponse> => mockResponse({
    proxy: mockProxyState.find(proxy => proxy.enabled && proxy.health_status === 'healthy') ?? null,
    message: 'Best available proxy'
  })
}

const mockSystemApi = {
  getStatus: (_params: Record<string, any> = {}) => mockResponse({
    status: 'ok', 
    version: '1.0.0',
    uptime: 123456,
    recordings_active: 1,
    storage_used: 1024 * 1024 * 5000 // 5GB
  }),
  getVersion: () => mockResponse({ version: '1.0.0', build: 'mock' }),
  getStreamersStatus: (_params: Record<string, any> = {}) => mockResponse({ live: 2, offline: 2, total: 4 }),
  getStreamsStatus: (_params: Record<string, any> = {}) => mockResponse({ live: 2, total: 4 }),
  getActiveRecordingsStatus: (_params: Record<string, any> = {}) => mockResponse({ active: 1, total: 1 }),
  getNotificationsStatus: (_params: Record<string, any> = {}) => mockResponse({ unread: 0, total: 0 })
}

const mockStreamsApi = {
  delete: (_streamId: number) => mockResponse(undefined),
}

const mockAuthApi = {
  getAuthUrl: () => mockResponse({ url: 'https://twitch.tv/oauth/mock' }),
  getFollowedChannels: () => mockResponse([
    { user_id: '123', user_login: 'mock1', user_name: 'Mock Channel 1' },
    { user_id: '456', user_login: 'mock2', user_name: 'Mock Channel 2' }
  ]),
  importStreamers: (_streamerIds: number[]) => mockResponse({ imported: 0, total: 0 }),
  getCallbackUrl: () => mockResponse({ callback_url: 'http://localhost:8000/auth/callback' }),
}


const mockSubscriptionsApi = {
  getAll: () => mockResponse({ total: 0, subscriptions: [] }),
  deleteAll: () => mockResponse({
    success: true,
    deleted_subscriptions: [],
    total_deleted: 0,
    total_failed: 0
  }),
  delete: (subscriptionId: string) => mockResponse({
    success: true,
    message: `Subscription ${subscriptionId} deleted`
  }),
  resubscribeAll: () => mockResponse({
    success: true,
    message: 'All subscriptions resubscribed',
    results: [],
    total_processed: 0
  })
}

const mockCategoriesApi = {
  getImage: (categoryName: string) => mockResponse({ category_name: categoryName, image_url: null }),
  preloadImages: (_names: string[]) => mockResponse(undefined),
}

const mockFilenamePresetsApi = {
  getAll: () => mockResponse({ status: 'success', data: [] })
}

const mockLiveApi = {
  startLiveStream: (
    streamerName: string,
    quality: string = 'best',
    supportedCodecs: string = 'h264',
    _enhancedQuality: boolean = false
  ) => mockResponse({
    success: true,
    session_id: `mock-live-${Date.now()}`,
    streamer_name: streamerName,
    quality,
    supported_codecs: supportedCodecs,
    idempotent: false,
    playlist_url: '/api/live/stream/mock/playlist.m3u8',
    message: 'Stream started (mock)'
  }),
  stopLiveStream: (_sessionId: string) => mockResponse({
    success: true,
    message: 'Stream stopped (mock)'
  }),
  getPlaylistUrl: (sessionId: string): string => `/api/live/stream/${sessionId}/playlist.m3u8`
}

// ============================================================================
// REAL API IMPORTS
// ============================================================================

import * as realApi from './api-real'

export { ApiRequestError, isApiRequestError } from './api-real'
export type { ApiRequestErrorCode } from './api-real'

// ============================================================================
// CONDITIONAL EXPORTS
// ============================================================================

if (import.meta.env.DEV) {
  if (import.meta.env.DEV) console.debug(USE_MOCK_DATA ? '🎭 Using MOCK API for all endpoints' : '🌐 Using REAL API for all endpoints')
}

export const streamersApi = USE_MOCK_DATA ? mockStreamersApi : realApi.streamersApi
export const videoApi = USE_MOCK_DATA ? mockVideoApi : realApi.videoApi  
export const recordingApi = USE_MOCK_DATA ? mockRecordingApi : realApi.recordingApi
export const backgroundQueueApi = USE_MOCK_DATA ? mockBackgroundQueueApi : realApi.backgroundQueueApi
export const settingsApi = USE_MOCK_DATA ? mockSettingsApi : realApi.settingsApi
export const apiKeysApi = USE_MOCK_DATA ? mockApiKeysApi : realApi.apiKeysApi
export const notificationApi = USE_MOCK_DATA ? mockNotificationApi : realApi.notificationApi
export const systemApi = USE_MOCK_DATA ? mockSystemApi : realApi.systemApi
export const streamsApi = USE_MOCK_DATA ? mockStreamsApi : realApi.streamsApi
export const authApi = USE_MOCK_DATA ? mockAuthApi : realApi.authApi
export const subscriptionsApi = USE_MOCK_DATA ? mockSubscriptionsApi : realApi.subscriptionsApi
export const categoriesApi = USE_MOCK_DATA ? mockCategoriesApi : realApi.categoriesApi
export const filenamePresetsApi = USE_MOCK_DATA ? mockFilenamePresetsApi : realApi.filenamePresetsApi

export const proxyApi = USE_MOCK_DATA ? mockProxyApi : realApi.proxyApi
export const liveApi = USE_MOCK_DATA ? mockLiveApi : realApi.liveApi
