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
        <svg viewBox="0 0 24 24" width="16" height="16" style="margin-right: 8px;">
          <path fill="white" d="M11.64 5.93H13.07V10.21H11.64M15.57 5.93H17V10.21H15.57M7 2L3.43 5.57V18.43H7.71V22L11.29 18.43H14.14L20.57 12V2M19.14 11.29L16.29 14.14H13.43L10.93 16.64V14.14H7.71V3.43H19.14Z"/>
        </svg>
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
            <svg viewBox="0 0 24 24" width="16" height="16">
              <path fill="currentColor" d="M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z" />
            </svg>
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
/* Twitch Import Form Styling */
.twitch-import-container {
  background-color: var(--background-card);
  border-radius: var(--border-radius);
  padding: var(--spacing-lg);
  border: 1px solid var(--border-color);
}

/* Auth Section */
.auth-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-lg) 0;
}

.btn-twitch {
  background-color: #9146FF;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-md) var(--spacing-lg);
  border-radius: var(--border-radius);
  border: none;
  font-weight: 600;
  transition: all 0.3s var(--vue-ease);
  margin-top: var(--spacing-lg);
}

.btn-twitch:hover {
  background-color: #7f3edd;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(145, 70, 255, 0.3);
}

.btn-twitch:active {
  transform: translateY(0);
}

.setup-hint {
  background-color: var(--background-darker);
  padding: var(--spacing-md);
  border-radius: var(--border-radius);
  border-left: 3px solid var(--primary-color);
  width: 100%;
  max-width: 800px;
  margin-bottom: var(--spacing-md);
}

.callback-url {
  margin-top: var(--spacing-sm);
  padding: var(--spacing-sm);
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: var(--border-radius-sm);
  overflow-x: auto;
}

code {
  font-family: monospace;
  background-color: rgba(255, 255, 255, 0.1);
  padding: 2px 4px;
  border-radius: var(--border-radius-sm);
}

/* Loading */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(var(--primary-color-rgb, 66, 184, 131), 0.1);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s ease-in-out infinite;
  margin-bottom: var(--spacing-md);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Filter Container */
.filter-container {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--spacing-lg);
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.search-box {
  flex: 1;
  min-width: 200px;
}

.filter-buttons {
  display: flex;
  gap: var(--spacing-sm);
}

@media (max-width: 768px) {
  .filter-container {
    flex-direction: column;
  }
  
  .filter-buttons {
    width: 100%;
    flex-wrap: wrap;
    margin-top: var(--spacing-sm);
  }
  
  .filter-buttons button {
    flex: 1;
    white-space: nowrap;
    padding-left: var(--spacing-sm);
    padding-right: var(--spacing-sm);
    font-size: 0.9rem;
  }
}

/* Channels Grid */
.channels-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--spacing-md);
}

.channel-card {
  background-color: var(--background-darker);
  border-radius: var(--border-radius);
  padding: var(--spacing-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid var(--border-color);
  transition: all 0.2s var(--vue-ease);
}

.channel-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
  border-color: var(--primary-color-muted);
}

.channel-card.selected {
  border-color: var(--primary-color);
  background-color: rgba(var(--primary-color-rgb, 66, 184, 131), 0.1);
}

.channel-content {
  flex: 1;
  overflow: hidden;
}

.channel-name {
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.channel-login {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.selection-indicator {
  opacity: 0;
  color: var(--primary-color);
  font-size: 1.2rem;
  margin-left: var(--spacing-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
}

.channel-card.selected .selection-indicator {
  opacity: 1;
}

/* No Data State */
.no-data-container {
  text-align: center;
  padding: var(--spacing-xl);
  background-color: var(--background-darker);
  border-radius: var(--border-radius);
  color: var(--text-secondary);
}

/* Error Message */
.error-message {
  background-color: rgba(var(--danger-color-rgb, 239, 68, 68), 0.1);
  color: var(--danger-color);
  padding: var(--spacing-md);
  border-radius: var(--border-radius);
  margin-bottom: var(--spacing-lg);
}

.callback-url-hint {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background-color: rgba(255, 255, 255, 0.05);
  border-radius: var(--border-radius);
  border-left: 3px solid #ff9800;
}

/* Import Results */
.results-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  background-color: var(--background-darker);
  padding: var(--spacing-md);
  border-radius: var(--border-radius);
}

.result-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.result-label {
  font-weight: 600;
  margin-bottom: var(--spacing-xs);
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.result-value {
  font-size: 1.5rem;
  font-weight: 600;
}

.result-value.success {
  color: var(--success-color, #42b883);
}

.result-value.error {
  color: var(--danger-color, #ef4444);
}

.result-value.info {
  color: var(--info-color, #3b82f6);
}

.failure-list {
  background-color: rgba(var(--danger-color-rgb, 239, 68, 68), 0.1);
  padding: var(--spacing-md);
  border-radius: var(--border-radius);
  margin-bottom: var(--spacing-lg);
}

.failure-list h4 {
  margin-top: 0;
  color: var(--danger-color);
}

.failure-list ul {
  padding-left: var(--spacing-lg);
  margin: var(--spacing-sm) 0 0;
}

.failure-list li {
  margin-bottom: var(--spacing-sm);
}

.import-results {
  padding: var(--spacing-lg);
  background-color: var(--background-card);
  border-radius: var(--border-radius);
  margin-top: var(--spacing-xl);
  border: 1px solid var(--border-color);
}
</style>
