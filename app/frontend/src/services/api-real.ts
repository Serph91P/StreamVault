// API client for StreamVault - REAL BACKEND IMPLEMENTATION
// This file is imported by api.ts when NOT in mock mode

interface RequestConfig {
  headers?: Record<string, string>
  body?: any
  method?: string
  [key: string]: any
}

interface ApiClientOptions {
  headers?: Record<string, string>
}

class ApiClient {
  constructor() {
    // All API calls use relative paths (/api/...)
    // BASE_URL is configured via docker-compose environment variables
  }

  async request(endpoint: string, options: RequestConfig = {}): Promise<any> {
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
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('application/json')) {
        return await response.json()
      } else {
        return response
      }
    } catch (error) {
      console.error('API request failed:', error)
      throw error
    }
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
  // Start recording for a specific streamer
  startRecording: (streamerId: number) => 
    apiClient.post(`/api/recording/start/${streamerId}`),

  // Stop recording for a specific streamer
  stopRecording: (streamerId: number) => 
    apiClient.post(`/api/recording/stop/${streamerId}`),

  // Get all active recordings
  getActiveRecordings: () => 
    apiClient.get('/api/recording/active'),

  // Get recording settings
  getSettings: () => 
    apiClient.get('/api/recording/settings'),

  // Update recording settings
  updateSettings: (settings: any) => 
    apiClient.put('/api/recording/settings', settings),

  // Get streamer-specific recording settings
  getStreamerSettings: (streamerId: number) => 
    apiClient.get(`/api/recording/streamers/${streamerId}`),

  // Update streamer-specific recording settings
  updateStreamerSettings: (streamerId: number, settings: any) => 
    apiClient.put(`/api/recording/streamers/${streamerId}`, settings),

  // Force start recording (bypasses normal checks)
  forceStartRecording: (streamerId: number) => 
    apiClient.post(`/api/recording/force-start/${streamerId}`),

  // Force stop recording
  forceStopRecording: (recordingId: number) => 
    apiClient.post(`/api/recording/force-stop/${recordingId}`),

  // Get recording status for a specific recording
  getRecordingStatus: (recordingId: number) => 
    apiClient.get(`/api/recording/status/${recordingId}`),

  // Delete a recording
  deleteRecording: (recordingId: number) => 
    apiClient.delete(`/api/recording/${recordingId}`),

  // Get recording history
  getRecordingHistory: (params: Record<string, any> = {}) => 
    apiClient.get('/api/recording/history', params),

  // Check if streamer is live
  checkStreamerLiveStatus: (streamerId: number) => 
    apiClient.get(`/api/streamers/${streamerId}/live-status`),
}

// Streamers API endpoints  
export const streamersApi = {
  // Get all streamers
  getAll: () => 
    apiClient.get('/api/streamers'),

  // Get a specific streamer  
  get: (streamerId: number) => 
    apiClient.get(`/api/streamers/streamer/${streamerId}`),

  // Add a new streamer by username
  add: (username: string) => 
    apiClient.post(`/api/streamers/${username}`),

  // Delete a streamer
  delete: (streamerId: number, deleteRecordings: boolean = false) => 
    apiClient.delete(`/api/streamers/${streamerId}?delete_recordings=${deleteRecordings}`),

  // Validate streamer username
  validate: (username: string) => 
    apiClient.get(`/api/streamers/validate/${username}`),

  // Get streamer's streams
  getStreams: (streamerId: number, params: Record<string, any> = {}) => 
    apiClient.get(`/api/streamers/${streamerId}/streams`, params),

  // Delete all streams for a streamer (skips currently recording by default)
  deleteAllStreams: (streamerId: number, opts: { excludeActive?: boolean } = {}) => 
    apiClient.delete(`/api/streamers/${streamerId}/streams${opts.excludeActive !== false ? '?exclude_active=true' : ''}`),

  // Delete specific stream for a streamer
  deleteStream: (streamerId: number, streamId: number) => 
    apiClient.delete(`/api/streamers/${streamerId}/streams/${streamId}`),

  // Get stream chapters for a streamer
  getStreamChapters: (streamerId: number, streamId: number) => 
    apiClient.get(`/api/streamers/${streamerId}/streams/${streamId}/chapters`),

  // Check if streamer is live
  checkLiveStatus: (streamerId: number) => 
    apiClient.get(`/api/streamers/${streamerId}/live-status`),

  // Get debug live status for all streamers
  getDebugLiveStatus: () => 
    apiClient.get('/api/streamers/debug-live-status'),

  // Subscription management
  getSubscriptions: () => 
    apiClient.get('/api/streamers/subscriptions'),

  deleteSubscriptions: () => 
    apiClient.delete('/api/streamers/subscriptions'),

  deleteSubscription: (subscriptionId: string) => 
    apiClient.delete(`/api/streamers/subscriptions/${subscriptionId}`),

  resubscribeAll: () => 
    apiClient.post('/api/streamers/resubscribe-all'),
}

// Alternative export name for backwards compatibility
export const streamerApi = streamersApi

// Streams API endpoints
export const streamsApi = {
  // Delete a stream
  delete: (streamId: number) => 
    apiClient.delete(`/api/streams/${streamId}`),

  // Check recordings for streams (batch operation)
  checkRecordings: (streamIds: number[]) => 
    apiClient.post('/api/streams/check-recordings', { stream_ids: streamIds }),
}

// System API endpoints
export const systemApi = {
  // Get system status
  getStatus: () => 
    apiClient.get('/api/status/system'),

  // Get health status
  getHealth: () => 
    apiClient.get('/api/status/health'),

  // Get all streamers status
  getStreamersStatus: () => 
    apiClient.get('/api/status/streamers'),

  // Get all streams status
  getStreamsStatus: () => 
    apiClient.get('/api/status/streams'),

  // Get active recordings status
  getActiveRecordingsStatus: () => 
    apiClient.get('/api/status/active-recordings'),

  // Get background queue status
  getBackgroundQueueStatus: () => 
    apiClient.get('/api/status/background-queue'),

  // Get notifications status
  getNotificationsStatus: () => 
    apiClient.get('/api/status/notifications'),
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

  // Get streamers (for settings)
  getStreamers: () => 
    apiClient.get('/api/settings/streamers'),

  // Test notification
  testNotification: (data: any) => 
    apiClient.post('/api/settings/test-notification', data),

  // Test WebSocket notification
  testWebSocketNotification: (data: any) => 
    apiClient.post('/api/settings/test-websocket-notification', data),
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

  // Get specific task
  getTask: (taskId: string) => 
    apiClient.get(`/api/background-queue/tasks/${taskId}`),

  // Enqueue generic task
  enqueueTask: (taskData: any) => 
    apiClient.post('/api/background-queue/tasks/enqueue', taskData),

  // Enqueue metadata generation task
  enqueueMetadataGeneration: (streamId: number) => 
    apiClient.post('/api/background-queue/tasks/metadata-generation', { stream_id: streamId }),

  // Enqueue thumbnail generation task
  enqueueThumbnailGeneration: (streamId: number) => 
    apiClient.post('/api/background-queue/tasks/thumbnail-generation', { stream_id: streamId }),

  // Enqueue file cleanup task
  enqueueFileCleanup: (streamerId: number) => 
    apiClient.post('/api/background-queue/tasks/file-cleanup', { streamer_id: streamerId }),

  // Get queue health
  getHealth: () => 
    apiClient.get('/api/background-queue/health'),
}

// Authentication API endpoints
export const authApi = {
  // Get Twitch auth URL
  getAuthUrl: () => 
    apiClient.get('/api/twitch/auth-url'),

  // Handle auth callback
  handleCallback: (code: string, state: string) => 
    apiClient.get(`/api/twitch/callback?code=${code}&state=${state}`),

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

// Images API endpoints
export const imagesApi = {
  // Streamer profile images
  getStreamerImage: (streamerId: number) => 
    apiClient.get(`/api/images/streamer/${streamerId}`),

  downloadStreamerImage: (streamerId: number) => 
    apiClient.post(`/api/images/streamer/${streamerId}/download`),

  // Category images
  getCategoryImage: (categoryName: string) => 
    apiClient.get(`/api/images/category/${categoryName}`),

  downloadCategoryImage: (categoryName: string) => 
    apiClient.post(`/api/images/category/${categoryName}/download`),

  // Image management
  getStats: () => 
    apiClient.get('/api/images/stats'),

  syncImages: () => 
    apiClient.post('/api/images/sync'),

  cleanupImages: () => 
    apiClient.post('/api/images/cleanup'),

  checkMissingImages: () => 
    apiClient.post('/api/images/sync/check-missing'),

  getSyncQueueStatus: () => 
    apiClient.get('/api/images/sync/queue-status'),

  // Get available streamers/categories for images
  getStreamers: () => 
    apiClient.get('/api/images/streamers'),

  getCategories: () => 
    apiClient.get('/api/images/categories'),
}

// Category browser + image cache endpoints
export const categoriesApi = {
  // Full category listing with favorite metadata
  getAll: () =>
    apiClient.get('/api/categories'),

  // Favorite categories for current user
  getFavorites: () =>
    apiClient.get('/api/categories/favorites'),

  // Mark a category as favorite
  addFavorite: (categoryId: number) =>
    apiClient.post('/api/categories/favorites', { category_id: categoryId }),

  // Remove from favorites
  removeFavorite: (categoryId: number) =>
    apiClient.delete(`/api/categories/favorites/${categoryId}`),

  // Immediate category image fetch (downloads if missing)
  getImage: (categoryName: string) =>
    apiClient.get(`/api/categories/image/${categoryName}`),

  // Batch image fetch helper
  getImagesBatch: (categoryNames: string[]) =>
    apiClient.post('/api/categories/images/batch', categoryNames),

  // Kick off background preload of category art
  preloadImages: (categoryNames: string[]) =>
    apiClient.post('/api/categories/preload-images', categoryNames),

  // Force refresh/download for list of categories
  refreshImages: (categoryNames: string[]) =>
    apiClient.post('/api/categories/refresh-images', categoryNames),

  // Clean cached artwork older than threshold
  cleanupImages: (daysOld: number = 30) =>
    apiClient.post(`/api/categories/cleanup-images?days_old=${daysOld}`),

  // Cache metadata (counts, storage path, etc.)
  getCacheStatus: () =>
    apiClient.get('/api/categories/cache-status'),

  // Missing image report for debugging
  getMissingImages: () =>
    apiClient.get('/api/categories/missing-images')
}

// Filename presets exposed via recording routes
export const filenamePresetsApi = {
  getAll: () =>
    apiClient.get('/api/recording/filename-presets')
}

// Video API endpoints
export const videoApi = {
  // Get all videos
  getAll: (params: Record<string, any> = {}) => 
    apiClient.get('/api/videos', params),

  // Get videos for specific streamer by ID
  getByStreamerId: (streamerId: number) => 
    apiClient.get(`/api/videos/streamer/${streamerId}`),

  // Get videos for specific streamer by name
  getByStreamerName: (streamerName: string) => 
    apiClient.get(`/api/videos/${streamerName}`),

  // Get specific video by streamer name and filename
  getByStreamerAndFilename: (streamerName: string, filename: string) => 
    apiClient.get(`/api/videos/${streamerName}/${filename}`),

  // Get video by filename
  getByFilename: (filename: string) => 
    apiClient.get(`/api/videos/stream_by_filename/${filename}`),

  // Get video stream URL (returns string for direct use in video src attribute)
  getVideoStreamUrl: (streamId: number): string => 
    `/api/videos/${streamId}/stream`,

  // Stream video
  streamVideo: (streamId: number) => 
    apiClient.get(`/api/videos/${streamId}/stream`),

  // Get video chapters
  getChapters: (streamId: number) => 
    apiClient.get(`/api/videos/${streamId}/chapters`),

  // Get video thumbnail
  getThumbnail: (streamId: number) => 
    apiClient.get(`/api/videos/${streamId}/thumbnail`),

  // Get public video (shared)
  getPublicVideo: (streamId: number) => 
    apiClient.get(`/api/videos/public/${streamId}`),

  // Create share token for video
  createShareToken: (streamId: number, data: any) => 
    apiClient.post(`/api/videos/${streamId}/share-token`, data),

  // Debug endpoints
  getDebugInfo: (streamId: number) => 
    apiClient.get(`/api/videos/debug/${streamId}`),

  getTestVideo: (streamId: number) => 
    apiClient.get(`/api/videos/test/${streamId}`),

  getDebugDatabase: () => 
    apiClient.get('/api/debug/videos-database'),

  getDebugRecordingsDirectory: () => 
    apiClient.get('/api/debug/recordings-directory'),
}

// Export the main API client as default
export default apiClient


