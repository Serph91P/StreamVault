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
          Back to streamers
        </button>
        
        <button @click="forceOfflineRecording(parseInt(streamerId))" class="btn btn-warning">
          Force Recording (Offline Mode)
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
            Back to Streamers
          </button>
          
          <button 
            v-if="!hasLiveStreams" 
            @click="forceOfflineRecording(parseInt(streamerId))" 
            class="btn btn-warning"
            :disabled="isStartingOfflineRecording"
          >
            <i class="fas fa-record-vinyl"></i>
            {{ isStartingOfflineRecording ? 'Starting Recording...' : 'Force Recording (Offline)' }}
          </button>
          
          <button 
            @click="confirmDeleteAllStreams" 
            class="btn btn-danger delete-all-btn"
            :disabled="deletingAllStreams || streams.length === 0"
            :title="`Delete all ${streams.length} streams`"
          >
            <i class="fas fa-trash-alt"></i>
            {{ deletingAllStreams ? 'Deleting All...' : `Delete All (${streams.length})` }}
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
            <div class="stream-thumbnail">
              <div v-if="stream.category_name" class="category-image-small">
                <img 
                  v-if="!getCategoryImage(stream.category_name).startsWith('icon:')"
                  :src="getCategoryImage(stream.category_name)" 
                  :alt="stream.category_name" 
                  @error="handleImageError($event, stream.category_name)"
                  loading="lazy"
                />
                <i 
                  v-else
                  :class="getCategoryImage(stream.category_name).replace('icon:', 'fas ')" 
                  class="category-icon"
                ></i>
              </div>
              <div v-else class="category-placeholder">
                <i class="fas fa-video"></i>
              </div>
            </div>
            
            <div class="stream-summary">
              <div class="stream-badges">
                <span class="status-badge" :class="{ 'live': !stream.ended_at }">
                  {{ !stream.ended_at ? 'LIVE' : 'ENDED' }}
                </span>
                <span 
                  v-if="!stream.ended_at" 
                  class="recording-badge" 
                  :class="isStreamRecording(parseInt(streamerId)) ? 'recording' : 'not-recording'"
                >
                  {{ isStreamRecording(parseInt(streamerId)) ? 'REC' : 'OFF' }}
                </span>
              </div>
              
              <h3 class="stream-title">{{ stream.title || formatDate(stream.started_at) }}</h3>
              <div class="stream-meta">
                <span class="duration">{{ calculateDuration(stream.started_at, stream.ended_at) }}</span>
                <span v-if="stream.category_name" class="category">{{ stream.category_name }}</span>
              </div>
            </div>
            
            <div class="expand-controls">
              <div class="quick-actions">
                <!-- Action buttons with larger, more visible icons -->
                <button 
                  v-if="stream.ended_at"
                  @click.stop="watchVideo(stream)" 
                  class="btn-icon btn-primary"
                  title="Watch Video"
                  aria-label="Watch Video"
                >
                  <i class="fas fa-play fa-lg"></i>
                </button>
                
                <button 
                  @click.stop="confirmDeleteStream(stream)" 
                  class="btn-icon btn-danger" 
                  :disabled="deletingStreamId === stream.id || (!stream.ended_at && isStreamRecording(parseInt(streamerId)))"
                  title="Delete Stream"
                  aria-label="Delete Stream"
                >
                  <i v-if="deletingStreamId === stream.id" class="fas fa-spinner fa-spin fa-lg"></i>
                  <i v-else class="fas fa-trash-alt fa-lg"></i>
                </button>
                
                <button
                  class="btn-icon btn-secondary"
                  @click.stop="toggleStreamExpansion(stream.id)" 
                  title="Toggle Details" 
                  aria-label="Toggle Details"
                >
                  <i class="fas fa-chevron-down fa-lg" :class="{ 'rotated': expandedStreams[stream.id] }"></i>
                </button>
              </div>

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
                  v-if="!isStreamRecording(parseInt(streamerId))" 
                  @click="startRecording(parseInt(streamerId))" 
                  class="btn btn-success" 
                  :disabled="isStartingRecording"
                >
                  {{ isStartingRecording ? 'Starting...' : 'Force Record' }}
                </button>
                <button 
                  v-else 
                  @click="stopRecording(parseInt(streamerId))"
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
                :disabled="deletingStreamId === stream.id || (!stream.ended_at && isStreamRecording(parseInt(streamerId)))"
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
  // First check local state which gets updated immediately via WebSockets
  if (localRecordingState.value[streamerIdValue] !== undefined) {
    console.log(`Using local recording state for ${streamerIdValue}: ${localRecordingState.value[streamerIdValue]}`);
    return localRecordingState.value[streamerIdValue];
  }
  
  // Then check activeRecordings from the server
  if (!activeRecordings.value || !Array.isArray(activeRecordings.value)) {
    console.log(`No active recordings available for ${streamerIdValue}`);
    return false;
  }
  
  console.log(`Active recordings for ${streamerIdValue}:`, activeRecordings.value);
  
  const isRecording = activeRecordings.value.some(rec => {
    // Ensure both are treated as numbers for comparison
    return parseInt(rec.streamer_id.toString()) === parseInt(streamerIdValue.toString());
  });
  
  console.log(`Stream ${streamerIdValue} recording status: ${isRecording}`);
  return isRecording;
}

// Aufnahme starten
const startRecording = async (streamerIdValue: number) => {
  try {
    isStartingRecording.value = true
    
    // Update local state immediately for better UX
    localRecordingState.value[streamerIdValue] = true
    
    const response = await fetch(`/api/recording/force/${streamerIdValue}`, {
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
    console.log(`Successfully started recording for streamer ${streamerIdValue}`);
    
    // Fetch active recordings to ensure our UI is in sync
    await fetchActiveRecordings()
    
  } catch (error) {
    console.error('Failed to start recording:', error)
    alert(`Failed to start recording: ${error instanceof Error ? error.message : String(error)}`)
    
    // Reset local state on failure
    localRecordingState.value[streamerIdValue] = false
  } finally {
    isStartingRecording.value = false
  }
}

// Neue Methode: Force-Offline-Recording starten
const forceOfflineRecording = async (streamerIdValue: number) => {
  try {
    isStartingOfflineRecording.value = true
    
    // Update local state immediately for better UX
    localRecordingState.value[streamerIdValue] = true
    
    const response = await fetch(`/api/recording/force-offline/${streamerIdValue}`, {
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
    console.log(`Successfully started offline recording for streamer ${streamerIdValue}`);
    
    // Fetch active recordings to ensure our UI is in sync
    await fetchActiveRecordings()
    
    // Reload streams to show the newly created stream
    await fetchStreams(streamerId.value)
    
  } catch (error) {
    console.error('Failed to start offline recording:', error)
    alert(`Failed to start offline recording: ${error instanceof Error ? error.message : String(error)}`)
    
    // Reset local state on failure
    localRecordingState.value[streamerIdValue] = false
  } finally {
    isStartingOfflineRecording.value = false
  }
}

// Aufnahme stoppen
const stopRecording = async (streamerIdValue: number) => {
  try {
    isStoppingRecording.value = true
    
    // Sofort Status lokal aktualisieren für bessere UX
    localRecordingState.value[streamerIdValue] = false
    
    await stopStreamRecording(streamerIdValue)
    
    // Nach erfolgreicher API-Anfrage trotzdem aktualisieren
    await fetchActiveRecordings()
    
  } catch (error) {
    console.error('Failed to stop recording:', error)
    alert(`Failed to stop recording: ${error instanceof Error ? error.message : String(error)}`)
    // Setze den lokalen Status zurück, wenn die Anfrage fehlschlägt
    localRecordingState.value[streamerIdValue] = true
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
    console.log('Delete stream result:', result)
    
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
    console.log('Delete all streams result:', result)
    
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
    console.log("Loaded active recordings:", activeRecordings.value);
    
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
  
  // Poll active recordings immediately and then every 5 seconds
  await fetchActiveRecordings();
  console.log("Initial active recordings:", activeRecordings.value);
  
  const interval = setInterval(async () => {
    try {
      await fetchActiveRecordings();
      console.log("Updated active recordings:", activeRecordings.value);
    } catch (err) {
      console.error("Error fetching active recordings:", err);
    }
  }, 5000);
  
  // Cleanup on component unmount
  onUnmounted(() => {
    clearInterval(interval);
  });
});

// WebSocket-Nachrichten überwachen
watch(messages, (newMessages) => {
  if (newMessages.length === 0) return
  
  const latestMessage = newMessages[newMessages.length - 1]
  console.log('Received WebSocket message:', latestMessage)
  
  // Update local state based on WebSocket events
  if (latestMessage.type === 'recording.started') {
    const streamerId = parseInt(latestMessage.data.streamer_id);
    console.log(`Recording started for streamer ${streamerId}`);
    
    // Update local state immediately
    localRecordingState.value[streamerId] = true;
    
    // Also update our local cache of activeRecordings
    if (!activeRecordings.value) {
      activeRecordings.value = [];
    }
    
    // Add or update the recording in our cache
    const existingIndex = activeRecordings.value.findIndex(r => 
      parseInt(r.streamer_id.toString()) === streamerId
    );
    
    if (existingIndex >= 0) {
      activeRecordings.value[existingIndex] = latestMessage.data;
    } else {
      activeRecordings.value.push(latestMessage.data);
    }
    
    // Still fetch from server to ensure we're in sync
    fetchActiveRecordings();
    
  } else if (latestMessage.type === 'recording.stopped') {
    const streamerId = parseInt(latestMessage.data.streamer_id);
    console.log(`Recording stopped for streamer ${streamerId}`);
    
    // Update local state immediately
    localRecordingState.value[streamerId] = false;
    
    // Remove from our local cache
    if (activeRecordings.value) {
      activeRecordings.value = activeRecordings.value.filter(r => 
        parseInt(r.streamer_id.toString()) !== streamerId
      );
    }
    
    // Sync with server
    fetchActiveRecordings();
  } else if (latestMessage.type === 'stream.online') {
    // Wenn ein neuer Stream erkannt wird, aktualisieren wir die Stream-Liste
    if (parseInt(latestMessage.data.streamer_id) === parseInt(streamerId.value)) {
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
  
  // Log the error for debugging
  console.error(`Failed to load image for category: ${categoryName}`, event);
  
  // Try to load default image
  img.onerror = () => {
    // If default image also fails, replace with an icon
    if (container) {
      container.innerHTML = `<i class="fas fa-gamepad category-icon"></i>`;
      container.classList.add('category-placeholder');
      container.classList.remove('category-image-small');
    }
  };
  
  // Prevent infinite loops and try the default image
  img.src = '/images/categories/default-category.svg';
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
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.stream-card {
  background: #1f1f23;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
  transition: all 0.3s ease;
  border: 1px solid #333;
  min-width: 0;
  max-width: 100%;
  word-wrap: break-word;
  height: auto;
  min-height: 160px; /* Increased minimum height */
}

.stream-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.stream-card.expanded {
  border-color: #9146FF;
}

/* Compact Header */
.stream-compact-header {
  display: flex;
  align-items: flex-start; /* Align items at the top */
  padding: 16px;
  cursor: pointer;
  background: #18181b;
  border-bottom: 1px solid #333;
  transition: background-color 0.2s ease;
  min-width: 0;
  position: relative;
  min-height: 140px; /* Increased height to accommodate content */
  flex-wrap: nowrap; /* Prevent wrapping */
  gap: 16px; /* Increased space between elements */
}

.stream-compact-header:hover {
  background: #1a1a1e;
}

.stream-thumbnail {
  flex-shrink: 0;
  width: 65px;
  height: 90px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
  margin-right: 0;
}

.category-image-small {
  width: 65px;
  height: 90px;
  overflow: hidden;
  border-radius: 6px;
  background-color: #121214;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
  border: 1px solid #333;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.category-image-small img {
  width: 100%; /* Fill the width */
  height: 100%; /* Fill the height */
  object-fit: contain; /* Keep aspect ratio and show full image */
  border-radius: 5px;
  padding: 2px; /* Small padding to ensure no edge clipping */
}

.category-placeholder {
  width: 65px;
  height: 90px;
  background: linear-gradient(45deg, #333, #444);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #888;
  font-size: 24px;
  border: 1px solid #333;
  z-index: 1;
}

.category-icon {
  font-size: 24px;
  color: #9146FF;
}

.stream-summary {
  flex: 1;
  min-width: 0;
  padding-right: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: flex-start; /* Align at top */
  padding-top: 4px;
}

.stream-badges {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.stream-title {
  margin: 8px 0 12px 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: #fff;
  word-wrap: break-word;
  overflow-wrap: break-word;
  hyphens: auto;
  line-height: 1.4;
  max-width: 100%;
  white-space: normal;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.9); /* Enhanced text shadow for better contrast */
  padding-right: 30px; /* Make space for expand controls */
}

.stream-meta {
  display: flex;
  gap: 12px;
  font-size: 1rem;
  color: #aaa;
  flex-wrap: wrap;
  align-items: center;
  overflow: hidden;
  margin-top: auto; /* Push to bottom of container */
  position: relative;
  padding-top: 6px;
}

.stream-meta .duration {
  font-weight: 700;
  color: #a366ff;
  white-space: nowrap;
  background-color: rgba(145, 70, 255, 0.15);
  padding: 3px 8px;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.stream-meta .category {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 180px;
  background-color: rgba(255, 255, 255, 0.15);
  padding: 3px 8px;
  border-radius: 4px;
  color: #ddd;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.expand-controls {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  flex-shrink: 0;
  margin-left: auto;
  position: absolute;
  top: 12px;
  right: 12px;
  min-width: auto;
  justify-content: flex-end;
  z-index: 5;
}

.quick-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.btn-icon {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.15rem;
  transition: all 0.2s ease;
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.4);
  opacity: 0.9;
}

.btn-icon.btn-primary {
  background: #1a73e8;
  color: white;
  border: 2px solid rgba(255, 255, 255, 0.2);
}

.btn-icon.btn-primary:hover:not(:disabled) {
  background: #1557b0;
  transform: translateY(-2px);
  box-shadow: 0 5px 10px rgba(0, 0, 0, 0.5);
  opacity: 1;
}

.btn-icon.btn-danger {
  background: #e02c40;
  color: white;
  border: 2px solid rgba(255, 255, 255, 0.2);
}

.btn-icon.btn-danger:hover:not(:disabled) {
  background: #ba1f30;
  transform: translateY(-2px);
  box-shadow: 0 5px 10px rgba(0, 0, 0, 0.5);
  opacity: 1;
  transform: translateY(-2px);
  box-shadow: 0 5px 8px rgba(0, 0, 0, 0.4);
}

.btn-icon.btn-secondary {
  background: #3a3a3a;
  color: #e0e0e0;
  border: 2px solid rgba(255, 255, 255, 0.1);
}

.btn-icon.btn-secondary:hover:not(:disabled) {
  background: #4a4a4a;
  transform: translateY(-2px);
  box-shadow: 0 5px 10px rgba(0, 0, 0, 0.5);
  opacity: 1;
}

.btn-icon:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.expand-btn {
  width: 32px;
  height: 32px;
  border: 1px solid #555;
  background: transparent;
  color: #aaa;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.expand-btn:hover {
  background: #333;
  color: #fff;
}

.expand-btn i.rotated {
  transform: rotate(180deg);
}

/* Add icon animations */
.fa-play, .fa-trash-alt, .fa-chevron-down {
  transition: transform 0.2s ease;
}

.btn-icon:hover:not(:disabled) .fa-play {
  transform: scale(1.2);
}

.btn-icon:hover:not(:disabled) .fa-trash-alt {
  transform: scale(1.2);
}

.btn-icon:hover:not(:disabled) .fa-chevron-down {
  transform: scale(1.2);
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

/* Status badges */
.status-badge {
  background-color: #444;
  color: white;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: bold;
  text-transform: uppercase;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  letter-spacing: 0.5px;
}

.status-badge.live {
  background-color: #e91916;
  animation: pulse 2s infinite;
  box-shadow: 0 1px 5px rgba(233, 25, 22, 0.5);
}

.recording-badge {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: bold;
  text-transform: uppercase;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  letter-spacing: 0.5px;
}

.recording-badge.recording {
  background-color: var(--success-color);
  color: white;
  animation: pulse 2s infinite;
}

.recording-badge.not-recording {
  background-color: var(--danger-color);
  color: white;
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
    gap: 12px;
  }
  
  .stream-compact-header {
    padding: 12px;
    gap: 10px;
    min-height: 80px;
  }
  
  .category-image-small {
    width: 50px;
    height: 65px;
  }
  
  .stream-thumbnail {
    width: 50px;
    height: 65px;
    margin-right: 12px;
  }
  
  .category-placeholder {
    width: 50px;
    height: 65px;
    font-size: 14px;
  }
  
  .stream-title {
    font-size: 1rem;
    -webkit-line-clamp: 2;
    line-clamp: 2;
  }
  
  .stream-meta {
    font-size: 0.75rem;
  }
  
  .stream-meta .category {
    max-width: 100px;
  }
  
  .quick-actions {
    gap: 2px;
  }
  
  .btn-icon {
    width: 28px;
    height: 28px;
    font-size: 0.7rem;
  }
  
  .modal-content {
    min-width: 320px;
    padding: 15px;
  }
}

@media (max-width: 480px) {
  .stream-list {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  
  .stream-card {
    min-width: 280px;
    max-width: calc(100vw - 40px);
    min-height: 180px; /* Taller on mobile */
  }
  
  .stream-compact-header {
    flex-direction: row;
    padding: 16px;
    min-height: 160px; /* Taller header on mobile */
    align-items: flex-start;
  }
  
  .stream-thumbnail {
    width: 65px;
    height: 90px;
    margin-right: 12px;
  }
  
  .category-image-small {
    width: 65px;
    height: 90px;
  }
  
  .category-placeholder {
    width: 65px;
    height: 90px;
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
    width: 40px;
    height: 40px;
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
