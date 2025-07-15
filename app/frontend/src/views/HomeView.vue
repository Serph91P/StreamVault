<script setup lang="ts">
import { onMounted, computed, ref, watch } from 'vue'
import { useStreamers } from '@/composables/useStreamers'
import { useRecordingSettings } from '@/composables/useRecordingSettings'
import { useStreams } from '@/composables/useStreams'
import { useWebSocket } from '@/composables/useWebSocket'

const { streamers, fetchStreamers, updateStreamer } = useStreamers()
const { activeRecordings, fetchActiveRecordings } = useRecordingSettings()
const { messages, connectionStatus } = useWebSocket()
const totalStreamers = computed(() => streamers.value.length)
const liveStreamers = computed(() => streamers.value.filter(s => s.is_live).length)
const totalActiveRecordings = computed(() => activeRecordings.value ? activeRecordings.value.length : 0)

// For last recording, fetch all streams and find the latest ended stream
const lastRecording = ref<any>(null)
const lastRecordingStreamer = ref<any>(null)
const isLoadingLastRecording = ref(false)

async function fetchLastRecording() {
  isLoadingLastRecording.value = true
  let allStreams: any[] = []
  for (const streamer of streamers.value) {
    try {
      const response = await fetch(`/api/streamers/${streamer.id}/streams`)
      if (response.ok) {
        const data = await response.json()
        if (data.streams && Array.isArray(data.streams)) {          // Add streamer info to each stream
          const streamsWithStreamer = data.streams.map((stream: any) => ({
            ...stream,
            streamer_name: streamer.username,
            streamer_id: streamer.id
          }))
          allStreams = allStreams.concat(streamsWithStreamer)
        }
      }
    } catch (e) {
      // ignore
    }
  }
  // Find the latest ended stream
  const endedStreams = allStreams.filter(s => s.ended_at)
  endedStreams.sort((a, b) => new Date(b.ended_at).getTime() - new Date(a.ended_at).getTime())
  const latestStream = endedStreams[0] || null
  lastRecording.value = latestStream
  if (latestStream) {
    lastRecordingStreamer.value = streamers.value.find(s => String(s.id) === String(latestStream.streamer_id))
  }
  isLoadingLastRecording.value = false
}

// WebSocket message handling
watch(messages, (newMessages) => {
  const message = newMessages[newMessages.length - 1]
  if (!message) return

  console.log('HomeView: New message detected:', message)

  switch (message.type) {
    case 'stream.online': {
      console.log('HomeView: Processing stream online:', message.data)
      updateStreamer(String(message.data.streamer_id), {
        is_live: true,
        title: message.data.title || '',
        category_name: message.data.category_name || '',
        language: message.data.language || '',
        last_updated: new Date().toISOString()
      })
      break
    }
    case 'stream.offline': {
      console.log('HomeView: Processing stream offline:', message.data)
      updateStreamer(String(message.data.streamer_id), {
        is_live: false,
        last_updated: new Date().toISOString()
      })
      break
    }
    case 'recording.started': {
      console.log('HomeView: Processing recording started:', message.data)
      const streamerId = Number(message.data.streamer_id)
      const streamer = streamers.value.find(s => String(s.id) === String(streamerId))
      if (streamer) {
        streamer.is_recording = true
      }
      // Refresh active recordings count
      fetchActiveRecordings()
      break
    }
    case 'recording.stopped': {
      console.log('HomeView: Processing recording stopped:', message.data)
      const streamerId = Number(message.data.streamer_id)
      const streamer = streamers.value.find(s => String(s.id) === String(streamerId))
      if (streamer) {
        streamer.is_recording = false
      }
      // Refresh active recordings count
      fetchActiveRecordings()
      break
    }
  }
}, { deep: true })

// Connection status handling
watch(connectionStatus, (status) => {
  if (status === 'connected') {
    void fetchStreamers()
    void fetchActiveRecordings()
  }
}, { immediate: true })

onMounted(async () => {
  await fetchStreamers()
  await fetchActiveRecordings()
  await fetchLastRecording()
})
</script>

<template>
  <div class="home-view">
    <div class="container">
      <div class="status-box">
        <h2>Dashboard</h2>
        <p>Welcome back to StreamVault! Here you can see the current status of your streamers and recordings.</p>
        <div class="dashboard-stats">
          <div class="stat-item">
            <span class="stat-label">Total Streamers</span>
            <span class="stat-value">{{ totalStreamers }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Live Streamers</span>
            <span class="stat-value">{{ liveStreamers }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Active Recordings</span>
            <span class="stat-value">{{ totalActiveRecordings }}</span>
          </div>          <div class="stat-item">
            <span class="stat-label">Last Recording</span>
            <span class="stat-value">
              <template v-if="isLoadingLastRecording">Loading...</template>
              <template v-else-if="lastRecording">
                <strong>{{ lastRecording.streamer_name }}</strong><br />
                {{ lastRecording.title || 'Untitled' }}<br />
                <small>{{ lastRecording.ended_at ? new Date(lastRecording.ended_at).toLocaleString() : '' }}</small>
              </template>
              <template v-else>No recordings found</template>
            </span>
          </div>
        </div>
        <div class="dashboard-actions">
          <router-link to="/streamers" class="btn btn-primary">Manage Streamers</router-link>
          <router-link to="/add-streamer" class="btn btn-secondary">Add New Streamer</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.status-box {
  background: var(--background-secondary);
  border-radius: var(--radius-md);
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  padding: 1.5rem 2rem;
  margin-bottom: 2rem;
  text-align: center;
}
.status-box h2 {
  margin-bottom: 0.5rem;
}
.dashboard-stats {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 2rem;
  margin-top: 1.5rem;
}
.stat-item {
  min-width: 160px;
  background: var(--background-card, #1f1f23);
  border-radius: var(--border-radius, 8px);
  padding: 1.2rem 1.7rem;
  box-shadow: var(--shadow-sm, 0 2px 4px rgba(0,0,0,0.12));
  display: flex;
  flex-direction: column;
  align-items: center;
  border: 1px solid var(--border-color, #2d2d35);
  transition: box-shadow 0.2s, transform 0.2s;
}
.stat-item:hover {
  box-shadow: var(--shadow-md, 0 4px 8px rgba(0,0,0,0.16));
  transform: translateY(-2px);
}
.stat-label {
  font-size: 1rem;
  color: var(--text-secondary, #b1b1b9);
  margin-bottom: 0.25rem;
  letter-spacing: 0.01em;
}
.stat-value {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--primary-color, #42b883);
  text-shadow: 0 1px 2px rgba(0,0,0,0.08);
}
.stat-item:last-child .stat-value {
  color: var(--accent-color, #7c4dff);
}

.dashboard-actions {
  margin-top: 2rem;
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .dashboard-actions {
    flex-direction: column;
  }
}
</style>
