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
      <div class="actions-container">        
        <button 
          v-if="!hasLiveStreams" 
          @click="forceOfflineRecording(parseInt(streamerId))" 
          class="btn btn-warning"
          :disabled="isStartingOfflineRecording"
        >
          {{ isStartingOfflineRecording ? 'Starting Recording...' : 'Force Recording (Offline Mode)' }}
        </button>
      </div>
      
      <div class="streams-summary">
        <p>Found {{ streams.length }} streams</p>
      </div>
      
      <div class="stream-list">
        <div v-for="stream in streams" 
             :key="stream.id"
             class="stream-card">
          <div class="stream-header">
            <div class="stream-info">
              <span class="status-badge" :class="{ 'live': !stream.ended_at }">
                {{ !stream.ended_at ? 'LIVE' : 'ENDED' }}
              </span>
              <span 
                v-if="!stream.ended_at" 
                class="recording-badge" 
                :class="isStreamRecording(parseInt(streamerId)) ? 'recording' : 'not-recording'"
              >
                {{ isStreamRecording(parseInt(streamerId)) ? 'RECORDING' : 'NOT RECORDING' }}
              </span>
              <h3>{{ formatDate(stream.started_at) }}</h3>
            </div>
          </div>
            <!-- Category Timeline - Show complete history if events are available -->
          <CategoryTimeline 
            v-if="stream.events && stream.events.length > 0"
            :events="stream.events"
            :stream-started="stream.started_at"
            :stream-ended="stream.ended_at"
          />
          
          <!-- Fallback: Simple category display if no events data -->
          <div v-else-if="stream.category_name" class="category-visual">
            <div class="category-image">
              <img :src="getCategoryImage(stream.category_name)" :alt="stream.category_name" />
            </div>
            <div class="category-name">{{ stream.category_name }}</div>
          </div>
          
          <div class="stream-content">
            <p><strong>Title:</strong> {{ stream.title || '-' }}</p>
            <p><strong>Duration:</strong> {{ calculateDuration(stream.started_at, stream.ended_at) }}</p>
            <p v-if="stream.ended_at"><strong>Ended:</strong> {{ formatDate(stream.ended_at) }}</p>
          </div>
          <div class="stream-actions">
            <div v-if="!stream.ended_at">
              <button 
                v-if="!isStreamRecording(parseInt(streamerId))" 
                @click="startRecording(parseInt(streamerId))" 
                class="btn btn-success" 
                :disabled="isStartingRecording"
              >
                {{ isStartingRecording ? 'Starting Recording...' : 'Force Record' }}
              </button>
              <button 
                v-else 
                @click="stopRecording(parseInt(streamerId))"
                class="btn btn-danger" 
                :disabled="isStoppingRecording"
              >
                {{ isStoppingRecording ? 'Stopping Recording...' : 'Stop Recording' }}
              </button>
            </div>
            
            <!-- Watch Video button for ended streams -->
            <button 
              v-if="stream.ended_at"
              @click="watchVideo(stream)" 
              class="btn btn-primary watch-btn"
            >
              Watch Video
            </button>
            
            <!-- Delete Stream button - disabled while stream is recording -->
            <button 
              @click="confirmDeleteStream(stream)" 
              class="btn btn-danger delete-btn" 
              :disabled="
                deletingStreamId === stream.id || 
                (!stream.ended_at && isStreamRecording(parseInt(streamerId)))
              "
            >
              <span v-if="deletingStreamId === stream.id" class="loader"></span>
              <span v-else>Delete Stream</span>
            </button>
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStreams } from '@/composables/useStreams'
import { useRecordingSettings } from '@/composables/useRecordingSettings'
import { useWebSocket } from '@/composables/useWebSocket'
import CategoryTimeline from './CategoryTimeline.vue'
const route = useRoute()
const router = useRouter()
const streamerId = computed(() => route.params.id as string || route.query.id as string)
const streamerName = computed(() => route.query.name as string)

const { streams, isLoading, fetchStreams } = useStreams()
const { activeRecordings, fetchActiveRecordings, stopRecording: stopStreamRecording } = useRecordingSettings()
const { messages } = useWebSocket()

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

// Daten laden
const loadStreams = async () => {
  if (streamerId.value) {
    await fetchStreams(streamerId.value);
    await fetchActiveRecordings();
    console.log("Loaded active recordings:", activeRecordings.value);
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

const getCategoryImage = (categoryName: string): string => {
  if (!categoryName) return '/images/default-category.png';
  
  // Replace spaces with hyphens and convert to lowercase for URL-friendly format
  const formattedName = categoryName.replace(/\s+/g, '-').toLowerCase();
  
  // Try to get the category image from Twitch's CDN
  // This is a common pattern for Twitch category box art
  return `https://static-cdn.jtvnw.net/ttv-boxart/${formattedName}-144x192.jpg`;
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
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.stream-card {
  background: #1f1f23;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
  transition: transform 0.2s;
}

.stream-card:hover {
  transform: translateY(-5px);
}

.stream-header {
  background: #18181b;
  padding: 15px;
  border-bottom: 1px solid #333;
}

.stream-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stream-info h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 500;
}

.status-badge {
  background-color: #444;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: bold;
}

.status-badge.live {
  background-color: #e91916;
  animation: pulse 2s infinite;
}

.recording-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: bold;
  margin-right: 0.5rem;
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

.stream-content {
  padding: 15px;
}

.stream-content p {
  margin: 8px 0;
}

.stream-actions {
  padding: 15px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.watch-btn {
  background-color: #007bff;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
}

.watch-btn:hover {
  background-color: #0056b3;
}

.delete-btn {
  margin-left: auto;
}

.offline-recording-section {
  margin-top: var(--spacing-lg);
  padding: var(--spacing-md);
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: var(--border-radius);
}

.help-text {
  margin-top: var(--spacing-sm);
  color: var(--text-muted-color);
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
}

.modal-content {
  background-color: #1f1f23;
  border-radius: 8px;
  padding: 20px;
  min-width: 400px;
  max-width: 90%;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.5);
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

.stream-details {
  background-color: #18181b;
  padding: 10px;
  border-radius: 4px;
  margin-bottom: 20px;
}

.stream-details p {
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

@keyframes pulse {
  0% {
    opacity: 0.8;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.8;
  }
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .stream-list {
    grid-template-columns: 1fr;
  }
  
  .stream-actions {
    flex-direction: column;
  }
  
  .delete-btn {
    margin-left: 0;
    margin-top: 10px;
  }
  
  .modal-content {
    min-width: 320px;
    padding: 15px;
  }
}

/* Add this to your existing CSS */
.category-visual {
  display: flex;
  align-items: center;
  padding: 10px 15px;
  background: rgba(24, 24, 27, 0.5);
  border-radius: 4px;
  margin: 0 15px 15px;
}

.category-image {
  width: 50px;
  height: 66px;
  overflow: hidden;
  border-radius: 4px;
  flex-shrink: 0;
  margin-right: 12px;
  background-color: #121214;
  display: flex;
  align-items: center;
  justify-content: center;
}

.category-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.2s ease;
}

.category-visual:hover .category-image img {
  transform: scale(1.1);
}

.category-name {
  font-weight: 500;
  color: #9146FF;
}

/* Adjust stream-content padding to account for the category visual */
.stream-content {
  padding-top: 0;
}

/* Grid layout adjustments for better fit with category visuals */
@media (min-width: 1024px) {
  .stream-list {
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  }
}
</style>
