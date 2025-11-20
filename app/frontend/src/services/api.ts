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
  mockSettings,
  mockProxies
} from '../mocks/mockData'

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
  add: (username: string) => mockResponse({
    id: Date.now(),
    username,
    display_name: username,
    is_live: false,
    is_recording: false
  }),
  delete: (id: number, deleteRecordings = false) => mockResponse({ success: true, deleteRecordings }),
  validate: (username: string) => mockResponse({
    valid: true,
    user_id: '12345',
    display_name: username,
    profile_image_url: 'https://static-cdn.jtvnw.net/user-default-pictures-uv/cdd517fe-def4-11e9-948e-784f43822e80-profile_image-300x300.png'
  }),
  getStreams: (streamerId: number) => mockResponse({
    streams: mockVideos.filter(video => video.streamer_id === streamerId)
  }),
  deleteAllStreams: (streamerId: number) => mockResponse({ success: true, streamerId }),
  deleteStream: (streamerId: number, streamId: number) => mockResponse({ success: true, streamerId, streamId }),
  getStreamChapters: (streamerId: number, streamId: number) => mockResponse({ chapters: [] }),
  checkLiveStatus: (streamerId: number) => mockResponse({ streamer_id: streamerId, is_live: false }),
  getDebugLiveStatus: () => mockResponse({ live: 0, offline: mockStreamers.length }),
  getSubscriptions: () => mockResponse({ data: [] }),
  deleteSubscriptions: () => mockResponse({ success: true }),
  deleteSubscription: (subscriptionId: string) => mockResponse({ success: true, subscriptionId }),
  resubscribeAll: () => mockResponse({ success: true }),
  forceRecord: (id: number) => mockResponse({ success: true, message: 'Recording started' })
}

const mockVideoApi = {
  getAll: () => mockResponse(mockVideos),
  getById: (id: number) => mockResponse(mockVideos.find(v => v.id === id) || null),
  delete: (id: number) => mockResponse({ success: true }),
  deleteMultiple: (ids: number[]) => mockResponse({ success: true, count: ids.length }),
  getChapters: (id: number) => mockResponse([]),
  regenerateMetadata: (id: number) => mockResponse({ success: true })
}

const mockRecordingApi = {
  getActiveRecordings: () => mockResponse(mockActiveRecordings),
  stop: (streamerId: number) => mockResponse({ success: true }),
  startRecording: (streamerId: number) => mockResponse({ success: true }),
  stopRecording: (streamerId: number) => mockResponse({ success: true }),
  getSettings: () => mockResponse({}),
  updateSettings: (settings: any) => mockResponse({ success: true }),
  getStreamerSettings: (streamerId: number) => mockResponse({}),
  updateStreamerSettings: (streamerId: number, settings: any) => mockResponse({ success: true }),
  forceStartRecording: (streamerId: number) => mockResponse({ success: true, streamerId }),
  forceStopRecording: (recordingId: number) => mockResponse({ success: true, recordingId }),
  getRecordingStatus: (recordingId: number) => mockResponse({ recordingId, status: 'stopped' }),
  deleteRecording: (recordingId: number) => mockResponse({ success: true, recordingId }),
  getRecordingHistory: () => mockResponse([]),
  checkStreamerLiveStatus: (streamerId: number) => mockResponse({ streamer_id: streamerId, is_live: false })
}

const mockBackgroundQueueApi = {
  getStats: () => mockResponse(mockQueueStats),
  getActiveTasks: () => mockResponse(mockActiveTasks),
  getRecentTasks: () => mockResponse([]),
  getTask: (taskId: string) => mockResponse({ taskId, status: 'queued' }),
  enqueueTask: (taskData: any) => mockResponse({ success: true, task: taskData }),
  enqueueMetadataGeneration: (streamId: number) => mockResponse({ success: true, streamId }),
  enqueueThumbnailGeneration: (streamId: number) => mockResponse({ success: true, streamId }),
  enqueueFileCleanup: (streamerId: number) => mockResponse({ success: true, streamerId }),
  getHealth: () => mockResponse({ healthy: true })
}

const mockSettingsApi = {
  getAll: () => mockResponse(mockSettings),
  update: (data: any) => mockResponse({ ...mockSettings, ...data }),
  getRecordingSettings: () => mockResponse(mockSettings.recording || {}),
  updateRecordingSettings: (data: any) => mockResponse({ success: true }),
  getNotificationSettings: () => mockResponse(mockSettings.notifications || {}),
  updateNotificationSettings: (data: any) => mockResponse({ success: true })
}

const mockNotificationApi = {
  getState: () => mockResponse({ last_read: null, last_cleared: null }),
  markRead: (timestamp?: string) => mockResponse({ success: true }),
  clear: () => mockResponse({ success: true })
}

const mockProxyApi = {
  getAll: () => mockResponse(mockProxies),
  create: (data: any) => mockResponse({ ...data, id: Date.now() }),
  update: (id: number, data: any) => mockResponse({ ...data, id }),
  delete: (id: number) => mockResponse({ success: true }),
  test: (id: number) => mockResponse({ success: true, latency: 123 }),
  healthCheck: () => mockResponse({ healthy: 3, unhealthy: 0 })
}

const mockSystemApi = {
  getStatus: () => mockResponse({ 
    status: 'ok', 
    version: '1.0.0',
    uptime: 123456,
    recordings_active: 1,
    storage_used: 1024 * 1024 * 5000 // 5GB
  }),
  getVersion: () => mockResponse({ version: '1.0.0', build: 'mock' }),
  getStreamersStatus: () => mockResponse({ live: 2, offline: 2, total: 4 }),
  getStreamsStatus: () => mockResponse({ live: 2, total: 4 }),
  getActiveRecordingsStatus: () => mockResponse({ active: 1, total: 1 }),
  getBackgroundQueueStatus: () => mockResponse(mockQueueStats),
  getNotificationsStatus: () => mockResponse({ unread: 0, total: 0 })
}

const mockStreamsApi = {
  delete: (streamId: number) => mockResponse({ success: true, streamId }),
  checkRecordings: (streamIds: number[]) => mockResponse({ success: true, processed: streamIds.length })
}

const mockAuthApi = {
  getAuthUrl: () => mockResponse({ url: 'https://twitch.tv/oauth/mock' }),
  handleCallback: (code: string, state: string) => mockResponse({ success: true, code, state }),
  getFollowedChannels: () => mockResponse([
    { user_id: '123', user_login: 'mock1', user_name: 'Mock Channel 1' },
    { user_id: '456', user_login: 'mock2', user_name: 'Mock Channel 2' }
  ]),
  importStreamers: (streamerIds: number[]) => mockResponse({ imported: streamerIds.length, total: streamerIds.length }),
  login: (data: any) => mockResponse({ success: true, token: 'mock-token' }),
  logout: () => mockResponse({ success: true }),
  check: () => mockResponse({ authenticated: true }),
  setup: () => mockResponse({ setup_required: false }),
  getConnectionStatus: () => mockResponse({ 
    connected: false, 
    has_oauth_token: false,
    has_browser_token: true,
    token_source: 'browser'
  }),
  getCallbackUrl: () => mockResponse({ callback_url: 'http://localhost:8000/auth/callback' }),
  exchangeCode: (code: string) => mockResponse({ success: true }),
  disconnect: () => mockResponse({ success: true }),
  importFollowedChannels: () => mockResponse({ imported: 0, total: 0 })
}

const mockImagesApi = {
  getThumbnail: (videoId: number) => mockResponse(null),
  getStreamerAvatar: (streamerId: number) => mockResponse(null)
}

const mockSubscriptionsApi = {
  getAll: () => mockResponse({ data: [] }),
  deleteAll: () => mockResponse({ success: true }),
  delete: (subscriptionId: string) => mockResponse({ success: true, subscriptionId }),
  resubscribeAll: () => mockResponse({ success: true })
}

const mockCategoriesApi = {
  getAll: () => mockResponse([]),
  getFavorites: () => mockResponse([]),
  addFavorite: (categoryId: number) => mockResponse({ success: true, categoryId }),
  removeFavorite: (categoryId: number) => mockResponse({ success: true, categoryId }),
  getImage: (categoryName: string) => mockResponse({ category_name: categoryName, image_url: null }),
  getImagesBatch: (names: string[]) => mockResponse({
    category_images: names.reduce<Record<string, string | null>>((acc, name) => {
      acc[name] = null
      return acc
    }, {})
  }),
  preloadImages: (names: string[]) => mockResponse({ message: `Started preloading ${names.length} category images`, categories: names }),
  refreshImages: (names: string[]) => mockResponse({ message: `Started refreshing ${names.length} category images`, categories: names }),
  cleanupImages: (daysOld: number = 30) => mockResponse({ success: true, daysOld }),
  getCacheStatus: () => mockResponse({ cached_categories: 0, failed_downloads: 0 }),
  getMissingImages: () => mockResponse({ missing: [] })
}

const mockFilenamePresetsApi = {
  getAll: () => mockResponse([]),
  create: (data: any) => mockResponse({ ...data, id: Date.now() }),
  update: (id: number, data: any) => mockResponse({ success: true }),
  delete: (id: number) => mockResponse({ success: true })
}

// ============================================================================
// REAL API IMPORTS
// ============================================================================

import * as realApi from './api-real'

// ============================================================================
// CONDITIONAL EXPORTS
// ============================================================================

if (USE_MOCK_DATA) {
  console.log('🎭 Using MOCK API for all endpoints')
} else {
  console.log('🌐 Using REAL API for all endpoints')
}

export const streamersApi = USE_MOCK_DATA ? mockStreamersApi : realApi.streamersApi
export const videoApi = USE_MOCK_DATA ? mockVideoApi : realApi.videoApi  
export const recordingApi = USE_MOCK_DATA ? mockRecordingApi : realApi.recordingApi
export const backgroundQueueApi = USE_MOCK_DATA ? mockBackgroundQueueApi : realApi.backgroundQueueApi
export const settingsApi = USE_MOCK_DATA ? mockSettingsApi : realApi.settingsApi
export const notificationApi = USE_MOCK_DATA ? mockNotificationApi : realApi.notificationApi
export const systemApi = USE_MOCK_DATA ? mockSystemApi : realApi.systemApi
export const streamsApi = USE_MOCK_DATA ? mockStreamsApi : realApi.streamsApi
export const authApi = USE_MOCK_DATA ? mockAuthApi : realApi.authApi
export const imagesApi = USE_MOCK_DATA ? mockImagesApi : realApi.imagesApi
export const subscriptionsApi = USE_MOCK_DATA ? mockSubscriptionsApi : (realApi.subscriptionsApi || { getAll: () => Promise.resolve([]) })
export const categoriesApi = USE_MOCK_DATA ? mockCategoriesApi : (realApi.categoriesApi || { getAll: () => Promise.resolve([]) })
export const filenamePresetsApi = USE_MOCK_DATA ? mockFilenamePresetsApi : (realApi.filenamePresetsApi || { getAll: () => Promise.resolve([]) })

// Proxy API only exists in mock mode (no real backend endpoint yet)
export const proxyApi = USE_MOCK_DATA ? mockProxyApi : {
  getAll: () => Promise.resolve([]),
  create: () => Promise.resolve({ success: false }),
  update: () => Promise.resolve({ success: false }),
  delete: () => Promise.resolve({ success: false }),
  test: () => Promise.resolve({ success: false }),
  healthCheck: () => Promise.resolve({ healthy: 0, unhealthy: 0 })
}
