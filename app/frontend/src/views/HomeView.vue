<script setup lang="ts">
import StreamerList from '../components/StreamerList.vue'
import { onMounted, computed, ref } from 'vue'
import { useStreamers } from '@/composables/useStreamers'
import { useRecordingSettings } from '@/composables/useRecordingSettings'
import { useStreams } from '@/composables/useStreams'

const { streamers, fetchStreamers } = useStreamers()
const { activeRecordings, fetchActiveRecordings } = useRecordingSettings()
const totalStreamers = computed(() => streamers.value.length)
const liveStreamers = computed(() => streamers.value.filter(s => s.is_live).length)
const totalActiveRecordings = computed(() => activeRecordings.value.length)

// For last recording, fetch all streams and find the latest ended stream
const lastRecording = ref<any>(null)
const isLoadingLastRecording = ref(false)

async function fetchLastRecording() {
  isLoadingLastRecording.value = true
  let allStreams: any[] = []
  for (const streamer of streamers.value) {
    try {
      const response = await fetch(`/api/streamers/${streamer.id}/streams`)
      if (response.ok) {
        const data = await response.json()
        if (data.streams && Array.isArray(data.streams)) {
          allStreams = allStreams.concat(data.streams)
        }
      }
    } catch (e) {
      // ignore
    }
  }
  // Find the latest ended stream
  const endedStreams = allStreams.filter(s => s.ended_at)
  endedStreams.sort((a, b) => new Date(b.ended_at).getTime() - new Date(a.ended_at).getTime())
  lastRecording.value = endedStreams[0] || null
  isLoadingLastRecording.value = false
}

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
          </div>
          <div class="stat-item">
            <span class="stat-label">Last Recording</span>
            <span class="stat-value">
              <template v-if="isLoadingLastRecording">Loading...</template>
              <template v-else-if="lastRecording">
                {{ lastRecording.title || 'Untitled' }}<br />
                <small>{{ lastRecording.ended_at ? new Date(lastRecording.ended_at).toLocaleString() : '' }}</small>
              </template>
              <template v-else>No recordings found</template>
            </span>
          </div>
        </div>
      </div>
      <section class="content-section">
        <div class="page-header">
          <h2>Your Streamers</h2>
          <p class="description">Manage your tracked streamers and their recordings</p>
        </div>
        
        <StreamerList />
      </section>
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
  background: var(--background-tertiary, #f7f7fa);
  border-radius: 8px;
  padding: 1rem 1.5rem;
  box-shadow: 0 1px 4px rgba(0,0,0,0.03);
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: background 0.2s, box-shadow 0.2s;
}
.stat-item:nth-child(1) {
  background: linear-gradient(135deg, #3b82f6 0%, #60a5fa 100%);
  color: #fff;
}
.stat-item:nth-child(2) {
  background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
  color: #fff;
}
.stat-item:nth-child(3) {
  background: linear-gradient(135deg, #f59e42 0%, #fbbf24 100%);
  color: #fff;
}
.stat-item:nth-child(4) {
  background: linear-gradient(135deg, #6366f1 0%, #818cf8 100%);
  color: #fff;
}
.stat-label {
  font-size: 1rem;
  color: rgba(255,255,255,0.85);
  margin-bottom: 0.25rem;
  letter-spacing: 0.01em;
}
.stat-value {
  font-size: 1.3rem;
  font-weight: bold;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.08);
}
</style>
