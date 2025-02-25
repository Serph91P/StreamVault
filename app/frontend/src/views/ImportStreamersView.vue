<template>
    <div class="import-streamers-container">
      <h2 class="page-title">Import Twitch Streamers</h2>
      
      <div v-if="error" class="error-message">
        {{ error }}
      </div>
      
      <div v-if="!isAuthenticated && !loading" class="auth-section">
        <p class="description">
          Connect with your Twitch account to import streamers you follow.
        </p>
        <button @click="startTwitchAuth" class="btn btn-twitch">
          <i class="fa fa-twitch"></i> Connect with Twitch
        </button>
      </div>
      
      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
        <p>{{ loadingMessage }}</p>
      </div>
      
      <div v-if="isAuthenticated && !importing" class="selection-section">
        <div class="controls">
          <div class="search-box">
            <input 
              type="text" 
              v-model="searchQuery" 
              placeholder="Search streamers..." 
              class="search-input"
            />
          </div>
          
          <div class="selection-actions">
            <button 
              @click="selectAll" 
              class="btn btn-secondary" 
              :disabled="filteredChannels.length === 0"
            >
              Select All
            </button>
            <button 
              @click="deselectAll" 
              class="btn btn-secondary" 
              :disabled="selectedStreamers.length === 0"
            >
              Deselect All
            </button>
            <button 
              @click="importSelected" 
              class="btn btn-primary" 
              :disabled="selectedStreamers.length === 0"
            >
              Import {{ selectedStreamers.length }} Streamers
            </button>
          </div>
        </div>
        
        <div v-if="channels.length === 0" class="no-channels">
          You don't follow any channels on Twitch.
        </div>
        
        <div v-else-if="filteredChannels.length === 0" class="no-results">
          No channels match your search.
        </div>
        
        <div v-else class="channels-grid">
          <div 
            v-for="channel in filteredChannels" 
            :key="channel.id"
            class="channel-card"
            :class="{ selected: isSelected(channel) }"
            @click="toggleSelection(channel)"
          >
            <div class="channel-content">
              <div class="channel-name">{{ channel.display_name }}</div>
              <div class="channel-login">{{ channel.login }}</div>
            </div>
            <div class="selection-indicator">
              <i class="fa" :class="isSelected(channel) ? 'fa-check-circle' : 'fa-circle-o'"></i>
            </div>
          </div>
        </div>
      </div>
      
      <div v-if="importResults" class="import-results">
        <h3>Import Results</h3>
        <div class="results-summary">
          <div class="result-item">
            <span class="result-label">Total:</span>
            <span class="result-value">{{ importResults.total }}</span>
          </div>
          <div class="result-item">
            <span class="result-label">Added:</span>
            <span class="result-value success">{{ importResults.added }}</span>
          </div>
          <div class="result-item">
            <span class="result-label">Skipped:</span>
            <span class="result-value info">{{ importResults.skipped }}</span>
          </div>
          <div class="result-item">
            <span class="result-label">Failed:</span>
            <span class="result-value error">{{ importResults.failed }}</span>
          </div>
        </div>
        
        <div v-if="importResults.failures && importResults.failures.length > 0" class="failure-list">
          <h4>Failures:</h4>
          <ul>
            <li v-for="(failure, index) in importResults.failures" :key="index">
              <strong>{{ failure.username }}</strong>: {{ failure.reason }}
            </li>
          </ul>
        </div>
        
        <button @click="resetImport" class="btn btn-primary">Import More Streamers</button>
      </div>
    </div>
  </template>
  
  <script setup lang="ts">
  import { ref, computed, onMounted } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  
  interface Channel {
    id: string
    login: string
    display_name: string
  }
  
  interface ImportResults {
    total: number
    added: number
    skipped: number
    failed: number
    failures: Array<{
      username: string
      reason: string
    }>
  }
  
  const route = useRoute()
  const router = useRouter()
  
  // State
  const channels = ref<Channel[]>([])
  const selectedStreamers = ref<Channel[]>([])
  const accessToken = ref<string | null>(null)
  const error = ref<string | null>(null)
  const loading = ref<boolean>(false)
  const loadingMessage = ref<string>('Loading...')
  const searchQuery = ref<string>('')
  const importing = ref<boolean>(false)
  const importResults = ref<ImportResults | null>(null)
  
  // Computed
  const isAuthenticated = computed(() => !!accessToken.value)
  
  const filteredChannels = computed(() => {
    if (!searchQuery.value) return channels.value
    
    const query = searchQuery.value.toLowerCase()
    return channels.value.filter(channel => 
      channel.login.toLowerCase().includes(query) || 
      channel.display_name.toLowerCase().includes(query)
    )
  })
  
  // Methods
  function isSelected(channel: Channel): boolean {
    return selectedStreamers.value.some(s => s.id === channel.id)
  }
  
  function toggleSelection(channel: Channel): void {
    const index = selectedStreamers.value.findIndex(s => s.id === channel.id)
    
    if (index === -1) {
      selectedStreamers.value.push(channel)
    } else {
      selectedStreamers.value.splice(index, 1)
    }
  }
  
  function selectAll(): void {
    selectedStreamers.value = [...filteredChannels.value]
  }
  
  function deselectAll(): void {
    selectedStreamers.value = []
  }
  
  async function startTwitchAuth(): Promise<void> {
    try {
      loading.value = true
      loadingMessage.value = 'Connecting to Twitch...'
      
      const response = await fetch('/api/twitch/auth-url')
      const data = await response.json()
      
      window.location.href = data.auth_url
    } catch (err: any) {
      error.value = err.message || 'Failed to start Twitch authentication'
      loading.value = false
    }
  }
  
  async function loadFollowedChannels(token: string): Promise<void> {
    try {
      loading.value = true
      loadingMessage.value = 'Loading channels you follow...'
      
      const response = await fetch(`/api/twitch/followed-channels?access_token=${token}`)
      
      if (!response.ok) {
        throw new Error('Failed to load followed channels')
      }
      
      const data = await response.json()
      channels.value = data.channels || []
    } catch (err: any) {
      error.value = err.message || 'Failed to load followed channels'
    } finally {
      loading.value = false
    }
  }
  
  async function importSelected(): Promise<void> {
    if (selectedStreamers.value.length === 0) return
    
    try {
      importing.value = true
      loading.value = true
      loadingMessage.value = 'Importing selected streamers...'
      
      const response = await fetch('/api/twitch/import-streamers', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(selectedStreamers.value)
      })
      
      if (!response.ok) {
        throw new Error('Failed to import streamers')
      }
      
      const results = await response.json()
      importResults.value = results
    } catch (err: any) {
      error.value = err.message || 'Failed to import streamers'
    } finally {
      loading.value = false
      importing.value = false
    }
  }
  
  function resetImport(): void {
    importResults.value = null
    selectedStreamers.value = []
  }
  
  // Lifecycle
  onMounted(async () => {
    // Check if we've returned from Twitch auth
    const tokenParam = route.query.token as string | undefined
    const errorParam = route.query.error as string | undefined
    
    if (errorParam) {
      error.value = errorParam === 'auth_failed' 
        ? 'Authentication failed. Please try again.' 
        : errorParam
    }
    
    if (tokenParam) {
      accessToken.value = tokenParam
      // Clear the token from URL for security
      router.replace({ query: {} })
      // Load followed channels
      await loadFollowedChannels(tokenParam)
    }
  })
  </script>
  