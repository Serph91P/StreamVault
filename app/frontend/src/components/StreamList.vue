<template>
  <div class="streams-container">
    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <div class="spinner"></div>
      <p>Loading streams...</p>
    </div>
    
    <!-- Empty State -->
    <div v-else-if="streams.length === 0" class="empty-state">
      <div class="empty-icon">🎬</div>
      <h3>No Streams Found</h3>
      <p>This streamer hasn't streamed yet or all streams have been deleted.</p>
      <button @click="handleBack" class="btn btn-primary">
        ← Back to Streamers
      </button>
    </div>
    
    <!-- Streams Content -->
    <div v-else class="streams-content">
      <!-- Header -->
      <div class="page-header">
        <div class="header-left">
          <button @click="handleBack" class="back-button">
            ← Streamers
          </button>
          <div class="header-info">
            <h1>{{ streamerName || 'Recent Streams' }}</h1>
            <p class="stream-count">{{ streams.length }} {{ streams.length === 1 ? 'stream' : 'streams' }}</p>
          </div>
        </div>
        
        <div class="header-actions">
          <button 
            v-if="streams.length > 1"
            @click="confirmDeleteAllStreams" 
            class="btn btn-danger"
            :disabled="deletingAllStreams"
          >
            🗑️ {{ deletingAllStreams ? 'Deleting...' : `Delete All (${streams.length})` }}
          </button>
        </div>
      </div>
      
      <!-- Stream Grid -->
      <div class="stream-grid">
        <div 
          v-for="stream in sortedStreams" 
          :key="stream.id"
          class="stream-card"
          :class="{ 
            'live': !stream.ended_at,
            'recording': isStreamBeingRecorded(stream)
          }"
        >
          <!-- Stream Thumbnail -->
          <div class="stream-thumbnail">
            <div class="thumbnail-container">
              <!-- Category/Game Image -->
              <div v-if="stream.category_name" class="category-image-container">
                <template v-if="getCategoryImageSrc(stream.category_name).startsWith('icon:')">
                  <div class="category-icon">
                    <i :class="`fas ${getCategoryImageSrc(stream.category_name).replace('icon:', '')}`"></i>
                  </div>
                </template>
                <template v-else>
                  <img 
                    :src="getCategoryImageSrc(stream.category_name)"
                    :alt="stream.category_name" 
                    @error="handleImageError($event, stream.category_name)"
                    loading="lazy"
                    class="category-image"
                  />
                </template>
                <div class="category-overlay">
                  <span class="category-label">{{ stream.category_name }}</span>
                </div>
              </div>
              <div v-else class="category-placeholder">
                <div class="placeholder-content">
                  <i class="fas fa-gamepad"></i>
                  <span>No Category</span>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Stream Info -->
          <div class="stream-info">
            <div class="stream-header">
              <h3 class="stream-title">{{ stream.title || 'Untitled Stream' }}</h3>
              <div class="stream-meta">
                <span class="stream-date">{{ formatDate(stream.started_at) }}</span>
                <span v-if="stream.category_name" class="stream-category">
                  <i class="fas fa-tag"></i> {{ stream.category_name }}
                </span>
                <span class="stream-duration">
                  <i class="fas fa-clock"></i> {{ calculateDuration(stream) }}
                </span>
              </div>
              
              <!-- Recording Status Indicator -->
              <div class="recording-status">
                <div v-if="!stream.ended_at" class="live-status">
                  <span class="status-indicator live">
                    <i class="fas fa-circle"></i> LIVE
                  </span>
                  <span 
                    v-if="isStreamBeingRecorded(stream)" 
                    class="status-indicator recording"
                  >
                    <i class="fas fa-record-vinyl recording-pulse"></i> RECORDING
                  </span>
                  <span 
                    v-else 
                    class="status-indicator not-recording"
                  >
                    <i class="fas fa-circle-o"></i> NOT RECORDING
                  </span>
                </div>
                <div v-else class="ended-status">
                  <span class="status-indicator ended">
                    <i class="fas fa-stop-circle"></i> ENDED
                  </span>
                  <span 
                    v-if="hasRecording(stream)" 
                    class="status-indicator has-recording"
                  >
                    <i class="fas fa-video"></i> VIDEO AVAILABLE
                  </span>
                  <span 
                    v-else 
                    class="status-indicator no-recording"
                  >
                    <i class="fas fa-video-slash"></i> NO VIDEO
                  </span>
                </div>
              </div>
            </div>
            
            <!-- Stream Actions -->
            <div class="stream-actions">
              <!-- Recording Actions (Primary Actions) -->
              <div class="recording-actions">
                <!-- Watch Video Button (for ended streams with recording) -->
                <button 
                  v-if="stream.ended_at && hasRecording(stream)"
                  @click="watchVideo(stream)" 
                  class="btn btn-primary action-btn"
                  title="Watch Video"
                >
                  <i class="fas fa-play"></i> Watch Video
                </button>
                
                <!-- Force Start Recording Button (for live streams without recording) -->
                <button 
                  v-if="!stream.ended_at && !isStreamBeingRecorded(stream)"
                  @click="forceStartRecording(stream.streamer_id)" 
                  class="btn btn-success action-btn"
                  :disabled="forceRecordingStreamerId === stream.streamer_id"
                  title="Force Start Recording"
                >
                  <span v-if="forceRecordingStreamerId === stream.streamer_id">
                    <i class="fas fa-spinner fa-spin"></i> Starting...
                  </span>
                  <span v-else>
                    <i class="fas fa-record-vinyl"></i> Force Recording
                  </span>
                </button>
                
                <!-- Stop Recording Button (for active recordings) -->
                <button 
                  v-if="!stream.ended_at && isStreamBeingRecorded(stream)"
                  @click="stopRecording(stream.streamer_id)" 
                  class="btn btn-warning action-btn"
                  :disabled="stoppingRecordingStreamerId === stream.streamer_id"
                  title="Stop Recording"
                >
                  <span v-if="stoppingRecordingStreamerId === stream.streamer_id">
                    <i class="fas fa-spinner fa-spin"></i> Stopping...
                  </span>
                  <span v-else>
                    <i class="fas fa-stop"></i> Stop Recording
                  </span>
                </button>
              </div>
              
              <!-- Secondary Actions -->
              <div class="secondary-actions">
                <!-- Details Toggle Button -->
                <button 
                  @click="toggleStreamExpansion(stream.id)"
                  class="btn btn-secondary action-btn"
                  title="Show/Hide Details"
                >
                  <i :class="expandedStreams[stream.id] ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
                  {{ expandedStreams[stream.id] ? 'Hide' : 'Show' }} Details
                </button>
                
                <!-- Delete Stream Button -->
                <button 
                  @click="confirmDeleteStream(stream)" 
                  class="btn btn-danger action-btn" 
                  :disabled="deletingStreamId === stream.id || (!stream.ended_at && isStreamBeingRecorded(stream))"
                  title="Delete Stream"
                >
                  <span v-if="deletingStreamId === stream.id">
                    <i class="fas fa-spinner fa-spin"></i>
                  </span>
                  <span v-else">
                    <i class="fas fa-trash"></i>
                  </span>
                </button>
              </div>
            </div>
          </div>
          
          <!-- Expanded Details -->
          <div v-if="expandedStreams[stream.id]" class="stream-details">
            <div class="details-grid">
              <div class="detail-item">
                <span class="detail-label">Duration:</span>
                <span class="detail-value">{{ calculateDuration(stream) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Started:</span>
                <span class="detail-value">{{ formatDate(stream.started_at) }}</span>
              </div>
              <div v-if="stream.ended_at" class="detail-item">
                <span class="detail-label">Ended:</span>
                <span class="detail-value">{{ formatDate(stream.ended_at) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Category:</span>
                <span class="detail-value">{{ stream.category_name || 'Unknown' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Language:</span>
                <span class="detail-value">{{ stream.language || 'Unknown' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Recording:</span>
                <span class="detail-value">
                  <span v-if="!stream.ended_at">
                    {{ isStreamBeingRecorded(stream) ? '🔴 Recording' : '⭕ Not Recording' }}
                  </span>
                  <span v-else>
                    {{ hasRecording(stream) ? '✅ Available' : '❌ Not Available' }}
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Delete Confirmation Modal -->
    <div v-if="showDeleteModal" class="modal-overlay" @click.self="cancelDelete">
      <div class="modal">
        <div class="modal-header">
          <h3>Delete Stream</h3>
          <button @click="cancelDelete" class="close-btn">×</button>
        </div>
        <div class="modal-body">
          <p>Are you sure you want to delete this stream?</p>
          <div v-if="streamToDelete" class="stream-preview">
            <p><strong>Title:</strong> {{ streamToDelete.title || 'Untitled' }}</p>
            <p><strong>Date:</strong> {{ formatDate(streamToDelete.started_at) }}</p>
            <p><strong>Category:</strong> {{ streamToDelete.category_name || 'Unknown' }}</p>
          </div>
          <p class="warning">⚠️ This action cannot be undone and will delete all associated files.</p>
        </div>
        <div class="modal-actions">
          <button @click="cancelDelete" class="btn btn-secondary">Cancel</button>
          <button @click="deleteStream" class="btn btn-danger" :disabled="deletingStreamId !== null">
            {{ deletingStreamId !== null ? '⏳ Deleting...' : '🗑️ Delete Stream' }}
          </button>
        </div>
      </div>
    </div>
    
    <!-- Delete All Confirmation Modal -->
    <div v-if="showDeleteAllModal" class="modal-overlay" @click.self="cancelDeleteAll">
      <div class="modal">
        <div class="modal-header">
          <h3>Delete All Streams</h3>
          <button @click="cancelDeleteAll" class="close-btn">×</button>
        </div>
        <div class="modal-body">
          <p>Delete <strong>ALL {{ streams.length }} streams</strong> for this streamer?</p>
          <p class="warning">⚠️ This will permanently delete all stream records and files. This action cannot be undone!</p>
        </div>
        <div class="modal-actions">
          <button @click="cancelDeleteAll" class="btn btn-secondary">Cancel</button>
          <button @click="deleteAllStreams" class="btn btn-danger" :disabled="deletingAllStreams">
            {{ deletingAllStreams ? '⏳ Deleting...' : '🗑️ Delete All Streams' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStreams } from '@/composables/useStreams'
import { useRecordingSettings } from '@/composables/useRecordingSettings'
import { useWebSocket } from '@/composables/useWebSocket'
import { useCategoryImages } from '@/composables/useCategoryImages'
import { recordingApi } from '@/services/api'

const route = useRoute()
const router = useRouter()
const streamerId = computed(() => route.params.id as string || route.query.id as string)
const streamerName = computed(() => route.query.name as string)

const { streams, isLoading, fetchStreams } = useStreams()
const { activeRecordings, fetchActiveRecordings } = useRecordingSettings()
const { messages } = useWebSocket()
const { getCategoryImage, preloadCategoryImages } = useCategoryImages()

// UI State
const expandedStreams = ref<Record<number, boolean>>({})
const deletingStreamId = ref<number | null>(null)
const deletingAllStreams = ref(false)
const showDeleteModal = ref(false)
const showDeleteAllModal = ref(false)
const streamToDelete = ref<any>(null)
const forceRecordingStreamerId = ref<number | null>(null)
const stoppingRecordingStreamerId = ref<number | null>(null)

// WebSocket State for real-time updates
const localRecordingState = ref<Record<number, boolean>>({})

// Computed Properties
const sortedStreams = computed(() => {
  return [...streams.value].sort((a, b) => {
    // Live streams first
    if (!a.ended_at && b.ended_at) return -1
    if (a.ended_at && !b.ended_at) return 1
    
    // Then by start date (newest first)
    const aDate = a.started_at ? new Date(a.started_at).getTime() : 0
    const bDate = b.started_at ? new Date(b.started_at).getTime() : 0
    return bDate - aDate
  })
})

// Check if a specific stream is being recorded
const isStreamBeingRecorded = (stream: any): boolean => {
  if (!stream || stream.ended_at) return false
  
  const streamId = Number(stream.id)
  const streamerId = Number(stream.streamer_id)
  
  // Check local WebSocket state first
  if (localRecordingState.value[streamId] !== undefined) {
    return localRecordingState.value[streamId]
  }
  
  // Check active recordings
  if (!activeRecordings.value || !Array.isArray(activeRecordings.value)) {
    return false
  }
  
  return activeRecordings.value.some(rec => {
    const recordingStreamId = Number(rec.streamer_id)
    return recordingStreamId === streamerId && !stream.ended_at
  })
}

// WebSocket message handling
watch(messages, (newMessages) => {
  if (!newMessages || newMessages.length === 0) return
  
  const latestMessage = newMessages[newMessages.length - 1]
  
  if (latestMessage.type === 'recording_started') {
    const streamId = Number(latestMessage.data?.stream_id)
    if (streamId) {
      localRecordingState.value[streamId] = true
    }
  } else if (latestMessage.type === 'recording_stopped') {
    const streamId = Number(latestMessage.data?.stream_id)
    if (streamId) {
      localRecordingState.value[streamId] = false
    }
  }
}, { deep: true })

// Utility Functions
const getCategoryImageSrc = (categoryName: string): string => {
  const imageUrl = getCategoryImage(categoryName)
  return imageUrl || 'icon:fa-gamepad'
}

const handleImageError = (event: Event, categoryName: string) => {
  const target = event.target as HTMLImageElement
  target.style.display = 'none'
  
  const wrapper = target.parentElement
  if (wrapper) {
    wrapper.innerHTML = '<div class="category-icon"><i class="fas fa-gamepad"></i></div>'
  }
}

const formatDate = (dateString: string | null): string => {
  if (!dateString) return 'Unknown'
  const date = new Date(dateString)
  return date.toLocaleDateString('de-DE', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const calculateDuration = (stream: any): string => {
  if (!stream.ended_at) return 'Live'
  
  const start = new Date(stream.started_at)
  const end = new Date(stream.ended_at)
  const durationMs = end.getTime() - start.getTime()
  const hours = Math.floor(durationMs / (1000 * 60 * 60))
  const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60))
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  } else {
    return `${minutes}m`
  }
}

const hasRecording = (stream: any): boolean => {
  // Check if stream has associated recording files
  return stream.recordings && stream.recordings.length > 0
}

// UI Actions
const toggleStreamExpansion = (streamId: number) => {
  expandedStreams.value[streamId] = !expandedStreams.value[streamId]
}

const handleBack = () => {
  router.push('/streamers')
}

const watchVideo = (stream: any) => {
  // Navigate to video player with stream details
  router.push({
    name: 'VideoPlayer',
    params: {
      streamerId: stream.streamer_id,
      streamId: stream.id
    },
    query: {
      title: stream.title,
      streamerName: streamerName.value
    }
  })
}

// Delete Functions
const confirmDeleteStream = (stream: any) => {
  streamToDelete.value = stream
  showDeleteModal.value = true
}

const confirmDeleteAllStreams = () => {
  showDeleteAllModal.value = true
}

const deleteStream = async () => {
  if (!streamToDelete.value) return
  
  try {
    deletingStreamId.value = streamToDelete.value.id
    
    const response = await fetch(`/api/streams/${streamToDelete.value.id}`, {
      method: 'DELETE',
      credentials: 'include'
    })
    
    if (!response.ok) {
      throw new Error(`Failed to delete stream: ${response.statusText}`)
    }
    
    // Remove from local state
    const index = streams.value.findIndex(s => s.id === streamToDelete.value.id)
    if (index > -1) {
      streams.value.splice(index, 1)
    }
    
    cancelDelete()
  } catch (error) {
    console.error('Error deleting stream:', error)
    alert('Failed to delete stream. Please try again.')
  } finally {
    deletingStreamId.value = null
  }
}

const deleteAllStreams = async () => {
  try {
    deletingAllStreams.value = true
    
    const response = await fetch(`/api/streamers/${streamerId.value}/streams`, {
      method: 'DELETE',
      credentials: 'include'
    })
    
    if (!response.ok) {
      throw new Error(`Failed to delete streams: ${response.statusText}`)
    }
    
    // Clear local state
    streams.value = []
    cancelDeleteAll()
    
    // Navigate back to streamers
    router.push('/streamers')
  } catch (error) {
    console.error('Error deleting all streams:', error)
    alert('Failed to delete all streams. Please try again.')
  } finally {
    deletingAllStreams.value = false
  }
}

const cancelDelete = () => {
  showDeleteModal.value = false
  streamToDelete.value = null
}

const cancelDeleteAll = () => {
  showDeleteAllModal.value = false
}

// Force Recording Method
const forceStartRecording = async (streamerId: number) => {
  try {
    forceRecordingStreamerId.value = streamerId
    
    const response = await recordingApi.forceStartRecording(streamerId)
    
    if (response.data.status === 'success') {
      // Update local recording state immediately
      const activeStream = streams.value.find(s => s.streamer_id === streamerId && !s.ended_at)
      if (activeStream) {
        localRecordingState.value[activeStream.id] = true
      }
    }
  } catch (error: any) {
    console.error('Error force starting recording:', error)
    
    let errorMessage = 'Failed to start recording.'
    if (error.response?.data?.detail) {
      errorMessage = error.response.data.detail
    } else if (error.message) {
      errorMessage = error.message
    }
    
    alert(errorMessage)
  } finally {
    forceRecordingStreamerId.value = null
  }
}

// Stop Recording Method
const stopRecording = async (streamerId: number) => {
  try {
    stoppingRecordingStreamerId.value = streamerId
    
    const response = await recordingApi.stopRecording(streamerId)
    
    if (response.data.status === 'success') {
      // Update local recording state immediately
      const activeStream = streams.value.find(s => s.streamer_id === streamerId && !s.ended_at)
      if (activeStream) {
        localRecordingState.value[activeStream.id] = false
      }
    }
  } catch (error: any) {
    console.error('Error stopping recording:', error)
    
    let errorMessage = 'Failed to stop recording.'
    if (error.response?.data?.detail) {
      errorMessage = error.response.data.detail
    } else if (error.message) {
      errorMessage = error.message
    }
    
    alert(errorMessage)
  } finally {
    stoppingRecordingStreamerId.value = null
  }
}

// Lifecycle
onMounted(async () => {
  if (streamerId.value) {
    await fetchStreams(streamerId.value)
    await fetchActiveRecordings()
    
    // Preload category images
    const categories = [...new Set(streams.value.map((s: any) => s.category_name).filter(Boolean))] as string[]
    await preloadCategoryImages(categories)
  }
})
</script>

<style scoped>
.streams-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  background: var(--background-primary);
  min-height: 100vh;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  gap: 16px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--border-color);
  border-top: 4px solid var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  background: var(--background-card);
  border-radius: var(--border-radius);
  border: 1px solid var(--border-color);
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 20px;
}

.empty-state h3 {
  margin: 0 0 10px 0;
  color: var(--text-primary);
}

.empty-state p {
  color: var(--text-secondary);
  margin-bottom: 30px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding: 20px;
  background: var(--background-card);
  border-radius: var(--border-radius);
  border: 1px solid var(--border-color);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.back-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  color: var(--text-primary);
  text-decoration: none;
  transition: all 0.2s;
  cursor: pointer;
}

.back-button:hover {
  background: var(--background-dark);
  border-color: var(--primary-color);
}

.header-info h1 {
  margin: 0;
  font-size: 2rem;
  color: var(--text-primary);
  font-weight: 600;
}

.stream-count {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin: 0;
}

.stream-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 20px;
}

.stream-card {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  overflow: hidden;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
}

.stream-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}

.stream-card.live {
  border-color: var(--danger-color);
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.2);
}

.stream-card.recording {
  border-color: var(--success-color);
  box-shadow: 0 2px 8px rgba(34, 197, 94, 0.2);
}

.stream-thumbnail {
  position: relative;
  height: 200px;
  overflow: hidden;
}

.thumbnail-container {
  position: relative;
  width: 100%;
  height: 100%;
}

.category-image-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.category-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.category-icon, .category-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--background-darker);
  color: var(--text-secondary);
  font-size: 3rem;
}

.status-badges {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  gap: 8px;
  flex-direction: column;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
  background: var(--background-darker);
  color: var(--text-secondary);
}

.status-badge.live {
  background: var(--danger-color);
  color: white;
}

.recording-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: bold;
  background: var(--success-color);
  color: white;
}

.stream-info {
  padding: 20px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.stream-title {
  margin: 0;
  font-size: 1.2rem;
  color: var(--text-primary);
  font-weight: 600;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.stream-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

/* Recording Status Indicators */
.recording-status {
  margin-top: 8px;
}

.live-status, .ended-status {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
}

.status-indicator.live {
  background: #ef4444;
  color: white;
}

.status-indicator.recording {
  background: #22c55e;
  color: white;
}

.status-indicator.not-recording {
  background: #6b7280;
  color: white;
}

.status-indicator.ended {
  background: #374151;
  color: #d1d5db;
}

.status-indicator.has-recording {
  background: #3b82f6;
  color: white;
}

.status-indicator.no-recording {
  background: #6b7280;
  color: #d1d5db;
}

.recording-pulse {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Improved Category Placeholder */
.category-placeholder .placeholder-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  font-size: 1rem;
  text-align: center;
}

.category-placeholder .placeholder-content i {
  font-size: 2rem;
  color: var(--text-secondary);
}

.category-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.8));
  color: white;
  padding: 8px 12px;
  font-size: 0.85rem;
  font-weight: 500;
}

/* Improved Button Styling */
.stream-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: auto;
  padding-top: 15px;
}

.recording-actions, .secondary-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.recording-actions {
  min-height: 40px;
}

.secondary-actions {
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
}

.action-btn {
  font-size: 0.85rem;
  padding: 10px 14px;
  border-radius: 6px;
  font-weight: 600;
  transition: all 0.2s ease;
  border: 2px solid transparent;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  white-space: nowrap;
}

.action-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.action-btn i {
  margin-right: 6px;
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.stream-actions .btn {
  font-size: 0.85rem;
  padding: 8px 12px;
  border-radius: 6px;
  font-weight: 600;
  transition: all 0.2s ease;
  border: 2px solid transparent;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.stream-actions .btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.stream-actions .btn-success {
  background: #22c55e;
  color: white;
  border-color: #16a34a;
}

.stream-actions .btn-success:hover:not(:disabled) {
  background: #16a34a;
  border-color: #15803d;
}

.stream-actions .btn-warning {
  background: #f59e0b;
  color: white;
  border-color: #d97706;
}

.stream-actions .btn-warning:hover:not(:disabled) {
  background: #d97706;
  border-color: #b45309;
}

.stream-actions .btn-info {
  background: #3b82f6;
  color: white;
  border-color: #2563eb;
}

.stream-actions .btn-info:hover:not(:disabled) {
  background: #2563eb;
  border-color: #1d4ed8;
}

.stream-actions .btn-primary {
  background: #6366f1;
  color: white;
  border-color: #4f46e5;
}

.stream-actions .btn-primary:hover:not(:disabled) {
  background: #4f46e5;
  border-color: #4338ca;
}

.stream-actions .btn-secondary {
  background: #6b7280;
  color: white;
  border-color: #4b5563;
}

.stream-actions .btn-secondary:hover:not(:disabled) {
  background: #4b5563;
  border-color: #374151;
}

.stream-actions .btn-danger {
  background: #ef4444;
  color: white;
  border-color: #dc2626;
}

.stream-actions .btn-danger:hover:not(:disabled) {
  background: #dc2626;
  border-color: #b91c1c;
}

.stream-actions .btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.stream-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.stream-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stream-actions .btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: var(--border-radius);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  text-decoration: none;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-color-hover);
}

.btn-secondary {
  background: var(--background-darker);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--background-dark);
  border-color: var(--primary-color);
}

.btn-danger {
  background: var(--danger-color);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: var(--danger-color-hover);
}

.stream-details {
  border-top: 1px solid var(--border-color);
  padding: 20px;
  background: var(--background-darker);
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
}

.detail-label {
  font-weight: 500;
  color: var(--text-secondary);
}

.detail-value {
  color: var(--text-primary);
  font-weight: 600;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: var(--border-radius);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  text-decoration: none;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-color-hover);
}

.btn-secondary {
  background: var(--background-darker);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--background-dark);
  border-color: var(--primary-color);
}

.btn-danger {
  background: var(--danger-color);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: var(--danger-color-hover);
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow: auto;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  color: var(--text-primary);
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  line-height: 1;
}

.close-btn:hover {
  color: var(--text-primary);
}

.modal-body {
  padding: 20px;
  color: var(--text-primary);
}

.stream-preview {
  background: var(--background-darker);
  padding: 15px;
  border-radius: var(--border-radius);
  margin: 15px 0;
}

.warning {
  color: var(--danger-color);
  font-weight: 500;
  margin-top: 15px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px;
  border-top: 1px solid var(--border-color);
}

/* Responsive Design */
@media (max-width: 768px) {
  .streams-container {
    padding: 15px;
  }
  
  .stream-grid {
    grid-template-columns: 1fr;
    gap: 15px;
  }
  
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 15px;
  }
  
  .header-left {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  
  .header-info h1 {
    font-size: 1.5rem;
  }
  
  .stream-actions {
    gap: 6px;
    padding-top: 10px;
  }
  
  .stream-actions .btn {
    font-size: 0.8rem;
    padding: 6px 10px;
    min-width: 80px;
  }
  
  .details-grid {
    grid-template-columns: 1fr;
  }
  
  .stream-card {
    border-radius: 8px;
  }
  
  .stream-info {
    padding: 15px;
  }
}
</style>
