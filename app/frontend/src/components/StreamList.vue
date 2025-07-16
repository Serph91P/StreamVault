<template>
  <div class="streams-container">
    <div v-if="isLoading" class="loading-container">
      <div class="spinner"></div>
      <p>Loading streams...</p>
    </div>
    <div v-else-if="streams.length === 0" class="no-data-container">
      <p>No streams found for this streamer.</p>
      <div class="action-buttons">
        <button @click="handleBack" class="btn btn-primary back-btn">
          <i class="fas fa-arrow-left"></i>
          <span>Back to streamers</span>
        </button>
        
        <button @click="forceOfflineRecording(Number(streamerId))" class="btn btn-warning">
          <i class="fas fa-record-vinyl"></i>
          <span>Force Recording (Offline Mode)</span>
        </button>
      </div>
    </div>
    <div v-else>
      <!-- Header with prominent actions -->
      <div class="streams-header">
        <div class="header-info">
          <h2>Streams Overview</h2>
          <div class="streams-summary">
            <span class="stream-count">{{ streams.length }} streams found</span>
            <span v-if="hasLiveStreams" class="live-indicator">• Live stream active</span>
          </div>
        </div>
        
        <div class="header-actions">
          <button 
            @click="handleBack" 
            class="btn btn-secondary back-btn"
          >
            <i class="fas fa-arrow-left"></i>
            <span>Back to Streamers</span>
          </button>
          
          <button 
            v-if="!hasLiveStreams" 
            @click="forceOfflineRecording(Number(streamerId))" 
            class="btn btn-warning"
            :disabled="isStartingOfflineRecording"
          >
            <i class="fas fa-record-vinyl"></i>
            <span>{{ isStartingOfflineRecording ? 'Starting Recording...' : 'Force Recording (Offline)' }}</span>
          </button>
          
          <button 
            @click="confirmDeleteAllStreams" 
            class="btn btn-danger delete-all-btn"
            :disabled="deletingAllStreams || streams.length === 0"
            :title="`Delete all ${streams.length} streams`"
          >
            <i class="fas fa-trash-alt"></i>
            <span>{{ deletingAllStreams ? 'Deleting All...' : `Delete All (${streams.length})` }}</span>
          </button>
        </div>
      </div>
      
      <div class="stream-list">
        <div v-for="stream in streams" 
             :key="stream.id"
             class="stream-card"
             :class="{ 'expanded': expandedStreams[stream.id] }">
          
          <!-- Compact Header -->
          <div class="stream-compact-header" @click="toggleStreamExpansion(stream.id)">
            <!-- Left: Category Image -->
            <div class="stream-thumbnail">
              <div v-if="stream.category_name" class="category-image-container">
                <template v-if="getCategoryImageSrc(stream.category_name).startsWith('icon:')">
                  <!-- Icon fallback -->
                  <div class="category-icon-wrapper">
                    <i :class="`fas ${getCategoryImageSrc(stream.category_name).replace('icon:', '')}`"></i>
                  </div>
                </template>
                <template v-else>
                  <!-- Real image -->
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
            
            <!-- Center: Stream Info -->
            <div class="stream-info">
              <div class="stream-badges">
                <span class="status-badge" :class="{ 'live': !stream.ended_at }">
                  {{ !stream.ended_at ? 'LIVE' : 'ENDED' }}
                </span>
                <span 
                  v-if="!stream.ended_at" 
                  class="recording-badge" 
                  :class="isStreamRecording(Number(streamerId)) ? 'recording' : 'not-recording'"
                >
                  {{ isStreamRecording(Number(streamerId)) ? 'REC' : 'OFF' }}
                </span>
              </div>
              
              <h3 class="stream-title">{{ stream.title || formatDate(stream.started_at) }}</h3>
              
              <div class="stream-meta">
                <div class="meta-item duration-item">
                  <i class="fas fa-clock"></i>
                  <span>{{ calculateDuration(stream.started_at, stream.ended_at) }}</span>
                </div>
                <div v-if="stream.category_name" class="meta-item category-item">
                  <i class="fas fa-gamepad"></i>
                  <span>{{ stream.category_name }}</span>
                </div>
              </div>
            </div>
            
            <!-- Right: Action Buttons -->
            <div class="stream-actions">
              <button 
                v-if="stream.ended_at"
                @click.stop="watchVideo(stream)" 
                class="action-btn play-btn"
                data-tooltip="Play Video"
              >
                <i class="fas fa-play"></i>
              </button>
              
              <button 
                @click.stop="confirmDeleteStream(stream)" 
                class="action-btn delete-btn" 
                :disabled="deletingStreamId === stream.id || (!stream.ended_at && isStreamRecording(Number(streamerId)))"
                data-tooltip="Delete Stream"
              >
                <i v-if="deletingStreamId === stream.id" class="fas fa-spinner fa-spin"></i>
                <i v-else class="fas fa-trash"></i>
              </button>
              
              <button
                class="action-btn expand-btn"
                @click.stop="toggleStreamExpansion(stream.id)" 
                :data-tooltip="expandedStreams[stream.id] ? 'Collapse Details' : 'Show Details'"
              >
                <i class="fas fa-chevron-down" :class="{ 'rotated': expandedStreams[stream.id] }"></i>
              </button>
            </div>
          </div>
          
          <!-- Expanded Details -->
          <div v-if="expandedStreams[stream.id]" class="stream-expanded-content">
            <!-- Full Category Timeline -->
            <CategoryTimeline 
              v-if="stream.events && stream.events.length > 0"
              :events="stream.events"
              :stream-started="stream.started_at"
              :stream-ended="stream.ended_at"
            />
            
            <!-- Detailed Information -->
            <div class="stream-details">
              <div class="detail-row">
                <span class="label">Started:</span>
                <span class="value">{{ formatDate(stream.started_at) }}</span>
              </div>
              <div v-if="stream.ended_at" class="detail-row">
                <span class="label">Ended:</span>
                <span class="value">{{ formatDate(stream.ended_at) }}</span>
              </div>
              <div v-if="stream.title" class="detail-row">
                <span class="label">Title:</span>
                <span class="value">{{ stream.title }}</span>
              </div>
              <div v-if="stream.category_name" class="detail-row">
                <span class="label">Category:</span>
                <span class="value">{{ stream.category_name }}</span>
              </div>
            </div>
            
            <!-- Full Action Panel -->
            <div class="stream-full-actions">
              <div v-if="!stream.ended_at" class="recording-controls">
                <button 
                  v-if="!isStreamRecording(Number(streamerId))" 
                  @click="startRecording(Number(streamerId))" 
                  class="btn btn-success" 
                  :disabled="isStartingRecording"
                >
                  {{ isStartingRecording ? 'Starting...' : 'Force Record' }}
                </button>
                <button 
                  v-else 
                  @click="stopRecording(Number(streamerId))"
                  class="btn btn-danger" 
                  :disabled="isStoppingRecording"
                >
                  {{ isStoppingRecording ? 'Stopping...' : 'Stop Recording' }}
                </button>
              </div>
              
              <button 
                v-if="stream.ended_at"
                @click="watchVideo(stream)" 
                class="btn btn-primary"
              >
                <i class="fas fa-play"></i>
                Watch Video
              </button>
              
              <button 
                @click="confirmDeleteStream(stream)" 
                class="btn btn-danger" 
                :disabled="deletingStreamId === stream.id || (!stream.ended_at && isStreamRecording(Number(streamerId)))"
              >
                <i v-if="deletingStreamId === stream.id" class="fas fa-spinner fa-spin"></i>
                <i v-else class="fas fa-trash-alt"></i>
                Delete Stream
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Confirmation Modal -->
    <div v-if="showDeleteModal" class="modal-overlay" @click.self="cancelDelete">
      <div class="modal-content">
        <h3>Delete Stream</h3>
        <p>Are you sure you want to delete this stream?</p>
        <p class="warning-text">This will permanently delete the stream record and all associated metadata files.</p>
        

        <div class="stream-stream" v-if="streamToDelete">
          <p><strong>Date:</strong> {{ formatDate(streamToDelete.started_at) }}</p>
          <p><strong>Title:</strong> {{ streamToDelete.title || '-' }}</p>
          <p><strong>Category:</strong> {{ streamToDelete.category_name || '-' }}</p>
        </div>
        
        <div class="modal-actions">
          <button @click="cancelDelete" class="btn btn-secondary">Cancel</button>
          <button @click="deleteStream" class="btn btn-danger" :disabled="deletingStreamId !== null">
            <span v-if="deletingStreamId !== null" class="loader"></span>
            <span v-else>Delete</span>
          </button>
        </div>
      </div>
    </div>
    
    <!-- Delete All Streams Confirmation Modal -->
    <div v-if="showDeleteAllModal" class="modal-overlay" @click.self="cancelDeleteAll">
      <div class="modal-content">
        <h3>Delete All Streams</h3>
        <p>Are you sure you want to delete <strong>ALL {{ streams.length }} streams</strong> for this streamer?</p>
        <p class="warning-text">This will permanently delete ALL stream records and associated metadata files. This action cannot be undone!</p>
        
        <div class="modal-actions">
          <button @click="cancelDeleteAll" class="btn btn-secondary">Cancel</button>
          <button @click="deleteAllStreams" class="btn btn-danger" :disabled="deletingAllStreams">
            <span v-if="deletingAllStreams" class="loader"></span>
            <span v-else>Delete All Streams</span>
          </button>
        </div>
      </div>
    </div>
    
    <!-- Floating Action Button for large lists -->
    <div 
      v-if="streams.length > 10 && !deletingAllStreams" 
      class="floating-delete-btn"
      @click="confirmDeleteAllStreams"
      :title="`Delete all ${streams.length} streams`"
    >
      <i class="fas fa-trash-alt"></i>
      <span class="fab-text">Delete All ({{ streams.length }})</span>
    </div>
    
    <!-- DEBUG: Test tooltip to see if our CSS works -->
    <div style="position: fixed; bottom: 100px; right: 20px; z-index: 9999;">
      <button 
        class="action-btn test-tooltip-btn" 
        data-tooltip="Test Tooltip Works!"
        style="background: #333; color: white; border: 1px solid #555; padding: 10px;"
      >
        TEST
      </button>
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
import CategoryTimeline from './CategoryTimeline.vue'
const route = useRoute()
const router = useRouter()
const streamerId = computed(() => route.params.id as string || route.query.id as string)
const streamerName = computed(() => route.query.name as string)

const { streams, isLoading, fetchStreams } = useStreams()
const { activeRecordings, fetchActiveRecordings, stopRecording: stopStreamRecording } = useRecordingSettings()
const { messages } = useWebSocket()
const { getCategoryImage, preloadCategoryImages } = useCategoryImages()

// State for recording actions
const isStartingRecording = ref(false)
const isStoppingRecording = ref(false)
const isStartingOfflineRecording = ref(false)
const localRecordingState = ref<Record<string, boolean>>({})


//State for stream deletion
const showDeleteModal = ref(false)
const streamToDelete = ref<any>(null)
const deletingStreamId = ref<number | null>(null)
const deleteResults = ref<any>(null)
const showDeleteAllModal = ref(false)
const deletingAllStreams = ref(false)

// State for expandable streams
const expandedStreams = ref<Record<number, boolean>>({})

// Computed property um zu prüfen, ob es Live-Streams gibt
const hasLiveStreams = computed(() => {
  return streams.value.some(stream => !stream.ended_at)
})

// Category image handling
const getCategoryImageSrc = (categoryName: string): string => {
  return getCategoryImage(categoryName)
}

// Formatierungsfunktionen
const formatDate = (date: string | undefined | null): string => {
  if (!date) return 'Unknown'
  return new Date(date).toLocaleString()
}

const calculateDuration = (start: string | undefined | null, end: string | undefined | null): string => {
  if (!start) return 'Unknown'
  
  const startTime = new Date(start).getTime()
  const endTime = end ? new Date(end).getTime() : Date.now()
  
  const durationMs = endTime - startTime
  
  if (durationMs < 0) return 'Invalid time'
  
  const seconds = Math.floor(durationMs / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  
  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`
  } else {
    return `${minutes}m ${seconds % 60}s`
  }
}

// Navigation zurück
const handleBack = () => {
  router.push('/')
}

// Watch video function
const watchVideo = (stream: any) => {
  router.push({
    name: 'VideoPlayer',
    params: { 
      streamerId: streamerId.value,
      streamId: stream.id 
    },
    query: {
      title: stream.title || `Stream ${stream.id}`,
      streamerName: streamerName.value
    }
  })
}

// Prüfen, ob ein Stream aktuell aufgenommen wird
const isStreamRecording = (streamerIdValue: number): boolean => {
  // Ensure we're working with numbers
  const targetStreamerId = Number(streamerIdValue);
  
  // First check local state which gets updated immediately via WebSockets
  if (localRecordingState.value[targetStreamerId] !== undefined) {
    
    return localRecordingState.value[targetStreamerId];
  }
  
  // Then check activeRecordings from the server
  if (!activeRecordings.value || !Array.isArray(activeRecordings.value)) {
    
    return false;
  }
  
  
  
  const isRecording = activeRecordings.value.some(rec => {
    // Ensure both are treated as numbers for comparison
    const recordingStreamerId = Number(rec.streamer_id);
    return recordingStreamerId === targetStreamerId;
  });
  
  
  return isRecording;
}

// Aufnahme starten
const startRecording = async (streamerIdValue: number) => {
  try {
    isStartingRecording.value = true
    
    // Ensure we're working with numbers
    const targetStreamerId = Number(streamerIdValue);
    
    // Update local state immediately for better UX
    localRecordingState.value[targetStreamerId] = true
    
    const response = await fetch(`/api/recording/force/${targetStreamerId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to start recording')
    }
    
    // Keep local state since it was successful
    
    
    // Fetch active recordings to ensure our UI is in sync
    await fetchActiveRecordings()
    
  } catch (error) {
    console.error('Failed to start recording:', error)
    alert(`Failed to start recording: ${error instanceof Error ? error.message : String(error)}`)
    
    // Reset local state on failure
    localRecordingState.value[Number(streamerIdValue)] = false
  } finally {
    isStartingRecording.value = false
  }
}

// Neue Methode: Force-Offline-Recording starten
const forceOfflineRecording = async (streamerIdValue: number) => {
  try {
    isStartingOfflineRecording.value = true
    
    // Ensure we're working with numbers
    const targetStreamerId = Number(streamerIdValue);
    
    // Update local state immediately for better UX
    localRecordingState.value[targetStreamerId] = true
    
    const response = await fetch(`/api/recording/force-offline/${targetStreamerId}`, {
     method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to start offline recording')
    }
    
    // Keep local state since it was successful
    
    
    // Fetch active recordings to ensure our UI is in sync
    await fetchActiveRecordings()
    
    // Reload streams to show the newly created stream
    await fetchStreams(streamerId.value)
    
  } catch (error) {
    console.error('Failed to start offline recording:', error)
    alert(`Failed to start offline recording: ${error instanceof Error ? error.message : String(error)}`)
    
    // Reset local state on failure
    localRecordingState.value[Number(streamerIdValue)] = false
  } finally {
    isStartingOfflineRecording.value = false
  }
}

// Aufnahme stoppen
const stopRecording = async (streamerIdValue: number) => {
  try {
    isStoppingRecording.value = true
    
    // Ensure we're working with numbers
    const targetStreamerId = Number(streamerIdValue);
    
    // Sofort Status lokal aktualisieren für bessere UX
    localRecordingState.value[targetStreamerId] = false
    
    await stopStreamRecording(targetStreamerId)
    
    // Nach erfolgreicher API-Anfrage trotzdem aktualisieren
    await fetchActiveRecordings()
    
  } catch (error) {
    console.error('Failed to stop recording:', error)
    alert(`Failed to stop recording: ${error instanceof Error ? error.message : String(error)}`)
    // Setze den lokalen Status zurück, wenn die Anfrage fehlschlägt
    localRecordingState.value[Number(streamerIdValue)] = true
  } finally {
    isStoppingRecording.value = false
  }
}

// Toggle stream expansion
const toggleStreamExpansion = (streamId: number) => {
  expandedStreams.value[streamId] = !expandedStreams.value[streamId]
}

// Stream deletion functions
const confirmDeleteStream = (stream: any) => {
  streamToDelete.value = stream
  showDeleteModal.value = true
}

const cancelDelete = () => {
  showDeleteModal.value = false
  streamToDelete.value = null
}

const deleteStream = async () => {
  if (!streamToDelete.value || !streamerId.value) return
  
  try {
    deletingStreamId.value = streamToDelete.value.id
    
    const response = await fetch(`/api/streamers/${streamerId.value}/streams/${streamToDelete.value.id}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to delete stream')
    }
    
    const result = await response.json()
    deleteResults.value = result

    
    // Remove stream from the UI
    streams.value = streams.value.filter(s => s.id !== streamToDelete.value.id)
    
    // Close the modal
    showDeleteModal.value = false
    streamToDelete.value = null
    
    // Show success success
    alert(`Stream deleted successfully. Removed ${result.deleted_files_count} associated files.`)
    
  } catch (error) {
    console.error('Failed to delete stream:', error)
    alert(`Failed to delete stream: ${error instanceof Error ? error.message : String(error)}`)
  } finally {
    deletingStreamId.value = null
  }
}

// New function to confirm deletion of all streams
const confirmDeleteAllStreams = () => {
  showDeleteAllModal.value = true
}

// Cancel deletion of all streams
const cancelDeleteAll = () => {
  showDeleteAllModal.value = false
}

// Delete all streams for the current streamer
const deleteAllStreams = async () => {
  if (!streamerId.value) return
  
  try {
    deletingAllStreams.value = true
    
    const response = await fetch(`/api/streamers/${streamerId.value}/streams`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to delete all streams')
    }
    
    const result = await response.json()

    
    // Clear the streams list in the UI
    streams.value = []
    
    // Close the modal
    showDeleteAllModal.value = false
    
    // Show success message
    alert(`All streams deleted successfully. Removed ${result.deleted_files_count} associated files.`)
    
  } catch (error) {
    console.error('Failed to delete all streams:', error)
    alert(`Failed to delete all streams: ${error instanceof Error ? error.message : String(error)}`)
  } finally {
    deletingAllStreams.value = false
  }
}

// Daten laden
const loadStreams = async () => {
  if (streamerId.value) {
    await fetchStreams(streamerId.value);
    await fetchActiveRecordings();
    
    
    // Preload category images for all streams
    const categories = streams.value
      .map(stream => stream.category_name)
      .filter((name: string | null): name is string => Boolean(name))
      .filter((value, index, self) => self.indexOf(value) === index); // Remove duplicates
    
    if (categories.length > 0) {
      preloadCategoryImages(categories);
    }
  }
}

onMounted(async () => {
  await loadStreams();
  
  // Load initial active recordings
  await fetchActiveRecordings();
  
});

// WebSocket-Nachrichten überwachen
watch(messages, (newMessages) => {
  if (newMessages.length === 0) return
  
  const latestMessage = newMessages[newMessages.length - 1]
  // Handle WebSocket messages
  if (latestMessage.type === 'active_recordings_update') {
    activeRecordings.value = latestMessage.data || []
  } else if (latestMessage.type === 'recording_started' || latestMessage.type === 'recording_stopped') {
    // Refresh active recordings when recording state changes
    fetchActiveRecordings()
  }
  
  // Update local state based on WebSocket events
  if (latestMessage.type === 'recording.started') {
    const streamerId = Number(latestMessage.data.streamer_id);
    
    
    // Update local state immediately
    localRecordingState.value[streamerId] = true;
    
    // Also update our local cache of activeRecordings
    if (!activeRecordings.value) {
      activeRecordings.value = [];
    }
    
    // Add or update the recording in our cache
    const existingIndex = activeRecordings.value.findIndex(r => 
      Number(r.streamer_id) === streamerId
    );
    
    if (existingIndex >= 0) {
      activeRecordings.value[existingIndex] = latestMessage.data;
    } else {
      activeRecordings.value.push(latestMessage.data);
    }
    
    // Still fetch from server to ensure we're in sync
    fetchActiveRecordings();
    
  } else if (latestMessage.type === 'recording.stopped') {
    const streamerId = Number(latestMessage.data.streamer_id);
    
    
    // Update local state immediately
    localRecordingState.value[streamerId] = false;
    
    // Remove from our local cache
    if (activeRecordings.value) {
      activeRecordings.value = activeRecordings.value.filter(r => 
        Number(r.streamer_id) !== streamerId
      );
    }
    
    // Sync with server
    fetchActiveRecordings();
  } else if (latestMessage.type === 'stream.online') {
    // Wenn ein neuer Stream erkannt wird, aktualisieren wir die Stream-Liste
    if (Number(latestMessage.data.streamer_id) === Number(streamerId.value)) {
      fetchStreams(streamerId.value);
    }
  }
}, { deep: true })

// Daten neu laden, wenn sich die StreamerID ändert
watch(streamerId, (newId, oldId) => {
  if (newId && newId !== oldId) {
    loadStreams()
  }
})

const handleImageError = (event: Event, categoryName: string) => {
  const img = event.target as HTMLImageElement;
  const container = img.parentElement;
  
  console.error(`Failed to load category image for: ${categoryName}`);
  
  // Hide the image
  img.style.display = 'none';
  
  // Show fallback icon by replacing the image with an icon wrapper
  if (container) {
    const iconWrapper = document.createElement('div');
    iconWrapper.className = 'category-icon-wrapper';
    
    const icon = document.createElement('i');
    icon.className = `fas ${getCategoryImage(categoryName).replace('icon:', '')}`;
    
    iconWrapper.appendChild(icon);
    container.appendChild(iconWrapper);
  }
}
</script>

<style scoped>
.streams-container {
  padding: 20px;
}

.loading-container,
.no-data-container {
  text-align: center;
  padding: 40px;
}

/* Header Styles */
.streams-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 30px;
  padding: 20px;
  background: linear-gradient(135deg, #1f1f23 0%, #18181b 100%);
  border-radius: 12px;
  border: 1px solid #333;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  position: sticky;
  top: 0;
  z-index: 100;
  backdrop-filter: blur(10px);
}

.header-info h2 {
  margin: 0 0 8px 0;
  color: #fff;
  font-size: 1.5rem;
  font-weight: 600;
}

.streams-summary {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stream-count {
  color: #aaa;
  font-size: 0.95rem;
  font-weight: 500;
}

.live-indicator {
  color: #dc3545;
  font-size: 0.9rem;
  font-weight: 600;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

/* Standardize all header buttons */
.header-actions .btn {
  height: 44px;
  min-width: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 16px;
  font-size: 0.9rem;
  font-weight: 600;
  white-space: nowrap;
}

/* Ensure consistent spacing for icons and text */
.header-actions .btn i {
  font-size: 0.9rem;
  margin: 0;
}

.header-actions .btn span {
  display: inline-block;
}

/* Back button specific styling */
.back-btn {
  min-width: 160px;
}

/* Delete all button specific styling */
.delete-all-btn {
  min-width: 140px;
}

.delete-all-btn {
  background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
  border: none;
  font-weight: 600;
  position: relative;
  transition: all 0.3s ease;
}

.delete-all-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #c82333 0%, #a71e2a 100%);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(220, 53, 69, 0.4);
}

.delete-all-btn:active:not(:disabled) {
  transform: translateY(0);
}

.delete-all-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none !important;
}

/* Responsive header */
@media (max-width: 768px) {
  .streams-header {
    flex-direction: column;
    gap: 20px;
    text-align: center;
  }
  
  .header-actions {
    justify-content: center;
    width: 100%;
  }
  
  /* Mobile button adjustments */
  .header-actions .btn {
    min-width: 140px;
    font-size: 0.85rem;
  }
  
  .back-btn {
    min-width: 140px;
  }
  
  .delete-all-btn {
    min-width: 120px;
  }
}

.actions-container {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  align-items: center;
  flex-wrap: wrap;
}

.action-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 20px;
}

/* Ensure consistent button styling across all contexts */
.action-buttons .btn {
  height: 44px;
  min-width: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 16px;
  font-size: 0.9rem;
  font-weight: 600;
}

.action-buttons .btn i {
  font-size: 0.9rem;
}

.action-buttons .btn span {
  display: inline-block;
}

.back-btn {
  display: flex;
  align-items: center;
}
.btn-warning {
  background-color: #ff9800;
  color: #000;
  font-weight: 500;
  transition: background-color 0.2s, transform 0.2s;
}

.btn-warning:hover:not(:disabled) {
  background-color: #ffac33;
  transform: translateY(-1px);
}

.btn-warning:active:not(:disabled) {
  transform: translateY(0);
}

.btn-warning:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.streams-summary {
  margin-bottom: 20px;
  font-size: 1.2em;
  color: #9146FF;
}

.stream-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 20px;
}

.stream-card {
  background: #1f1f23;
  border-radius: 12px;
  overflow: visible; /* Allow tooltips to be visible outside card bounds */
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
  transition: all 0.3s ease;
  border: 1px solid #333;
  min-width: 0;
  max-width: 100%;
  word-wrap: break-word;
  height: auto;
  min-height: 200px;
  margin-bottom: 60px; /* Increased space for tooltips */
  position: relative; /* Needed for tooltip positioning */
}

.stream-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.stream-card.expanded {
  border-color: #9146FF;
}

/* Compact Header - New Layout */
.stream-compact-header {
  display: flex;
  align-items: stretch;
  padding: 16px;
  cursor: pointer;
  background: #18181b;
  border-bottom: 1px solid #333;
  transition: background-color 0.2s ease;
  min-height: 120px;
  gap: 16px;
  border-radius: 12px 12px 0 0; /* Keep rounded corners only at top */
  overflow: visible; /* Allow tooltips to show outside header */
  position: relative; /* Needed for tooltip positioning */
}

.stream-compact-header:hover {
  background: #1a1a1e;
}

/* Left: Category Image */
.stream-thumbnail {
  flex-shrink: 0;
  width: 80px;
  height: 80px;
  align-self: center;
}

.category-image-container {
  width: 90px;   /* Adjusted for 3:4 aspect ratio like Twitch category images */
  height: 120px; /* 90 * 4/3 = 120 for proper 3:4 ratio (285x380) */
  border-radius: 8px;
  overflow: hidden;
  background-color: #121214;
  border: 1px solid #333;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.category-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.category-icon-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #6441a5, #9146ff);
  color: white;
  font-size: 24px;
}

.category-placeholder {
  width: 120px;  /* Match the new container width */
  height: 68px;   /* Match the new container height */
  background: linear-gradient(45deg, #333, #444);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #aaa;
  font-size: 20px;
  border: 1px solid #333;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

/* Center: Stream Info */
.stream-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: 0;
  padding-right: 16px;
}

.stream-badges {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.stream-title {
  margin: 0 0 8px 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: #fff;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stream-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: auto;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.85rem;
  color: #aaa;
  background: rgba(255, 255, 255, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
}

.meta-item i {
  font-size: 0.8rem;
}

.duration-item {
  background: rgba(145, 70, 255, 0.2);
  color: #b379ff;
}

.category-item {
  background: rgba(255, 255, 255, 0.1);
  color: #ddd;
}

/* Right: Action Buttons */
.stream-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 50px;
  padding: 8px 5px;
}

.action-btn {
  width: 40px !important;
  height: 40px !important;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all 0.2s ease;
  position: relative;
  margin: 0;
  padding: 0;
  background: rgba(255, 255, 255, 0.1) !important;
  backdrop-filter: blur(5px);
}

.action-btn i {
  font-size: 16px;
  font-weight: 900;
  z-index: 1;
  transition: color 0.2s ease;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.2) !important;
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.5);
}

/* Play button - Green play icon */
.play-btn i {
  color: #28a745;
}

.play-btn:hover i {
  color: #20c437;
}

/* Delete button - Red trash icon, override global styles */
.action-btn.delete-btn {
  background: rgba(255, 255, 255, 0.1) !important;
  box-shadow: none !important;
}

.action-btn.delete-btn i {
  color: #dc3545;
}

.action-btn.delete-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.2) !important;
  box-shadow: none !important;
}

.action-btn.delete-btn:hover:not(:disabled) i {
  color: #ff4757;
}

/* Expand button - Blue chevron icon */
.expand-btn i {
  color: #007bff;
}

.expand-btn:hover i {
  color: #0056b3;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

/* Icon animations and states */
.fa-play, .fa-trash, .fa-chevron-down {
  transition: transform 0.2s ease;
}

.fa-chevron-down.rotated {
  transform: rotate(180deg);
}

.fa-spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none !important;
  background: rgba(100, 100, 100, 0.3) !important;
}

.action-btn:disabled i {
  color: #666 !important;
}

/* Enhanced icon animations */
.fa-play, .fa-trash, .fa-chevron-down {
  transition: all 0.2s ease;
}

.fa-chevron-down.rotated {
  transform: rotate(180deg);
}

.fa-spinner {
  animation: spin 1s linear infinite;
  color: #ffc107 !important; /* Yellow spinner for visibility */
}

/* Tooltip system with proper positioning and high z-index */
.action-btn[data-tooltip], .test-tooltip-btn[data-tooltip] {
  position: relative;
}

.action-btn[data-tooltip]:hover:not(:disabled)::before,
.test-tooltip-btn[data-tooltip]:hover::before {
  content: attr(data-tooltip);
  position: absolute;
  top: -45px; /* Position above button */
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.95);
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  z-index: 99999; /* Very high z-index to ensure visibility */
  pointer-events: none;
  border: 1px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(8px);
  animation: tooltipFadeIn 0.2s ease-out;
}

/* Tooltip arrow pointing down */
.action-btn[data-tooltip]:hover:not(:disabled)::after,
.test-tooltip-btn[data-tooltip]:hover::after {
  content: '';
  position: absolute;
  top: -10px; /* Position arrow below tooltip */
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 6px solid rgba(0, 0, 0, 0.95);
  z-index: 99998;
  pointer-events: none;
  animation: tooltipFadeIn 0.2s ease-out;
}

@keyframes tooltipFadeIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(5px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

/* Prevent tooltips from overlapping by staggering positions slightly */
.play-btn[data-tooltip]:hover:not(:disabled)::before {
  left: 45%; /* Slightly left */
}

.delete-btn[data-tooltip]:hover:not(:disabled)::before {
  left: 50%; /* Center */
}

.expand-btn[data-tooltip]:hover:not(:disabled)::before {
  left: 55%; /* Slightly right */
}

.play-btn[data-tooltip]:hover:not(:disabled)::after {
  left: 45%;
}

.delete-btn[data-tooltip]:hover:not(:disabled)::after {
  left: 50%;
}

.expand-btn[data-tooltip]:hover:not(:disabled)::after {
  left: 55%;
}

/* Expanded Content */
.stream-expanded-content {
  padding: 16px;
  background: #1a1a1e;
  border-top: 1px solid #333;
  animation: slideDown 0.3s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    max-height: 0;
    padding-top: 0;
    padding-bottom: 0;
  }
  to {
    opacity: 1;
    max-height: 500px;
    padding-top: 16px;
    padding-bottom: 16px;
  }
}

.stream-details {
  margin-bottom: 16px;
}

.detail-row {
  display: flex;
  margin-bottom: 8px;
  font-size: 0.9rem;
}

.detail-row .label {
  width: 80px;
  color: #aaa;
  font-weight: 500;
  flex-shrink: 0;
}

.detail-row .value {
  color: #fff;
  word-break: break-word;
}

.stream-full-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.recording-controls {
  display: flex;
  gap: 8px;
}

/* Status badges - standardized sizing */
.status-badge {
  background-color: #444;
  color: white;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  box-shadow: 0 2px 4px rgba(0,0,0,0.4);
  letter-spacing: 0.5px;
  min-width: 50px;
  text-align: center;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-badge.live {
  background-color: #e91916;
  animation: pulse 2s infinite;
  box-shadow: 0 2px 6px rgba(233, 25, 22, 0.6);
}

.recording-badge {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  box-shadow: 0 2px 4px rgba(0,0,0,0.4);
  letter-spacing: 0.5px;
  min-width: 50px;
  text-align: center;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.recording-badge.recording {
  background-color: #28a745;
  color: white;
  animation: pulse 2s infinite;
  box-shadow: 0 2px 6px rgba(40, 167, 69, 0.6);
}

.recording-badge.not-recording {
  background-color: #dc3545;
  color: white;
  box-shadow: 0 2px 6px rgba(220, 53, 69, 0.6);
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.75);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  padding: 20px;
  box-sizing: border-box;
}

.modal-content {
  background-color: #1f1f23;
  border-radius: 12px;
  padding: 24px;
  min-width: 400px;
  max-width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
  border: 1px solid #333;
  /* Ensure modal is always visible */
  position: relative;
  transform: translateY(0);
}

.modal-content h3 {
  color: #fff;
  margin-top: 0;
  margin-bottom: 15px;
}

.warning-text {
  color: #ff5252;
  font-weight: 500;
  margin-bottom: 20px;
}

.stream-stream {
  background-color: #18181b;
  padding: 10px;
  border-radius: 4px;
  margin-bottom: 20px;
}

.stream-stream p {
  margin: 5px 0;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

.btn-secondary {
  background-color: #444;
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background-color: #555;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .stream-list {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  
  .stream-compact-header {
    padding: 12px;
    min-height: 100px;
    gap: 12px;
  }
  
  .stream-thumbnail {
    width: 100px;   /* Increased for mobile 16:9 */
    height: 56px;   /* 100 * 9/16 = 56.25, rounded to 56 */
  }
  
  .category-image-container, .category-placeholder {
    width: 75px;    /* Smaller but maintain 3:4 portrait ratio for mobile */
    height: 100px;  /* 75 * 4/3 = 100 for proper 3:4 ratio */
  }
  
  .category-icon-wrapper {
    font-size: 20px;  /* Smaller icon for mobile */
  }
  
  .stream-title {
    font-size: 1rem;
  }
  
  .stream-meta {
    gap: 8px;
  }
  
  .meta-item {
    font-size: 0.8rem;
    padding: 3px 6px;
  }
  
  .action-btn {
    width: 36px;
    height: 36px;
    font-size: 0.9rem;
  }
}

@media (max-width: 480px) {
  .stream-list {
    grid-template-columns: 1fr;
    gap: 20px;
  }
  
  .stream-card {
    min-width: 280px;
    max-width: calc(100vw - 40px);
    min-height: 220px; /* Much taller on mobile */
  }
  
  .stream-compact-header {
    flex-direction: row;
    padding: 20px;
    min-height: 200px; /* Much taller header on mobile */
    align-items: flex-start;
  }
  
  .stream-thumbnail {
    width: 80px;
    height: 112px;
    margin-right: 16px;
  }
  
  .category-image-small {
    width: 80px;
    height: 112px;
  }
  
  .category-placeholder {
    width: 80px;
    height: 112px;
  }
  
  .stream-summary {
    max-width: calc(100% - 100px);
    padding-right: 40px; /* Make room for action buttons */
  }
  
  .expand-controls {
    position: absolute;
    top: 12px;
    right: 12px;
  }
  
  .quick-actions {
    flex-direction: column;
    gap: 10px;
  }
  
  .btn-icon {
    width: 46px;
    height: 46px;
  }
  
  .stream-title {
    font-size: 1rem;
    margin-top: 6px;
    margin-bottom: 10px;
    -webkit-line-clamp: 3; /* Show more lines on mobile */
    line-clamp: 3;
    padding-right: 10px;
  }
  
  .stream-badges {
    margin-bottom: 8px;
  }
  
  .stream-meta {
    margin-top: 10px;
    font-size: 0.95rem;
  }
}

/* Floating Action Button */
.floating-delete-btn {
  position: fixed;
  bottom: 30px;
  right: 30px;
  background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
  color: white;
  border: none;
  border-radius: 50px;
  padding: 16px 24px;
  box-shadow: 0 4px 20px rgba(220, 53, 69, 0.4);
  cursor: pointer;
  z-index: 1000;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  border: 2px solid rgba(255, 255, 255, 0.2);
}

.floating-delete-btn:hover {
  background: linear-gradient(135deg, #c82333 0%, #a71e2a 100%);
  transform: translateY(-3px);
  box-shadow: 0 6px 25px rgba(220, 53, 69, 0.6);
}

.floating-delete-btn:active {
  transform: translateY(-1px);
}

.floating-delete-btn .fab-text {
  font-size: 0.9rem;
  white-space: nowrap;
}

.floating-delete-btn i {
  font-size: 1.1rem;
}

/* Hide FAB on small screens where header is always visible */
@media (max-width: 768px) {
  .floating-delete-btn {
    bottom: 20px;
    right: 20px;
    padding: 12px 16px;
    font-size: 0.85rem;
  }
  
  .floating-delete-btn .fab-text {
    display: none;
  }
  
  .floating-delete-btn {
    border-radius: 50%;
    width: 56px;
    height: 56px;
    padding: 0;
    justify-content: center;
  }
}
</style>
