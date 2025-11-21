/**
 * Development Mode Toggle
 * 
 * Set VITE_USE_MOCK_DATA=true in .env to use mock data
 * This allows frontend development without a running backend
 */

import { mockApi } from '@/mocks/mockApi'
import { 
  streamersApi as realStreamersApi,
  videoApi as realVideoApi,
  recordingApi as realRecordingApi,
  categoriesApi as realCategoriesApi,
  backgroundQueueApi as realBackgroundQueueApi,
  settingsApi as realSettingsApi,
  authApi as realAuthApi,
  proxyApi as realProxyApi,
  notificationApi as realNotificationApi
} from './api'

// Check if mock mode is enabled
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true'

// Log mode on startup
if (USE_MOCK_DATA) {
  console.log('🎭 MOCK MODE ENABLED - Using mock data for development')
} else {
  console.log('🌐 LIVE MODE - Connecting to real backend')
}

// Export API with conditional logic
export const streamersApi = USE_MOCK_DATA ? mockApi.streamers : realStreamersApi
export const videoApi = USE_MOCK_DATA ? mockApi.videos : realVideoApi
export const recordingApi = USE_MOCK_DATA ? mockApi.recordings : realRecordingApi
export const categoriesApi = USE_MOCK_DATA ? mockApi.categories : realCategoriesApi
export const queueApi = USE_MOCK_DATA ? mockApi.queue : realBackgroundQueueApi
export const backgroundQueueApi = queueApi
export const settingsApi = USE_MOCK_DATA ? mockApi.settings : realSettingsApi
export const twitchApi = USE_MOCK_DATA ? mockApi.twitch : realAuthApi
export const authApi = twitchApi
export const proxyApi = USE_MOCK_DATA ? mockApi.proxies : realProxyApi
export const notificationsApi = USE_MOCK_DATA ? mockApi.notifications : realNotificationApi

// Helper to check current mode
export const isMockMode = () => USE_MOCK_DATA
