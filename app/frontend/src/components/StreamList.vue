<template>
  <div class="streams-container">
    <!-- Bestehendes Template -->
    <div v-if="isLoading" class="loading-container">
      <span>Loading streams...</span>
    </div>
    <div v-else-if="streams.length === 0" class="no-data-container">
      <p>No streams found for this streamer.</p>
      <button @click="handleBack" class="btn btn-primary back-btn">
        Back to streamers
      </button>
      
      <!-- Neue Schaltfläche für Force-Recording, auch wenn keine Streams gefunden wurden -->
      <button @click="forceOfflineRecording(parseInt(streamerId))" class="btn btn-warning mt-3">
        Force Recording (Offline Mode)
      </button>
    </div>
    <div v-else>
      <div class="back-btn-container">
        <button @click="handleBack" class="btn btn-primary back-btn">
          Back to streamers
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
              <!-- Recording-Status anzeigen, wenn live -->
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
          <div class="stream-content">
            <p><strong>Title:</strong> {{ stream.title || '-' }}</p>
            <p><strong>Category:</strong> {{ stream.category_name || '-' }}</p>
            <p><strong>Duration:</strong> {{ calculateDuration(stream.started_at, stream.ended_at) }}</p>
            <p v-if="stream.ended_at"><strong>Ended:</strong> {{ formatDate(stream.ended_at) }}</p>
          </div>
          <!-- Aktionsbuttons nur für Live-Streams anzeigen -->
          <div class="stream-actions" v-if="!stream.ended_at">
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
        </div>
      </div>
      
      <!-- Neue Schaltfläche für Force-Offline-Recording, wenn keine Live-Streams gefunden wurden -->
      <div v-if="!hasLiveStreams" class="mt-4">
        <button @click="forceOfflineRecording(parseInt(streamerId))" class="btn btn-warning">
          {{ isStartingOfflineRecording ? 'Starting Offline Recording...' : 'Force Recording (Offline Mode)' }}
        </button>
        <p class="text-muted mt-2">
          Use this option if the streamer is live but StreamVault didn't detect it automatically.
        </p>
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
const route = useRoute()
const router = useRouter()
const streamerId = computed(() => route.params.id as string || route.query.id as string)
const streamerName = computed(() => route.query.name as string)

const { streams, isLoading, fetchStreams } = useStreams()
const { activeRecordings, fetchActiveRecordings, stopRecording: stopStreamRecording } = useRecordingSettings()
const { messages } = useWebSocket()

// State für Aufnahmeaktionen
const isStartingRecording = ref(false)
const isStoppingRecording = ref(false)
const isStartingOfflineRecording = ref(false)
const localRecordingState = ref<Record<string, boolean>>({})

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

.back-btn-container {
  margin-bottom: 20px;
}

.back-btn {
  margin-right: 10px;
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
  background-color: #444;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: bold;
}

.recording-badge.recording {
  background-color: #2ecc71;
  animation: pulse 2s infinite;
}

.recording-badge.not-recording {
  background-color: #e74c3c;
}

.stream-content {
  padding: 15px;
}

.stream-content p {
  margin: 8px 0;
}

.stream-actions {
  padding: 0 15px 15px;
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
}
</style>
