// API client for StreamVault - REAL BACKEND IMPLEMENTATION
// This file is imported by api.ts when NOT in mock mode

import router from '@/router'
import { appStorage } from '@/services/storage'
import type {
  BestProxyResponse,
  ProxyAddRequest,
  ProxyAddResponse,
  ProxyConfigSettings,
  ProxyConfigUpdateResponse,
  ProxyHealthCheckResponse,
  ProxyListResponse,
  ProxySuccessResponse,
  ProxyToggleResponse
} from '@/types/proxy'
import type { ApiKey, ApiKeyCreated } from '@/types/api-keys'

// Shared boundaries prevent concurrent safe requests from refreshing or logging out twice.
let refreshPromise: Promise<boolean> | null = null
let authLossError: ApiRequestError | null = null

interface RequestConfig extends RequestInit {
  headers?: Record<string, string>
  body?: any
}

export type ApiRequestErrorCode = 'auth_lost' | 'http_error'

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly code: ApiRequestErrorCode,
    readonly status?: number,
    readonly detail?: unknown
  ) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

export function isApiRequestError(error: unknown): error is ApiRequestError {
  return error instanceof ApiRequestError
}

const REFRESH_ENDPOINT = '/auth/refresh'
const RETRYABLE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

function isRefreshEndpoint(endpoint: string): boolean {
  return new URL(endpoint, 'http://streamvault.local').pathname === REFRESH_ENDPOINT
}

export class ApiClient {
  constructor() {
    // All API calls use relative paths (/api/...)
    // BASE_URL is configured via docker-compose environment variables
  }

  async request<T = any>(
    endpoint: string,
    options: RequestConfig = {},
    allowRefresh = true
  ): Promise<T> {
    const url = endpoint // Use endpoint directly (relative path)

    const config: RequestConfig = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    }

    // Ensure cookies (session) are always sent with API requests (fix für fehlende Persistenz)
    if (!('credentials' in config)) {
      ;(config as any).credentials = 'include'
    }

    if (config.body && typeof config.body === 'object') {
      config.body = JSON.stringify(config.body)
    }

    try {
      const response = await fetch(url, config)

      if (!response.ok) {
        if (response.status === 401) {
          const method = config.method?.toUpperCase() ?? 'GET'
          const canRefresh = allowRefresh
            && !isRefreshEndpoint(endpoint)
            && RETRYABLE_METHODS.has(method)

          if (canRefresh) {
            if (await this.refreshSession()) {
              return this.request<T>(endpoint, config, false)
            }
          }

          throw this.handleAuthLoss()
        }
        const contentType = response.headers.get('content-type')
        const errorBody = contentType?.includes('application/json')
          ? await response.json()
          : null
        const detail = errorBody?.detail
        throw new ApiRequestError(
          typeof detail === 'string'
            ? detail
            : typeof detail?.reason === 'string'
              ? detail.reason
              : `HTTP error! status: ${response.status}`,
          'http_error',
          response.status,
          detail
        )
      }

      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('application/json')) {
        return await response.json() as T
      } else {
        return response as T
      }
    } catch (error) {
      console.error('API request failed:', error)
      throw error
    }
  }

  private refreshSession(): Promise<boolean> {
    if (!refreshPromise) {
      refreshPromise = fetch(REFRESH_ENDPOINT, {
        method: 'POST',
        credentials: 'include'
      })
        .then(response => response.ok)
        .catch(() => false)
        .finally(() => {
          refreshPromise = null
        })
    }

    return refreshPromise
  }

  private handleAuthLoss(): ApiRequestError {
    if (authLossError) {
      return authLossError
    }

    console.warn('Session expired or invalid, redirecting to login...')
    appStorage.clearSessionToken()
    appStorage.clearSessionStorage()
    authLossError = new ApiRequestError('Session expired - redirecting to login', 'auth_lost', 401)
    router.push('/auth/login').finally(() => {
      authLossError = null
    })
    return authLossError
  }

  async get(endpoint: string, params: Record<string, any> = {}): Promise<any> {
    const searchParams = new URLSearchParams(params)
    const url = searchParams.toString() ? `${endpoint}?${searchParams}` : endpoint

    return this.request(url, {
      method: 'GET',
    })
  }

  async post(endpoint: string, data: any = {}): Promise<any> {
    return this.request(endpoint, {
      method: 'POST',
      body: data,
    })
  }

  async put(endpoint: string, data: any = {}): Promise<any> {
    return this.request(endpoint, {
      method: 'PUT',
      body: data,
    })
  }

  async delete(endpoint: string): Promise<any> {
    return this.request(endpoint, {
      method: 'DELETE',
    })
  }

  async patch(endpoint: string, data: any = {}): Promise<any> {
    return this.request(endpoint, {
      method: 'PATCH',
      body: data,
    })
  }
}

// Create and export a singleton instance
const apiClient = new ApiClient()

// Recording API endpoints
export const recordingApi = {
  // Stop recording for a specific streamer
  stopRecording: (streamerId: number) => 
    apiClient.post(`/api/recording/stop/${streamerId}`),

  // Get all active recordings
  getActiveRecordings: () => 
    apiClient.get('/api/recording/active'),


  // Force start recording (bypasses normal checks)
  forceStartRecording: (streamerId: number) => 
    apiClient.post(`/api/recording/force-start/${streamerId}`),

}

// Streamers API endpoints  
export const streamersApi = {
  // Get all streamers
  getAll: () => 
    apiClient.get('/api/streamers'),

  // Get a specific streamer  
  get: (streamerId: number) => 
    apiClient.get(`/api/streamers/streamer/${streamerId}`),


  // Delete a streamer
  delete: async (streamerId: string | number, deleteRecordings?: boolean): Promise<void> => {
    await apiClient.delete(
      `/api/streamers/${streamerId}${deleteRecordings === undefined ? '' : `?delete_recordings=${deleteRecordings}`}`
    )
  },


  // Get streamer's streams
  getStreams: (streamerId: number, params: Record<string, any> = {}) => 
    apiClient.get(`/api/streamers/${streamerId}/streams`, params),

  // Delete all streams for a streamer (skips currently recording by default)
  deleteAllStreams: (streamerId: number, opts: { excludeActive?: boolean } = {}) => 
    apiClient.delete(`/api/streamers/${streamerId}/streams${opts.excludeActive !== false ? '?exclude_active=true' : ''}`),


  // Get stream chapters for a streamer
  getStreamChapters: (streamerId: number, streamId: number) => 
    apiClient.get(`/api/streamers/${streamerId}/streams/${streamId}/chapters`),

  // Check if streamer is live
  checkLiveStatus: (streamerId: number) => 
    apiClient.get(`/api/streamers/${streamerId}/live-status`),

}

// Streams API endpoints
export const streamsApi = {
  // Delete a stream
  delete: (streamId: number) => 
    apiClient.delete(`/api/streams/${streamId}`),
}

// System API endpoints
export const systemApi = {
  // Get system status
  getStatus: (params: Record<string, any> = {}) =>
    apiClient.get('/api/status/system', params),

  // Get frontend/backend version information
  getVersion: () =>
    apiClient.get('/api/version'),


  // Get all streamers status
  getStreamersStatus: (params: Record<string, any> = {}) =>
    apiClient.get('/api/status/streamers', params),

  // Get all streams status
  getStreamsStatus: (params: Record<string, any> = {}) =>
    apiClient.get('/api/status/streams', params),

  // Get active recordings status
  getActiveRecordingsStatus: (params: Record<string, any> = {}) =>
    apiClient.get('/api/status/active-recordings', params),


  // Get notifications status
  getNotificationsStatus: (params: Record<string, any> = {}) =>
    apiClient.get('/api/status/notifications', params),
}

// Notification API endpoints
export const notificationApi = {
  // Get notification state (last read/cleared timestamps)
  getState: () => 
    apiClient.get('/api/notifications/state'),
  
  // Mark notifications as read
  markRead: (timestamp?: string) =>
    apiClient.post('/api/notifications/mark-read', { timestamp }),
  
  // Clear all notifications
  clear: () =>
    apiClient.post('/api/notifications/clear', {})
}

// Streamer subscription management (EventSub)
export const subscriptionsApi = {
  // List current EventSub subscriptions
  getAll: () =>
    apiClient.get('/api/streamers/subscriptions'),

  // Delete all subscriptions
  deleteAll: () =>
    apiClient.delete('/api/streamers/subscriptions'),

  // Delete a specific subscription by ID
  delete: (subscriptionId: string) =>
    apiClient.delete(`/api/streamers/subscriptions/${subscriptionId}`),

  // Ask backend to resubscribe all streamers
  resubscribeAll: () =>
    apiClient.post('/api/streamers/resubscribe-all')
}

// Settings API endpoints
export const settingsApi = {
  // Get global settings
  getGlobalSettings: () => 
    apiClient.get('/api/settings'),

  // Update global settings
  updateGlobalSettings: (settings: any) => 
    apiClient.post('/api/settings', settings),

  // Get streamer notification settings
  getStreamerSettings: () => 
    apiClient.get('/api/settings/streamer'),

  // Update streamer notification settings
  updateStreamerSettings: (streamerId: number, settings: any) => 
    apiClient.post(`/api/settings/streamer/${streamerId}`, settings),

}

export const apiKeysApi = {
  getAll: (): Promise<ApiKey[]> => apiClient.get('/api/api-keys'),
  create: (name: string): Promise<ApiKeyCreated> => apiClient.post('/api/api-keys', { name }),
  revoke: (id: number) => apiClient.delete(`/api/api-keys/${id}`)
}

// Background Queue API endpoints
export const backgroundQueueApi = {
  // Get queue statistics
  getStats: () => 
    apiClient.get('/api/background-queue/stats'),

  // Get active tasks
  getActiveTasks: () => 
    apiClient.get('/api/background-queue/active-tasks'),

  // Get recent tasks
  getRecentTasks: () => 
    apiClient.get('/api/background-queue/recent-tasks'),



  cancelStreamTasks: (streamId: number) =>
    apiClient.post(`/api/background-queue/cancel-stream/${streamId}`),
}

// Authentication API endpoints
export const authApi = {
  // Get Twitch auth URL
  getAuthUrl: () => 
    apiClient.get('/api/twitch/auth-url'),


  // Get followed channels
  getFollowedChannels: () => 
    apiClient.get('/api/twitch/followed-channels'),

  // Import streamers from followed channels
  importStreamers: (streamerIds: number[]) => 
    apiClient.post('/api/twitch/import-streamers', { streamer_ids: streamerIds }),

  // Get callback URL
  getCallbackUrl: () => 
    apiClient.get('/api/twitch/callback-url'),  // FIXED: Changed from /api/auth to /api/twitch
}


// Category browser + image cache endpoints
export const categoriesApi = {
  // Immediate category image fetch (downloads if missing)
  getImage: (categoryName: string) =>
    apiClient.get(`/api/categories/image/${encodeURIComponent(categoryName)}`),


  // Kick off background preload of category art
  preloadImages: (categoryNames: string[]) =>
    apiClient.post('/api/categories/preload-images', categoryNames),

}

// Filename presets exposed via recording routes
export const filenamePresetsApi = {
  getAll: () =>
    apiClient.get('/api/recording/filename-presets')
}

function proxyConfigQuery(config: Partial<ProxyConfigSettings>): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(config)) {
    if (value !== undefined) params.set(key, String(value))
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

// Payload-free POST actions use request() directly so no empty JSON body is sent.
export const proxyApi = {
  getAll: (): Promise<ProxyListResponse> =>
    apiClient.get('/api/proxy/list'),
  add: (request: ProxyAddRequest): Promise<ProxyAddResponse> =>
    apiClient.post('/api/proxy/add', request),
  delete: (proxyId: number): Promise<ProxySuccessResponse> =>
    apiClient.delete(`/api/proxy/${proxyId}`),
  toggle: (proxyId: number): Promise<ProxyToggleResponse> =>
    apiClient.request(`/api/proxy/${proxyId}/toggle`, { method: 'POST' }),
  test: (proxyId: number): Promise<ProxyHealthCheckResponse> =>
    apiClient.request(`/api/proxy/${proxyId}/test`, { method: 'POST' }),
  updatePriority: (proxyId: number, priority: number): Promise<ProxySuccessResponse> =>
    apiClient.post(`/api/proxy/${proxyId}/update-priority`, { priority }),
  updateConfig: (config: Partial<ProxyConfigSettings>): Promise<ProxyConfigUpdateResponse> =>
    apiClient.request(`/api/proxy/config/update${proxyConfigQuery(config)}`, { method: 'POST' }),
  getBest: (): Promise<BestProxyResponse> =>
    apiClient.get('/api/proxy/best')
}

// Live Streaming API endpoints
export const liveApi = {
  // Start a live stream for a streamer
  startLiveStream: (
    streamerName: string,
    quality: string = 'best',
    supportedCodecs: string = 'h264',
    enhancedQuality: boolean = false
  ) => apiClient.post(`/api/live/start/${streamerName}`, {
    quality,
    supported_codecs: supportedCodecs,
    enhanced_quality: enhancedQuality
  }),

  // Stop a live stream session
  stopLiveStream: (sessionId: string) =>
    apiClient.delete(`/api/live/stop/${sessionId}`),


  // Get HLS playlist URL
  getPlaylistUrl: (sessionId: string): string =>
    `/api/live/stream/${sessionId}/playlist.m3u8`,
}

// Video API endpoints
export const videoApi = {
  // Get all videos
  getAll: (params: Record<string, any> = {}) => 
    apiClient.get('/api/videos', params),


  // Get video stream URL (returns string for direct use in video src attribute)
  getVideoStreamUrl: (streamId: number): string => 
    `/api/videos/${streamId}/stream`,


  // Get video chapters
  getChapters: (streamId: number) => 
    apiClient.get(`/api/videos/${streamId}/chapters`),


  // Delete videos. VideosView receives stream IDs from /api/videos, and the
  // backend deletion implementation lives under /api/streams/{stream_id}.
  delete: (streamId: number) =>
    apiClient.delete(`/api/streams/${streamId}`),

  deleteMultiple: (streamIds: number[]) =>
    Promise.all(streamIds.map(streamId => apiClient.delete(`/api/streams/${streamId}`))),


  // Create share token for video
  createShareToken: (streamId: number, data: any) => 
    apiClient.post(`/api/videos/${streamId}/share-token`, data),

}

// Export the main API client as default
export default apiClient

