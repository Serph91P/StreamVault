<template>
  <div class="twitch-import-container">
    <div v-if="error" class="error-message">
      {{ error }}
      
      <!-- Callback URL guidance for redirect_mismatch error -->
      <div v-if="error.includes('redirect_mismatch')" class="callback-url-hint">
        <p><strong>Important:</strong> The Redirect URI in your Twitch Developer Dashboard must match the callback URL of your StreamVault installation.</p>
        <p v-if="callbackUrl" class="callback-url">
          Configure this URL in your Twitch Developer Dashboard:<br>
          <code>{{ callbackUrl }}</code>
        </p>
        <p v-else>
          Configure the following URL in your Twitch Developer Dashboard:<br>
          <code>https://your-streamvault-domain.com/api/twitch/callback</code><br>
          Replace "your-streamvault-domain.com" with your actual domain.
        </p>
      </div>
    </div>
    
    <div v-if="!isAuthenticated && !loading" class="auth-section">
      <!-- General guidance about callback URL -->
      <div class="setup-hint">
        <p>Before connecting to Twitch, make sure the callback URL is correctly configured in your Twitch Developer Dashboard.</p>
        <p v-if="callbackUrl" class="callback-url">
          <strong>Callback URL:</strong> <code>{{ callbackUrl }}</code>
        </p>
        <p v-else>
          <strong>Callback URL format:</strong> <code>https://your-streamvault-domain.com/api/twitch/callback</code>
        </p>
      </div>
      
      <button @click="startTwitchAuth" class="btn btn-twitch">
        Connect with Twitch
      </button>
    </div>
    
    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p>{{ loadingMessage }}</p>
    </div>
    
    <div v-if="isAuthenticated && !importing" class="selection-section">
      <div class="filter-container">
        <div class="search-box">
          <input 
            type="text" 
            v-model="searchQuery" 
            placeholder="Search streamers..." 
            class="form-control"
          />
        </div>
        
        <div class="filter-buttons">
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
      
      <div v-if="channels.length === 0" class="no-data-container">
        You don't follow any channels on Twitch.
      </div>
      
      <div v-else-if="filteredChannels.length === 0" class="no-data-container">
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
            ✓
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="importResults" class="import-results content-section">
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

const emit = defineEmits(['streamers-imported'])

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
const callbackUrl = ref<string | null>(null)

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
async function fetchCallbackUrl() {
  try {
    const response = await fetch('/api/twitch/callback-url')
    if (response.ok) {
      const data = await response.json()
      callbackUrl.value = data.url
    }
  } catch (err) {
    console.error('Failed to fetch callback URL:', err)
    // We don't set an error as this is not critical
  }
}

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
    
    // Emit an event if the import was successful
    if (results.added > 0) {
      emit('streamers-imported')
    }
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

function dismissError(): void {
  error.value = null
}

// Lifecycle
onMounted(async () => {
  // Fetch callback URL
  await fetchCallbackUrl()
  
  // Check if we've returned from Twitch auth
  const tokenParam = route.query.token as string | undefined
  const errorParam = route.query.error as string | undefined
  
  if (errorParam) {
    if (errorParam === 'redirect_mismatch') {
      error.value = 'redirect_mismatch: The Redirect URL in your Twitch Developer Dashboard does not match your StreamVault configuration.'
    } else {
      error.value = errorParam === 'auth_failed' 
        ? 'Authentication failed. Please try again.' 
        : errorParam
    }
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

<style scoped>
/* Diese speziellen Styles sind spezifisch für dieses Komponente und ergänzen das Design-System */
.callback-url-hint {
  margin-top: 15px;
  padding: 10px;
  background-color: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  border-left: 3px solid #ff9800;
}

.results-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 10px;
  margin-bottom: 1.5rem;
  background-color: rgba(0, 0, 0, 0.2);
  padding: 1rem;
  border-radius: 6px;
}

.result-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.result-label {
  font-weight: bold;
  margin-bottom: 0.25rem;
  font-size: 0.9rem;
}

.result-value {
  font-size: 1.5rem;
  font-weight: 600;
}

.result-value.success {
  color: var(--success-color);
}

.result-value.error {
  color: var(--danger-color);
}

.result-value.info {
  color: #17a2b8;
}

.failure-list {
  background-color: rgba(220, 53, 69, 0.1);
  padding: 1rem;
  border-radius: 4px;
  margin-bottom: 1.5rem;
}

.failure-list h4 {
  margin-top: 0;
  color: var(--danger-color);
}

.failure-list ul {
  padding-left: 1.5rem;
  margin: 0.5rem 0 0;
}

.failure-list li {
  margin-bottom: 0.5rem;
}

.import-results {
  padding: 1.5rem;
  background-color: var(--background-darker);
  border-radius: 6px;
  margin-top: 2rem;
}
</style>
</template>
