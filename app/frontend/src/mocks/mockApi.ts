/**
 * Mock API Service
 * 
 * Drop-in replacement for real API calls during development
 * Enable with VITE_USE_MOCK_DATA=true in .env
 */

import {
  mockStreamers,
  mockVideos,
  mockActiveRecordings,
  mockCategories,
  mockChapters,
  mockQueueStats,
  mockActiveTasks,
  mockSettings,
  mockProxies,
  mockVersionInfo
} from './mockData'

// Simulate network delay (can be adjusted)
const MOCK_DELAY_MS = 300

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

// Helper to simulate API response
const mockResponse = async <T>(data: T, delayMs = MOCK_DELAY_MS): Promise<T> => {
  await delay(delayMs)
  return data
}

export const mockApi = {
  // Streamers
  streamers: {
    getAll: () => mockResponse(mockStreamers),
    getById: (id: number) => mockResponse(mockStreamers.find(s => s.id === id)),
    create: (data: any) => mockResponse({ ...data, id: Date.now() }),
    update: (id: number, data: any) => mockResponse({ ...data, id }),
    delete: (id: number) => mockResponse({ success: true }),
    validate: (username: string) => mockResponse({ 
      valid: true, 
      user_id: '12345',
      display_name: username,
      profile_image_url: 'https://static-cdn.jtvnw.net/user-default-pictures-uv/cdd517fe-def4-11e9-948e-784f43822e80-profile_image-300x300.png'
    }),
    forceRecord: (id: number) => mockResponse({ success: true, message: 'Recording started' })
  },

  // Videos
  videos: {
    getAll: () => mockResponse(mockVideos),
    getById: (id: number) => mockResponse(mockVideos.find(v => v.id === id)),
    getByStreamer: (streamerId: number) => mockResponse(
      mockVideos.filter(v => v.streamer_id === streamerId)
    ),
    delete: (id: number) => mockResponse({ success: true }),
    getChapters: (id: number) => mockResponse(mockChapters.filter(c => c.stream_id === id))
  },

  // Recordings
  recordings: {
    getActive: () => mockResponse(mockActiveRecordings),
    stop: (id: number) => mockResponse({ success: true, message: 'Recording stopped' })
  },

  // Categories
  categories: {
    getAll: () => mockResponse(mockCategories),
    getFavorites: () => mockResponse(mockCategories.filter(c => c.is_favorite)),
    toggleFavorite: (id: string) => mockResponse({ success: true }),
    search: (query: string) => mockResponse(
      mockCategories.filter(c => c.name.toLowerCase().includes(query.toLowerCase()))
    )
  },

  // Background Queue
  queue: {
    getStats: () => mockResponse(mockQueueStats),
    getActiveTasks: () => mockResponse(mockActiveTasks),
    getRecentTasks: () => mockResponse([])
  },

  // Settings
  settings: {
    getAll: () => mockResponse(mockSettings),
    update: (section: string, data: any) => mockResponse({ ...mockSettings, [section]: data }),
    getVersion: () => mockResponse(mockVersionInfo)
  },

  // Twitch
  twitch: {
    getStatus: () => mockResponse({ 
      connected: true, 
      token_expires: mockSettings.twitch.oauth_token_expires,
      status: 'valid'
    }),
    disconnect: () => mockResponse({ success: true }),
    getFollowedChannels: () => mockResponse([
      { user_id: '123', user_login: 'example1', user_name: 'Example1' },
      { user_id: '456', user_login: 'example2', user_name: 'Example2' }
    ])
  },

  // Proxies
  proxies: {
    getAll: () => mockResponse(mockProxies),
    create: (data: any) => mockResponse({ ...data, id: Date.now() }),
    update: (id: number, data: any) => mockResponse({ ...data, id }),
    delete: (id: number) => mockResponse({ success: true }),
    testHealth: (id: number) => mockResponse({ 
      healthy: true, 
      response_time_ms: Math.random() * 200 
    })
  },

  // Notifications
  notifications: {
    getHistory: () => mockResponse([]),
    markAsRead: (id: number) => mockResponse({ success: true }),
    clearAll: () => mockResponse({ success: true })
  }
}
