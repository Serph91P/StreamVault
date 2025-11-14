<template>
  <div class="streamer-detail-view">
    <!-- Back Button -->
    <router-link to="/streamers" class="back-button" v-ripple>
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M19 12H5M12 19l-7-7 7-7" />
      </svg>
      Back
    </router-link>

    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <LoadingSkeleton type="streamer" />
      <div class="stats-grid">
        <LoadingSkeleton v-for="i in 3" :key="i" type="status" />
      </div>
    </div>

    <!-- Content -->
    <div v-else-if="streamer">
      <!-- Profile Banner -->
      <div class="profile-banner" :style="bannerStyle">
        <div class="banner-overlay"></div>
        <div class="profile-content">
          <!-- Avatar with Live Status -->
          <div class="profile-avatar" :class="{ 'is-live': streamer.is_live }">
            <img
              v-if="streamer.profile_image_url"
              :src="streamer.profile_image_url"
              :alt="streamer.name"
            />
            <div v-else class="avatar-placeholder">
              <svg class="icon-user">
                <use href="#icon-user" />
              </svg>
            </div>
            <div v-if="streamer.is_live" class="live-badge">
              <span class="live-pulse"></span>
              <span class="live-text">LIVE</span>
            </div>
          </div>

          <!-- Profile Info -->
          <div class="profile-info">
            <h1 class="streamer-name">{{ streamer.name }}</h1>
            <p v-if="streamer.display_name" class="streamer-username">
              @{{ streamer.display_name }}
            </p>
            <p v-if="streamer.description" class="streamer-description">
              {{ streamer.description }}
            </p>
          </div>

          <!-- Action Buttons -->
          <div class="profile-actions">
            <button
              @click="forceStartRecording(Number(streamerId))"
              class="btn-action btn-primary"
              :disabled="forceRecordingStreamerId === Number(streamerId)"
              v-ripple
            >
              <svg v-if="forceRecordingStreamerId !== Number(streamerId)" class="icon">
                <use href="#icon-video" />
              </svg>
              <span v-if="forceRecordingStreamerId === Number(streamerId)">Recording...</span>
              <span v-else>Record Now</span>
            </button>
            <button @click="confirmDeleteAll" class="btn-action btn-danger" v-ripple>
              <svg class="icon">
                <use href="#icon-trash" />
              </svg>
              Delete All
            </button>
            <button @click="openSettings" class="btn-action btn-secondary btn-icon-mobile" v-ripple>
              <svg class="icon">
                <use href="#icon-settings" />
              </svg>
              <span class="button-text">Settings</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Stats Section -->
      <div class="stats-section">
        <StatusCard
          :value="streamCount"
          label="Total Streams"
          icon="film"
          type="primary"
        />
        <StatusCard
          :value="recordedStreamsCount"
          label="Recorded"
          icon="check-circle"
          type="success"
        />
        <StatusCard
          :value="averageDuration"
          label="Avg Duration"
          icon="clock"
          type="info"
        />
      </div>

      <!-- Stream History Section -->
      <div class="history-section">
        <div class="history-header">
          <h2 class="section-title">Stream History</h2>

          <!-- Sort Dropdown -->
          <div class="view-controls">
            <button class="filter-button" @click="() => {}" v-ripple>
              <select v-model="sortBy" class="sort-select">
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
                <option value="duration-desc">Longest Duration</option>
                <option value="duration-asc">Shortest Duration</option>
              </select>
            </button>
          </div>
        </div>

        <!-- Streams Loading -->
        <div v-if="isLoadingStreams" class="streams-container">
          <LoadingSkeleton
            v-for="i in 6"
            :key="i"
            type="list-item"
          />
        </div>

        <!-- Streams Empty State -->
        <EmptyState
          v-else-if="sortedStreams.length === 0"
          title="No Streams Yet"
          description="Start recording this streamer to see their streams here."
          icon="video"
          action-label="Record Now"
          action-icon="video"
          @action="forceStartRecording(Number(streamerId))"
        />

        <!-- Streams List -->
        <div v-else class="streams-container">
          <StreamCard
            v-for="stream in sortedStreams"
            :key="stream.id"
            :stream="stream"
            @watch-live="handleWatchLive"
            @force-record="handleForceRecord"
            @watch="handleWatchRecording"
            @delete="handleDeleteStream"
          />
        </div>
      </div>
    </div>

    <!-- Error State -->
    <EmptyState
      v-else
      title="Streamer Not Found"
      description="The streamer you're looking for doesn't exist."
      icon="alert-circle"
      action-label="Back to Streamers"
      @action="$router.push('/streamers')"
    />

    <!-- Delete Confirmation Modal -->
    <Teleport to="body">
      <div v-if="showConfirm" class="modal-overlay" @click.self="showConfirm = false">
        <div class="modal">
          <div class="modal-header">
            <h3>Delete All Streams</h3>
            <button class="close-btn" @click="showConfirm = false" v-ripple>×</button>
          </div>
          <div class="modal-body">
            <p>Are you sure you want to delete all streams for this streamer?</p>
            <p class="warning">
              <svg class="icon-warning">
                <use href="#icon-alert-triangle" />
              </svg>
              Active recordings will be skipped to avoid data loss.
            </p>
          </div>
          <div class="modal-actions">
            <button class="btn-secondary" @click="showConfirm = false" v-ripple>
              Cancel
            </button>
            <button
              class="btn-danger"
              :disabled="deletingAll"
              @click="deleteAll"
              v-ripple
            >
              {{ deletingAll ? 'Deleting...' : 'Delete All' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Settings Modal -->
    <Teleport to="body">
      <div v-if="showSettings" class="modal-overlay" @click.self="closeSettings">
        <div class="modal settings-modal">
          <div class="modal-header">
            <h3>Settings for {{ streamer?.name || 'Streamer' }}</h3>
            <button class="close-btn" @click="closeSettings" v-ripple>×</button>
          </div>
          <div class="modal-body">
            <!-- Recording Quality Override -->
            <div class="setting-group">
              <label class="setting-label">Recording Quality</label>
              <select v-model="streamerSettings.quality" class="setting-input">
                <option value="">Use Global Setting</option>
                <option value="best">Best Available</option>
                <option value="1080p60">1080p60</option>
                <option value="720p60">720p60</option>
                <option value="720p">720p</option>
                <option value="480p">480p</option>
              </select>
              <p class="setting-hint">Override global recording quality for this streamer</p>
            </div>

            <!-- Custom Filename Template -->
            <div class="setting-group">
              <label class="setting-label">Custom Filename Template</label>
              <input 
                v-model="streamerSettings.filenameTemplate" 
                type="text"
                class="setting-input"
                placeholder="Leave empty to use global template"
              />
              <p class="setting-hint">
                Available variables: {streamer}, {title}, {game}, {date}, {time}
              </p>
            </div>

            <!-- Auto-Record Toggle -->
            <div class="setting-group">
              <label class="setting-checkbox">
                <input type="checkbox" v-model="streamerSettings.autoRecord" />
                <span>Auto-record when this streamer goes live</span>
              </label>
            </div>

            <!-- Notification Preferences -->
            <div class="setting-group">
              <label class="setting-label">Notifications</label>
              <label class="setting-checkbox">
                <input type="checkbox" v-model="streamerSettings.notifyOnline" />
                <span>Notify when goes online</span>
              </label>
              <label class="setting-checkbox">
                <input type="checkbox" v-model="streamerSettings.notifyOffline" />
                <span>Notify when goes offline</span>
              </label>
            </div>
          </div>
          <div class="modal-actions">
            <button class="btn-secondary" @click="closeSettings" v-ripple>
              Cancel
            </button>
            <button
              class="btn-primary"
              :disabled="savingSettings"
              @click="saveSettings"
              v-ripple
            >
              {{ savingSettings ? 'Saving...' : 'Save Settings' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { streamersApi } from '@/services/api'
import { useForceRecording } from '@/composables/useForceRecording'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusCard from '@/components/cards/StatusCard.vue'
import StreamCard from '@/components/cards/StreamCard.vue'

const route = useRoute()
const router = useRouter()

// URL params
const streamerId = computed(() => route.params.id as string)

// Loading states
const isLoading = ref(true)
const isLoadingStreams = ref(true)

// Data
const streamer = ref<any>(null)
const streams = ref<any[]>([])

// View controls
const sortBy = ref('newest')

// Delete flow
const showConfirm = ref(false)
const deletingAll = ref(false)

// Force recording
const { forceRecordingStreamerId, forceStartRecording } = useForceRecording()

// Settings modal
const showSettings = ref(false)
const savingSettings = ref(false)
const streamerSettings = ref({
  quality: '',
  filenameTemplate: '',
  autoRecord: true,
  notifyOnline: true,
  notifyOffline: true
})

const openSettings = () => {
  // Load current settings (TODO: fetch from API when backend is ready)
  showSettings.value = true
}

const closeSettings = () => {
  showSettings.value = false
}

const saveSettings = async () => {
  savingSettings.value = true
  
  try {
    // TODO: Implement API endpoint when backend is ready
    // await fetch(`/api/streamers/${streamerId.value}/settings`, {
    //   method: 'PUT',
    //   credentials: 'include',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify(streamerSettings.value)
    // })
    
    // Simulate API call for now
    await new Promise(resolve => setTimeout(resolve, 500))
    
    closeSettings()
  } catch (error) {
    console.error('Failed to save settings:', error)
  } finally {
    savingSettings.value = false
  }
}

// Banner gradient style
const bannerStyle = computed(() => {
  if (!streamer.value) return {}

  // Create gradient from primary/accent colors
  return {
    backgroundImage: streamer.value.is_live
      ? 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'
      : 'linear-gradient(135deg, var(--primary-color) 0%, var(--accent-color) 100%)'
  }
})

// Stats computed
const streamCount = computed(() => streams.value.length)

const recordedStreamsCount = computed(() => {
  return streams.value.filter(s => s.recording_path).length
})

const averageDuration = computed(() => {
  if (streams.value.length === 0) return '0m'

  const totalSeconds = streams.value.reduce((sum, s) => {
    if (!s.started_at) return sum
    const start = new Date(s.started_at).getTime()
    const end = s.ended_at ? new Date(s.ended_at).getTime() : new Date().getTime()
    return sum + Math.floor((end - start) / 1000)
  }, 0)

  const avgSeconds = totalSeconds / streams.value.length
  const hours = Math.floor(avgSeconds / 3600)
  const minutes = Math.floor((avgSeconds % 3600) / 60)

  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
})

// Sorted streams
const sortedStreams = computed(() => {
  const sorted = [...streams.value]

  switch (sortBy.value) {
    case 'newest':
      return sorted.sort((a, b) => {
        const dateA = new Date(a.started_at || 0).getTime()
        const dateB = new Date(b.started_at || 0).getTime()
        return dateB - dateA
      })
    case 'oldest':
      return sorted.sort((a, b) => {
        const dateA = new Date(a.started_at || 0).getTime()
        const dateB = new Date(b.started_at || 0).getTime()
        return dateA - dateB
      })
    case 'duration-desc':
      return sorted.sort((a, b) => {
        const aDur = a.ended_at ? new Date(a.ended_at).getTime() - new Date(a.started_at).getTime() : 0
        const bDur = b.ended_at ? new Date(b.ended_at).getTime() - new Date(b.started_at).getTime() : 0
        return bDur - aDur
      })
    case 'duration-asc':
      return sorted.sort((a, b) => {
        const aDur = a.ended_at ? new Date(a.ended_at).getTime() - new Date(a.started_at).getTime() : 0
        const bDur = b.ended_at ? new Date(b.ended_at).getTime() - new Date(b.started_at).getTime() : 0
        return aDur - bDur
      })
    default:
      return sorted
  }
})

// Fetch streamer data
async function fetchStreamer() {
  isLoading.value = true
  try {
    console.log('[DEBUG] Fetching streamer with ID:', streamerId.value, 'Type:', typeof streamerId.value)
    const response = await streamersApi.get(Number(streamerId.value))
    console.log('[DEBUG] Fetched streamer successfully:', response)
    streamer.value = response
  } catch (error: any) {
    console.error('[ERROR] Failed to fetch streamer:', error)
    console.error('[ERROR] Error details:', {
      message: error.message,
      status: error.response?.status,
      data: error.response?.data
    })
    streamer.value = null
  } finally {
    isLoading.value = false
  }
}

// Fetch streams
async function fetchStreams() {
  isLoadingStreams.value = true
  try {
    console.log('[StreamerDetailView] Fetching streams for streamer:', streamerId.value)
    const response = await streamersApi.getStreams(Number(streamerId.value))
    console.log('[StreamerDetailView] Streams response:', response)
    
    streams.value = response?.streams || []
    console.log('[StreamerDetailView] Loaded streams count:', streams.value.length)
    
    if (streams.value.length > 0) {
      console.log('[StreamerDetailView] Sample stream:', streams.value[0])
    }
  } catch (error: any) {
    console.error('[StreamerDetailView] Failed to fetch streams:', error)
    console.error('[StreamerDetailView] Error details:', {
      message: error.message,
      status: error.response?.status,
      data: error.response?.data
    })
    streams.value = []
  } finally {
    isLoadingStreams.value = false
  }
}

// Actions
function confirmDeleteAll() {
  showConfirm.value = true
}

async function deleteAll() {
  if (!streamerId.value) return

  try {
    deletingAll.value = true
    await streamersApi.deleteAllStreams(Number(streamerId.value), { excludeActive: true })
    showConfirm.value = false
    router.push('/streamers')
  } catch (error) {
    console.error('Failed to delete all streams:', error)
  } finally {
    deletingAll.value = false
  }
}

function handleWatchLive(stream: any) {
  if (!streamer.value) return
  window.open(`https://twitch.tv/${streamer.value.username}`, '_blank', 'noopener,noreferrer')
}

function handleForceRecord(stream: any) {
  forceStartRecording(Number(streamerId.value))
}

async function handleWatchRecording(stream: any) {
  if (!stream.recording_path) {
    console.warn('[StreamerDetailView] No recording path for stream:', stream.id)
    return
  }
  
  try {
    // Check if recording exists via API
    const response = await fetch(`/api/stream/${stream.id}/has-recording`, {
      credentials: 'include'
    })
    const data = await response.json()
    
    if (data.has_recording) {
      // Navigate to video player (we'll use stream ID as video ID for now)
      // TODO: Backend should return recording.id from the endpoint
      router.push(`/videos/${stream.id}`)
    } else {
      console.warn('[StreamerDetailView] Recording not found on disk for stream:', stream.id)
    }
  } catch (error) {
    console.error('[StreamerDetailView] Failed to check recording:', error)
  }
}

function handleDeleteStream(stream: any) {
  // TODO: Implement stream deletion
  console.log('[StreamerDetailView] Delete stream:', stream.id)
}

// Initialize
onMounted(async () => {
  await Promise.all([
    fetchStreamer(),
    fetchStreams()
  ])
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;
.streamer-detail-view {
  padding: var(--spacing-4);
  max-width: 1400px;
  margin: 0 auto;
  min-height: 100vh;
}

// Back Button
.back-button {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  margin-bottom: var(--spacing-6);
  background: var(--background-card);
  color: var(--text-primary);
  text-decoration: none;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  font-weight: v.$font-medium;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 20px;
    height: 20px;
    stroke: currentColor;
    fill: none;
  }

  &:hover {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: white;
    transform: translateX(-4px);
  }
}

// Profile Banner
.profile-banner {
  position: relative;
  border-radius: var(--radius-2xl);
  overflow: hidden;
  margin-bottom: var(--spacing-8);
  min-height: 300px;
  animation: fade-in v.$duration-500 v.$ease-out;
}

.banner-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    rgba(0, 0, 0, 0.3) 0%,
    rgba(0, 0, 0, 0.7) 100%
  );
}

.profile-content {
  position: relative;
  z-index: 2;
  padding: var(--spacing-8);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--spacing-6);
}

.profile-avatar {
  position: relative;
  width: 128px;
  height: 128px;
  border-radius: var(--radius-2xl);
  overflow: hidden;
  border: 4px solid rgba(255, 255, 255, 0.2);
  background: var(--background-darker);
  animation: bounce-in v.$duration-500 v.$ease-bounce;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .avatar-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--background-darker);

    .icon-user {
      width: 64px;
      height: 64px;
      stroke: var(--text-secondary);
      fill: none;
    }
  }

  &.is-live {
    border-color: var(--danger-color);
    box-shadow: 0 0 0 4px rgba(var(--danger-500-rgb), 0.3);
    animation: pulse-live 2s ease-in-out infinite;
  }
}

.live-badge {
  position: absolute;
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-1) var(--spacing-3);
  background: var(--danger-color);
  color: white;
  font-size: var(--text-xs);
  font-weight: v.$font-bold;
  border-radius: var(--radius-full);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.live-pulse {
  display: inline-block;
  width: 8px;
  height: 8px;
  background: white;
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse-live {
  0%, 100% {
    box-shadow: 0 0 0 4px rgba(var(--danger-500-rgb), 0.3);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(var(--danger-500-rgb), 0.1);
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.profile-info {
  flex: 1;
  max-width: 600px;
}

.streamer-name {
  font-size: var(--text-4xl);
  font-weight: v.$font-bold;
  color: white;
  margin: 0 0 var(--spacing-2) 0;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
}

.streamer-username {
  font-size: var(--text-lg);
  color: rgba(255, 255, 255, 0.8);
  margin: 0 0 var(--spacing-3) 0;
}

.streamer-description {
  font-size: var(--text-base);
  color: rgba(255, 255, 255, 0.9);
  line-height: v.$leading-relaxed;
  margin: 0;
}

.profile-actions {
  display: flex;
  gap: var(--spacing-3);
  flex-wrap: wrap;
  justify-content: center;
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-5);
  border-radius: var(--radius-lg);
  font-size: var(--text-base);
  font-weight: v.$font-semibold;
  border: none;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 20px;
    height: 20px;
    stroke: currentColor;
    fill: none;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  &.btn-primary {
    background: var(--primary-color);
    color: white;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);

    &:hover:not(:disabled) {
      background: var(--primary-600);
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    }
  }

  &.btn-danger {
    background: var(--danger-color);
    color: white;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);

    &:hover:not(:disabled) {
      background: var(--danger-600);
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    }
  }

  &.btn-secondary {
    background: rgba(255, 255, 255, 0.95);
    color: var(--text-primary);
    border: 1px solid rgba(255, 255, 255, 0.3);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);

    &:hover:not(:disabled) {
      background: rgba(255, 255, 255, 1);
      border-color: var(--primary-color);
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
  }
}

// Stats Section
.stats-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: var(--spacing-5);
  margin-bottom: var(--spacing-8);
  animation: fade-in v.$duration-500 v.$ease-out 200ms backwards;
}

// History Section
.history-section {
  animation: fade-in v.$duration-500 v.$ease-out 400ms backwards;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-6);
  gap: var(--spacing-4);
  flex-wrap: wrap;
}

.section-title {
  font-size: var(--text-2xl);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  margin: 0;
}

.view-controls {
  display: flex;
  gap: var(--spacing-3);
  align-items: center;
}

.sort-select {
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &:hover {
    border-color: var(--primary-color);
  }

  &:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

// Streams Container
.streams-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

// Modal
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: var(--spacing-4);
  animation: fade-in v.$duration-200 v.$ease-out;
}

.modal {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-2xl);
  max-width: 500px;
  width: 100%;
  animation: slide-in-up v.$duration-300 v.$ease-out;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-6);
  border-bottom: 1px solid var(--border-color);

  h3 {
    font-size: var(--text-xl);
    font-weight: v.$font-bold;
    color: var(--text-primary);
    margin: 0;
  }
}

.close-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  font-size: 28px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &:hover {
    background: rgba(var(--danger-500-rgb), 0.1);
    color: var(--danger-color);
  }
}

.modal-body {
  padding: var(--spacing-6);

  p {
    margin: 0 0 var(--spacing-4) 0;
    color: var(--text-primary);
    line-height: v.$leading-relaxed;
  }

  .warning {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
    padding: var(--spacing-3);
    background: rgba(var(--warning-500-rgb), 0.1);
    border: 1px solid var(--warning-color);
    border-radius: var(--radius-md);
    color: var(--warning-color);
    font-size: var(--text-sm);

    .icon-warning {
      width: 20px;
      height: 20px;
      stroke: currentColor;
      fill: none;
      flex-shrink: 0;
    }
  }
}

.modal-actions {
  display: flex;
  gap: var(--spacing-3);
  padding: var(--spacing-6);
  border-top: 1px solid var(--border-color);
  justify-content: flex-end;

  button {
    padding: var(--spacing-3) var(--spacing-5);
    border-radius: var(--radius-lg);
    font-weight: v.$font-semibold;
    border: none;
    cursor: pointer;
    transition: all v.$duration-200 v.$ease-out;

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }

  .btn-secondary {
    background: var(--background-darker);
    color: var(--text-primary);
    border: 1px solid var(--border-color);

    &:hover:not(:disabled) {
      background: var(--background-dark);
    }
  }

  .btn-danger {
    background: var(--danger-color);
    color: white;

    &:hover:not(:disabled) {
      background: var(--danger-600);
      box-shadow: var(--shadow-md);
    }
  }
}

// Settings Modal
.settings-modal {
  max-width: 600px;

  .modal-body {
    max-height: 60vh;
    overflow-y: auto;
  }
}

.setting-group {
  margin-bottom: var(--spacing-6);

  &:last-child {
    margin-bottom: 0;
  }
}

.setting-label {
  display: block;
  margin-bottom: var(--spacing-2);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.setting-input {
  width: 100%;
  padding: var(--spacing-3);
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--text-base);
  transition: all v.$duration-200 v.$ease-out;

  &:focus {
    outline: none;
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(var(--primary-500-rgb), 0.1);
  }

  &::placeholder {
    color: var(--text-tertiary);
  }
}

.setting-hint {
  margin-top: var(--spacing-2);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  line-height: v.$leading-relaxed;
}

.setting-checkbox {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  margin-bottom: var(--spacing-2);
  cursor: pointer;
  user-select: none;

  input[type="checkbox"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
    accent-color: var(--primary-color);
  }

  span {
    color: var(--text-primary);
    font-size: var(--text-sm);
  }

  &:hover {
    span {
      color: var(--primary-color);
    }
  }
}

@include m.respond-below('lg') {  // < 1024px
  .profile-content {
    padding: var(--spacing-6);
  }

  .streamer-name {
    font-size: var(--text-3xl);
  }

  .stats-section {
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  }
}

@include m.respond-below('sm') {  // < 640px
  .profile-content {
    padding: var(--spacing-4);
  }

  .profile-avatar {
    width: 96px;
    height: 96px;

    .icon-user {
      width: 48px;
      height: 48px;
    }
  }

  .streamer-name {
    font-size: var(--text-2xl);
  }

  .profile-actions {
    width: 100%;

    .btn-action {
      flex: 1;
      justify-content: center;
      min-height: 44px;  // Touch-friendly
    }
  }

  .history-header {
    flex-direction: column;
    align-items: stretch;
    gap: var(--spacing-3);
  }

  .view-controls {
    justify-content: space-between;
    gap: var(--spacing-2);
  }
  
  .view-toggle {
    flex: none;  // Fixed width
    
    .toggle-btn {
      min-width: 44px;  // Touch-friendly
      min-height: 44px;
      padding: var(--spacing-2);
      
      .icon {
        width: 22px;
        height: 22px;
      }
    }
  }
  
  .sort-select {
    flex: 1;  // Fill remaining space
    min-height: 44px;  // Touch-friendly
    font-size: 16px;  // Prevent iOS zoom
    padding: var(--spacing-3);
  }

  .videos-container.view-grid {
    grid-template-columns: 1fr;
  }
  
  .stats-section {
    grid-template-columns: 1fr;  // Stack stats on mobile
    gap: var(--spacing-3);
  }
}

// Mobile icon-only buttons (< 375px - very small phones)
@include m.respond-below('xs') {  // < 375px
  .btn-icon-mobile {
    .button-text {
      display: none; // Hide text on mobile
    }

    // Keep icon visible and centered
    .icon {
      margin: 0;
    }

    // Smaller padding since no text
    padding: var(--spacing-3);
    min-width: 44px;
    justify-content: center;
  }

  .profile-actions {
    gap: var(--spacing-2);
  }
  
  .modal-actions {
    flex-direction: column;  // Stack buttons vertically
    
    button {
      width: 100%;
      min-height: 44px;  // Touch-friendly
      justify-content: center;
    }
  }
}

// Animations
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes bounce-in {
  0% {
    opacity: 0;
    transform: scale(0.3);
  }
  50% {
    transform: scale(1.05);
  }
  70% {
    transform: scale(0.9);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes slide-in-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
