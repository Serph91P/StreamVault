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
import { authApi } from '@/services/api'

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
    const data = await authApi.getCallbackUrl()
    callbackUrl.value = data.url
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
    
    const data = await authApi.getAuthUrl()
    
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
    
    const data = await authApi.getFollowedChannels()
    
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
    
    const streamerIds = selectedStreamers.value.map(s => parseInt(s.id))
    const results = await authApi.importStreamers(streamerIds)
    
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
  background-color: var(--background-card, #1f1f23);
  border-radius: var(--border-radius, 8px);
  padding: var(--spacing-lg, 1.5rem);
  border: 1px solid var(--border-color, #2d2d35);
}

/* Auth Section */
.auth-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-md, 1rem) 0;
}

/* Vue-styled Twitch button */
.btn-twitch {
  background-color: #9146FF;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.75rem 1.5rem;
  border-radius: var(--border-radius, 8px);
  border: none;
  font-weight: 600;
  font-size: 0.95rem;
  transition: all 0.25s var(--vue-ease, cubic-bezier(0.25, 0.8, 0.5, 1));
  cursor: pointer;
  box-shadow: none;
  position: relative;
  overflow: hidden;
  margin-top: var(--spacing-md, 1rem);
}

.btn-twitch:hover {
  background-color: #7d5bbe;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(145, 70, 255, 0.25);
}

.btn-twitch:active {
  transform: translateY(0);
  box-shadow: 0 2px 4px rgba(145, 70, 255, 0.2);
}

/* Vue-style ripple effect */
.btn-twitch::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 5px;
  height: 5px;
  background: rgba(255, 255, 255, 0.5);
  opacity: 0;
  border-radius: 100%;
  transform: scale(1, 1) translate(-50%);
  transform-origin: 50% 50%;
}

.btn-twitch:focus:not(:active)::after {
  animation: ripple 0.8s ease-out;
}

@keyframes ripple {
  0% {
    transform: scale(0, 0);
    opacity: 0.5;
  }
  100% {
    transform: scale(20, 20);
    opacity: 0;
  }
}

.setup-hint {
  background-color: var(--background-darker, #18181b);
  padding: var(--spacing-md, 1rem);
  border-radius: var(--border-radius, 8px);
  border-left: 3px solid var(--primary-color, #42b883);
  width: 100%;
  max-width: 800px;
  margin-bottom: var(--spacing-md, 1rem);
  font-size: 0.95rem;
  line-height: 1.6;
  color: var(--text-secondary, #adadb8);
}

.callback-url {
  margin-top: var(--spacing-sm, 0.5rem);
  padding: var(--spacing-sm, 0.5rem);
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: var(--border-radius-sm, 4px);
  overflow-x: auto;
  font-size: 0.9rem;
}

code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  background-color: rgba(255, 255, 255, 0.1);
  padding: 2px 4px;
  border-radius: var(--border-radius-sm, 4px);
  font-size: 0.9em;
}

/* Loading */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: var(--text-secondary, #adadb8);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(var(--primary-color-rgb, 66, 184, 131), 0.1);
  border-top-color: var(--primary-color, #42b883);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: var(--spacing-md, 1rem);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Filter Container */
.filter-container {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--spacing-lg, 1.5rem);
  gap: var(--spacing-md, 1rem);
  flex-wrap: wrap;
}

.search-box {
  flex: 1;
  min-width: 200px;
}

.filter-buttons {
  display: flex;
  gap: var(--spacing-sm, 0.5rem);
}

@media (max-width: 768px) {
  .filter-container {
    flex-direction: column;
  }
  
  .filter-buttons {
    width: 100%;
    flex-wrap: wrap;
    margin-top: var(--spacing-sm, 0.5rem);
  }
  
  .filter-buttons button {
    flex: 1;
    white-space: nowrap;
    padding-left: var(--spacing-sm, 0.5rem);
    padding-right: var(--spacing-sm, 0.5rem);
    font-size: 0.9rem;
  }
}

/* Channels Grid */
.channels-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--spacing-md, 1rem);
}

.channel-card {
  background-color: var(--background-darker, #18181b);
  border-radius: var(--border-radius, 8px);
  padding: var(--spacing-md, 1rem);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid var(--border-color, #2d2d35);
  transition: all 0.25s var(--vue-ease, cubic-bezier(0.25, 0.8, 0.5, 1));
}

.channel-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm, 0 2px 8px rgba(0, 0, 0, 0.1));
  border-color: var(--primary-color-muted, rgba(66, 184, 131, 0.5));
  background-color: rgba(var(--background-darker-rgb, 24, 24, 27), 0.8);
}

.channel-card.selected {
  border-color: var(--primary-color, #42b883);
  background-color: rgba(var(--primary-color-rgb, 66, 184, 131), 0.1);
}

.channel-content {
  flex: 1;
  overflow: hidden;
}

.channel-name {
  font-weight: 600;
  color: var(--text-primary, #efeff1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.channel-login {
  font-size: 0.9rem;
  color: var(--text-secondary, #adadb8);
}

.selection-indicator {
  opacity: 0;
  color: var(--primary-color, #42b883);
  margin-left: var(--spacing-sm, 0.5rem);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.channel-card.selected .selection-indicator {
  opacity: 1;
  transform: scale(1.2);
}

/* No Data State */
.no-data-container {
  text-align: center;
  padding: var(--spacing-xl, 2rem);
  background-color: var(--background-darker, #18181b);
  border-radius: var(--border-radius, 8px);
  color: var(--text-secondary, #adadb8);
  border: 1px dashed var(--border-color, #2d2d35);
}

/* Error Message */
.error-message {
  background-color: rgba(var(--danger-color-rgb, 239, 68, 68), 0.1);
  color: var(--danger-color, #ef4444);
  padding: var(--spacing-md, 1rem);
  border-radius: var(--border-radius, 8px);
  margin-bottom: var(--spacing-lg, 1.5rem);
}

.callback-url-hint {
  margin-top: var(--spacing-md, 1rem);
  padding: var(--spacing-md, 1rem);
  background-color: rgba(255, 255, 255, 0.05);
  border-radius: var(--border-radius, 8px);
  border-left: 3px solid #ff9800;
}

/* Import Results */
.results-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: var(--spacing-md, 1rem);
  margin-bottom: var(--spacing-lg, 1.5rem);
  background-color: var(--background-darker, #18181b);
  padding: var(--spacing-md, 1rem);
  border-radius: var(--border-radius, 8px);
}

.result-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.result-label {
  font-weight: 600;
  margin-bottom: var(--spacing-xs, 0.25rem);
  font-size: 0.9rem;
  color: var(--text-secondary, #adadb8);
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
  padding: var(--spacing-md, 1rem);
  border-radius: var(--border-radius, 8px);
  margin-bottom: var(--spacing-lg, 1.5rem);
}

.failure-list h4 {
  margin-top: 0;
  color: var(--danger-color, #ef4444);
}

.failure-list ul {
  padding-left: var(--spacing-lg, 1.5rem);
  margin: var(--spacing-sm, 0.5rem) 0 0;
}

.failure-list li {
  margin-bottom: var(--spacing-sm, 0.5rem);
}

.import-results {
  padding: var(--spacing-lg, 1.5rem);
  background-color: var(--background-card, #1f1f23);
  border-radius: var(--border-radius, 8px);
  margin-top: var(--spacing-xl, 2rem);
  border: 1px solid var(--border-color, #2d2d35);
}

/* Standard buttons - match Vue.js style */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border-radius: var(--border-radius-sm, 6px);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.25s var(--vue-ease, cubic-bezier(0.25, 0.8, 0.5, 1));
  border: none;
  font-size: 0.95rem;
  line-height: 1.5;
  white-space: nowrap;
  box-shadow: none;
}

.btn-primary {
  background-color: var(--primary-color, #42b883);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: var(--primary-color-hover, #3ca978);
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(66, 184, 131, 0.25);
}

.btn-secondary {
  background-color: rgba(255, 255, 255, 0.1);
  color: var(--text-primary, #efeff1);
  border: 1px solid var(--border-color, #2d2d35);
}

.btn-secondary:hover:not(:disabled) {
  background-color: rgba(255, 255, 255, 0.15);
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary:active:not(:disabled),
.btn-secondary:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: none;
}
</style>
