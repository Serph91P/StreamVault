// API client for StreamVault

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
  private baseURL: string

  constructor() {
    this.baseURL = import.meta.env.VITE_API_URL || ''
  }

  async request(endpoint: string, options: RequestConfig = {}): Promise<any> {
    const url = `${this.baseURL}${endpoint}`

    const config: RequestConfig = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
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
    apiClient.post(`/api/recordings/start`, { streamer_id: streamerId }),

  // Stop recording for a specific streamer
  stopRecording: (streamerId: number) => 
    apiClient.post(`/api/recordings/stop`, { streamer_id: streamerId }),

  // Get all active recordings
  getActiveRecordings: () => 
    apiClient.get('/api/recordings/active'),

  // Get recording settings
  getSettings: () => 
    apiClient.get('/api/recording-settings'),

  // Update recording settings
  updateSettings: (settings: any) => 
    apiClient.put('/api/recording-settings', settings),

  // Get streamer-specific recording settings
  getStreamerSettings: (streamerId: number) => 
    apiClient.get(`/api/streamers/${streamerId}/recording-settings`),

  // Update streamer-specific recording settings
  updateStreamerSettings: (streamerId: number, settings: any) => 
    apiClient.put(`/api/streamers/${streamerId}/recording-settings`, settings),

  // Force start recording (bypasses normal checks)
  forceStartRecording: (streamerId: number) => 
    apiClient.post(`/api/recordings/force-start`, { streamer_id: streamerId }),

  // Force stop recording
  forceStopRecording: (recordingId: number) => 
    apiClient.post(`/api/recordings/force-stop`, { recording_id: recordingId }),

  // Get recording status for a specific recording
  getRecordingStatus: (recordingId: number) => 
    apiClient.get(`/api/recordings/${recordingId}/status`),

  // Delete a recording
  deleteRecording: (recordingId: number) => 
    apiClient.delete(`/api/recordings/${recordingId}`),

  // Get recording history
  getRecordingHistory: (params: Record<string, any> = {}) => 
    apiClient.get('/api/recordings/history', params),
}

// Streamers API endpoints  
export const streamersApi = {
  // Get all streamers
  getAll: () => 
    apiClient.get('/api/streamers'),

  // Get a specific streamer
  get: (streamerId: number) => 
    apiClient.get(`/api/streamers/${streamerId}`),

  // Add a new streamer
  add: (streamerData: any) => 
    apiClient.post('/api/streamers', streamerData),

  // Update a streamer
  update: (streamerId: number, streamerData: any) => 
    apiClient.put(`/api/streamers/${streamerId}`, streamerData),

  // Delete a streamer
  delete: (streamerId: number) => 
    apiClient.delete(`/api/streamers/${streamerId}`),

  // Get streamer's streams
  getStreams: (streamerId: number, params: Record<string, any> = {}) => 
    apiClient.get(`/api/streamers/${streamerId}/streams`, params),
}

// Streams API endpoints
export const streamsApi = {
  // Get all streams
  getAll: (params: Record<string, any> = {}) => 
    apiClient.get('/api/streams', params),

  // Get a specific stream
  get: (streamId: number) => 
    apiClient.get(`/api/streams/${streamId}`),

  // Delete a stream
  delete: (streamId: number) => 
    apiClient.delete(`/api/streams/${streamId}`),

  // Delete all streams for a streamer
  deleteAllForStreamer: (streamerId: number) => 
    apiClient.delete(`/api/streamers/${streamerId}/streams`),
}

// System API endpoints
export const systemApi = {
  // Get system status
  getStatus: () => 
    apiClient.get('/api/status'),

  // Get system logs
  getLogs: (params: Record<string, any> = {}) => 
    apiClient.get('/api/system/logs', params),

  // Get system settings
  getSettings: () => 
    apiClient.get('/api/system/settings'),

  // Update system settings
  updateSettings: (settings: any) => 
    apiClient.put('/api/system/settings', settings),
}

// Export the main API client as default
export default apiClient
