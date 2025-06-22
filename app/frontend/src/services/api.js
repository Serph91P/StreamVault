// API client for StreamVault
class ApiClient {
  constructor() {
    this.baseURL = import.meta.env.VITE_API_URL || ''
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`
    
    const config = {
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

  async get(endpoint, params = {}) {
    const searchParams = new URLSearchParams(params)
    const url = searchParams.toString() ? `${endpoint}?${searchParams}` : endpoint
    
    return this.request(url, {
      method: 'GET',
    })
  }

  async post(endpoint, data = {}) {
    return this.request(endpoint, {
      method: 'POST',
      body: data,
    })
  }

  async put(endpoint, data = {}) {
    return this.request(endpoint, {
      method: 'PUT',
      body: data,
    })
  }

  async delete(endpoint) {
    return this.request(endpoint, {
      method: 'DELETE',
    })
  }

  async patch(endpoint, data = {}) {
    return this.request(endpoint, {
      method: 'PATCH',
      body: data,
    })
  }
}

// Create singleton instance
export const api = new ApiClient()

// Video-specific API methods
export const videoApi = {
  async getAllVideos() {
    return api.get('/api/videos')
  },

  async getStreamerVideos(streamerName) {
    return api.get(`/api/videos/${encodeURIComponent(streamerName)}`)
  },

  getVideoStreamUrl(streamerName, filename) {
    return `${api.baseURL}/api/videos/stream/${encodeURIComponent(streamerName)}/${encodeURIComponent(filename)}`
  },

  getVideoDownloadUrl(streamerName, filename) {
    return `${api.baseURL}/api/videos/stream/${encodeURIComponent(streamerName)}/${encodeURIComponent(filename)}?download=true`
  }
}

// Streamer API methods
export const streamerApi = {
  async getAllStreamers() {
    return api.get('/api/streamers')
  },

  async getStreamer(streamerId) {
    return api.get(`/api/streamers/${streamerId}`)
  },

  async addStreamer(streamerData) {
    return api.post('/api/streamers', streamerData)
  },

  async updateStreamer(streamerId, streamerData) {
    return api.put(`/api/streamers/${streamerId}`, streamerData)
  },

  async deleteStreamer(streamerId) {
    return api.delete(`/api/streamers/${streamerId}`)
  },

  async getStreamerStreams(streamerName) {
    return api.get(`/api/streamers/${encodeURIComponent(streamerName)}/streams`)
  }
}

// Settings API methods
export const settingsApi = {
  async getSettings() {
    return api.get('/api/settings')
  },

  async updateSettings(settings) {
    return api.put('/api/settings', settings)
  },

  async testTwitchConnection() {
    return api.post('/api/settings/test-twitch')
  }
}

// Auth API methods
export const authApi = {
  async login(credentials) {
    return api.post('/auth/login', credentials)
  },

  async logout() {
    return api.post('/auth/logout')
  },

  async getCurrentUser() {
    return api.get('/auth/me')
  },

  async setupAdmin(adminData) {
    return api.post('/auth/setup', adminData)
  }
}

// Recording API methods
export const recordingApi = {
  async getRecordings() {
    return api.get('/api/recordings')
  },

  async startRecording(streamerId) {
    return api.post(`/api/recordings/start/${streamerId}`)
  },

  async stopRecording(streamerId) {
    return api.post(`/api/recordings/stop/${streamerId}`)
  },

  async getRecordingStatus(streamerId) {
    return api.get(`/api/recordings/status/${streamerId}`)
  }
}

export default api
