<template>
  <div class="streams-container">
    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <div class="spinner"></div>
      <p>Loading streams...</p>
    </div>
    
    <!-- Empty State -->
    <div v-else-if="streams.length === 0" class="empty-state">
      <div class="empty-icon">
        <i class="fas fa-video-slash"></i>
      </div>
      <h3>No Streams Found</h3>
      <p>This streamer hasn't streamed yet or all streams have been deleted.</p>
      <button @click="handleBack" class="btn btn-primary">
        <i class="fas fa-arrow-left"></i>
        Back to Streamers
      </button>
    </div>
    
    <!-- Streams Content -->
    <div v-else class="streams-content">
      <!-- Header -->
      <div class="page-header">
        <div class="header-left">
          <button @click="handleBack" class="back-button">
            <i class="fas fa-arrow-left"></i>
            <span>Streamers</span>
          </button>
          <div class="header-info">
            <h1>{{ streamerName || 'Streams' }}</h1>
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
            <i class="fas fa-trash-alt"></i>
            <span>{{ deletingAllStreams ? 'Deleting...' : `Delete All (${streams.length})` }}</span>
          </button>
        </div>
      </div>
      
      <!-- Live Stream Banner -->
      <div v-if="liveStream" class="live-banner">
        <div class="live-content">
          <div class="live-indicator">
            <span class="live-dot"></span>
            <span class="live-text">LIVE NOW</span>
          </div>
          <div class="live-info">
            <h3>{{ liveStream.title || 'Untitled Stream' }}</h3>
            <p>{{ liveStream.category_name || 'No Category' }}</p>
          </div>
          <div class="recording-status">
            <span 
              class="recording-badge" 
              :class="isStreamBeingRecorded(liveStream) ? 'recording' : 'not-recording'"
            >
              <i :class="isStreamBeingRecorded(liveStream) ? 'fas fa-record-vinyl' : 'fas fa-stop-circle'"></i>
              {{ isStreamBeingRecorded(liveStream) ? 'RECORDING' : 'NOT RECORDING' }}
            </span>
          </div>
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
            'recording': isStreamBeingRecorded(stream),
            'expanded': expandedStreams[stream.id] 
          }"
        >
          <!-- Stream Header -->
          <div class="stream-header" @click="toggleStreamExpansion(stream.id)">
            <div class="stream-thumbnail">
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
              </div>
              <div v-else class="category-placeholder">
                <i class="fas fa-video"></i>
              </div>
            </div>
            
            <div class="stream-info">
              <div class="stream-badges">
                <span class="status-badge" :class="{ 'live': !stream.ended_at }">
                  {{ !stream.ended_at ? 'LIVE' : 'ENDED' }}
                </span>
                <span 
                  v-if="!stream.ended_at" 
                  class="recording-badge" 
                  :class="isStreamBeingRecorded(stream) ? 'recording' : 'not-recording'"
                >
                  {{ isStreamBeingRecorded(stream) ? 'REC' : 'OFF' }}
                </span>
              </div>
              
              <h3 class="stream-title">{{ stream.title || formatDate(stream.started_at) }}</h3>
              <div class="stream-meta">
                <span class="stream-date">{{ formatDate(stream.started_at) }}</span>
                <span v-if="stream.category_name" class="stream-category">{{ stream.category_name }}</span>
              </div>
            </div>
            
            <div class="expand-indicator">
              <i class="fas fa-chevron-down" :class="{ 'expanded': expandedStreams[stream.id] }"></i>
            </div>
          </div>
          
          <!-- Expanded Content -->
          <div v-if="expandedStreams[stream.id]" class="stream-details">
            <div class="stream-stats">
              <div class="stat-item">
                <span class="stat-label">Duration</span>
                <span class="stat-value">{{ calculateDuration(stream) }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">Viewers</span>
                <span class="stat-value">Unknown</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">Language</span>
                <span class="stat-value">{{ stream.language || 'Unknown' }}</span>
              </div>
            </div>
            
            <div class="stream-actions">
              <button 
                v-if="stream.ended_at"
                @click="watchVideo(stream)" 
                class="btn btn-primary"
                :disabled="!hasRecording(stream)"
              >
                <i class="fas fa-play"></i>
                Watch Video
              </button>
              
              <button 
                @click="confirmDeleteStream(stream)" 
                class="btn btn-danger" 
                :disabled="deletingStreamId === stream.id || (!stream.ended_at && isStreamBeingRecorded(stream))"
              >
                <i v-if="deletingStreamId === stream.id" class="fas fa-spinner fa-spin"></i>
                <i v-else class="fas fa-trash-alt"></i>
                Delete
              </button>
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
          <button @click="cancelDelete" class="modal-close">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="modal-body">
          <p>Are you sure you want to delete this stream?</p>
          <div v-if="streamToDelete" class="stream-preview">
            <p><strong>Date:</strong> {{ formatDate(streamToDelete.started_at) }}</p>
            <p><strong>Title:</strong> {{ streamToDelete.title || 'Untitled' }}</p>
            <p><strong>Category:</strong> {{ streamToDelete.category_name || 'No Category' }}</p>
          </div>
          <p class="warning">This action cannot be undone.</p>
        </div>
        <div class="modal-actions">
          <button @click="cancelDelete" class="btn btn-secondary">Cancel</button>
          <button @click="deleteStream" class="btn btn-danger" :disabled="deletingStreamId !== null">
            <i v-if="deletingStreamId !== null" class="fas fa-spinner fa-spin"></i>
            Delete Stream
          </button>
        </div>
      </div>
    </div>
    
    <!-- Delete All Confirmation Modal -->
    <div v-if="showDeleteAllModal" class="modal-overlay" @click.self="cancelDeleteAll">
      <div class="modal">
        <div class="modal-header">
          <h3>Delete All Streams</h3>
          <button @click="cancelDeleteAll" class="modal-close">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="modal-body">
          <p>Delete <strong>ALL {{ streams.length }} streams</strong> for this streamer?</p>
          <p class="warning">This will permanently delete all stream records and files. This action cannot be undone!</p>
        </div>
        <div class="modal-actions">
          <button @click="cancelDeleteAll" class="btn btn-secondary">Cancel</button>
          <button @click="deleteAllStreams" class="btn btn-danger" :disabled="deletingAllStreams">
            <i v-if="deletingAllStreams" class="fas fa-spinner fa-spin"></i>
            Delete All Streams
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStreams } from '@/composables/useStreams'
import { useRecordingSettings } from '@/composables/useRecordingSettings'
import { useWebSocket } from '@/composables/useWebSocket'
import { useCategoryImages } from '@/composables/useCategoryImages'

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

// WebSocket State for real-time updates
const localRecordingState = ref<Record<number, boolean>>({})

// Computed Properties
const liveStream = computed(() => {
  return streams.value.find(stream => !stream.ended_at)
})

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
    const recordingStreamId = Number(rec.streamer_id) // Use streamer_id as stream_id doesn't exist
    const recordingStreamerId = Number(rec.streamer_id)
    
    // Try to match by stream_id first, fall back to streamer_id for live streams
    return recordingStreamId === streamId || (recordingStreamerId === streamerId && !stream.ended_at)
  })
}

// WebSocket message handling
watch(messages, (newMessages) => {
  if (!newMessages || newMessages.length === 0) return
  
  const latestMessage = newMessages[newMessages.length - 1]
  
  if (latestMessage.type === 'active_recordings_update') {
    // Update local state from WebSocket
    const activeRecs = latestMessage.data || []
    
    // Clear previous state
    localRecordingState.value = {}
    
    // Set active recordings
    activeRecs.forEach((rec: any) => {
      const streamId = Number(rec.stream_id)
      if (streamId) {
        localRecordingState.value[streamId] = true
      }
    })
  } else if (latestMessage.type === 'recording_started') {
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
  if (!stream.ended_at) return 'Ongoing'
  
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
  if (stream.recordings && stream.recordings.length > 0) {
    const recording = stream.recordings[0]
    router.push(`/videos/${recording.id}`)
  }
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

// Lifecycle
onMounted(async () => {
  if (streamerId.value) {
    await fetchStreams(streamerId.value)
    await fetchActiveRecordings()
    
    // Preload category images
    const categories = [...new Set(streams.value.map(s => s.category_name).filter(Boolean))] as string[]
    await preloadCategoryImages(categories)
  }
})
</script>

<style scoped>
.streams-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
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
  border: 4px solid #f3f3f3;
  border-top: 4px solid #007bff;
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
}

.empty-icon {
  font-size: 4rem;
  color: #ccc;
  margin-bottom: 20px;
}

.empty-state h3 {
  margin: 0 0 10px 0;
  color: #666;
}

.empty-state p {
  color: #999;
  margin-bottom: 30px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 2px solid #eee;
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
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  color: #495057;
  text-decoration: none;
  transition: all 0.2s;
}

.back-button:hover {
  background: #e9ecef;
  border-color: #adb5bd;
}

.header-info h1 {
  margin: 0;
  font-size: 2rem;
  color: #333;
}

.stream-count {
  color: #666;
  font-size: 0.9rem;
}

.live-banner {
  background: linear-gradient(135deg, #ff4757, #ff3742);
  color: white;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 4px 15px rgba(255, 71, 87, 0.3);
}

.live-content {
  display: flex;
  align-items: center;
  gap: 20px;
}

.live-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.live-dot {
  width: 12px;
  height: 12px;
  background: white;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.live-text {
  font-weight: bold;
  font-size: 1.1rem;
}

.live-info {
  flex: 1;
}

.live-info h3 {
  margin: 0 0 5px 0;
  font-size: 1.3rem;
}

.live-info p {
  margin: 0;
  opacity: 0.9;
}

.recording-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: bold;
}

.recording-badge.recording {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.recording-badge.not-recording {
  background: rgba(0, 0, 0, 0.2);
  color: rgba(255, 255, 255, 0.8);
}

.stream-grid {
  display: grid;
  gap: 20px;
}

.stream-card {
  background: white;
  border: 1px solid #dee2e6;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.stream-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}

.stream-card.live {
  border-color: #ff4757;
  box-shadow: 0 2px 4px rgba(255, 71, 87, 0.2);
}

.stream-card.recording {
  border-color: #28a745;
  box-shadow: 0 2px 4px rgba(40, 167, 69, 0.2);
}

.stream-header {
  display: flex;
  align-items: center;
  padding: 20px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.stream-header:hover {
  background: #f8f9fa;
}

.stream-thumbnail {
  width: 60px;
  height: 60px;
  margin-right: 16px;
  flex-shrink: 0;
}

.category-image-container {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  overflow: hidden;
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
  background: #f8f9fa;
  border-radius: 8px;
  color: #6c757d;
  font-size: 1.5rem;
}

.stream-info {
  flex: 1;
  min-width: 0;
}

.stream-badges {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
}

.status-badge.live {
  background: #ff4757;
  color: white;
}

.status-badge:not(.live) {
  background: #6c757d;
  color: white;
}

.recording-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: bold;
}

.recording-badge.recording {
  background: #28a745;
  color: white;
}

.recording-badge.not-recording {
  background: #dc3545;
  color: white;
}

.stream-title {
  margin: 0 0 8px 0;
  font-size: 1.1rem;
  color: #333;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.stream-meta {
  display: flex;
  gap: 12px;
  font-size: 0.9rem;
  color: #666;
}

.expand-indicator {
  margin-left: 16px;
  color: #6c757d;
  transition: transform 0.3s;
}

.expand-indicator .fa-chevron-down.expanded {
  transform: rotate(180deg);
}

.stream-details {
  border-top: 1px solid var(--border-color, #2d2d35);
  padding: 20px;
  background: var(--background-card, #1f1f23);
}

.stream-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
}

.stat-label {
  display: block;
  font-size: 0.8rem;
  color: var(--text-secondary, #b1b1b9);
  margin-bottom: 4px;
}

.stat-value {
  display: block;
  font-weight: bold;
  color: var(--text-primary, #f1f1f3);
}

.stream-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
  text-decoration: none;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--primary-color, #42b883);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-color-dark, #2f9c6a);
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background: #545b62;
}

.btn-danger {
  background: var(--danger-color, #ff4757);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: var(--danger-color-dark, #c82333);
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
  background: white;
  border-radius: 12px;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow: auto;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #dee2e6;
}

.modal-header h3 {
  margin: 0;
  color: #333;
}

.modal-close {
  background: none;
  border: none;
  font-size: 1.2rem;
  color: #6c757d;
  cursor: pointer;
  padding: 4px;
}

.modal-body {
  padding: 20px;
}

.stream-preview {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 8px;
  margin: 15px 0;
}

.warning {
  color: #dc3545;
  font-weight: 500;
  margin-top: 15px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px;
  border-top: 1px solid #dee2e6;
}

/* Responsive Design */
@media (max-width: 768px) {
  .streams-container {
    padding: 15px;
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
  
  .live-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 15px;
  }
  
  .stream-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 15px;
    text-align: left;
  }
  
  .stream-thumbnail {
    margin-right: 0;
  }
  
  .stream-stats {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .stream-actions {
    width: 100%;
  }
  
  .btn {
    flex: 1;
    justify-content: center;
  }
}
</style>
