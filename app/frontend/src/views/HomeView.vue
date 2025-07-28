<script setup lang="ts">
import { onMounted, computed, ref, watch } from 'vue'
import { useSystemAndRecordingStatus } from '@/composables/useSystemAndRecordingStatus'

// Use hybrid status system for comprehensive real-time updates
const {
  systemStatus,
  streamersStatus,
  activeRecordings,
  notificationsStatus,
  isLoading,
  error,
  fetchAllStatus,
  lastUpdate
} = useSystemAndRecordingStatus()

// Computed properties derived from hybrid status
const totalStreamers = computed(() => {
  if (!streamersStatus.value) return 0
  return streamersStatus.value.length
})

const liveStreamers = computed(() => {
  if (!streamersStatus.value) return 0
  return streamersStatus.value.filter(s => s.is_live).length
})

const totalActiveRecordings = computed(() => {
  if (!activeRecordings.value) return 0
  return activeRecordings.value.length
})

// For last recording - derived from streamers data
const lastRecording = ref<any>(null)
const lastRecordingStreamer = ref<any>(null)

// Function to derive last recording from streamers data
function updateLastRecording() {
  if (!streamersStatus.value || streamersStatus.value.length === 0) {
    lastRecording.value = null
    lastRecordingStreamer.value = null
    return
  }
  
  // Find the streamer with the most recent activity
  let mostRecentStreamer = null
  let mostRecentTime = null
  
  for (const streamer of streamersStatus.value) {
    if (streamer.last_seen) {
      const updateTime = new Date(streamer.last_seen)
      if (!mostRecentTime || updateTime > mostRecentTime) {
        mostRecentTime = updateTime
        mostRecentStreamer = streamer
      }
    }
  }
  
  if (mostRecentStreamer) {
    lastRecordingStreamer.value = mostRecentStreamer
    lastRecording.value = {
      id: `recent-${mostRecentStreamer.id}`,
      streamer_name: mostRecentStreamer.name,
      title: mostRecentStreamer.current_title || 'Recent Stream',
      ended_at: mostRecentStreamer.last_seen,
      streamer_id: mostRecentStreamer.id
    }
  } else {
    lastRecording.value = null
    lastRecordingStreamer.value = null
  }
}

// Watch for changes in streamers data to update last recording
watch(streamersStatus, () => {
  updateLastRecording()
}, { deep: true })

// Watch for system updates
watch(lastUpdate, () => {
  updateLastRecording()
})

onMounted(async () => {
  // Initial data fetch using hybrid status system
  await fetchAllStatus()
  updateLastRecording()
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
            <span class="stat-label">Most Recent Activity</span>
            <span class="stat-value">
              <template v-if="lastRecording">
                <strong>{{ lastRecording.streamer_name }}</strong><br />
                {{ lastRecording.title || 'Recent Stream' }}<br />
                <small>{{ lastRecording.ended_at ? new Date(lastRecording.ended_at).toLocaleString() : '' }}</small>
              </template>
              <template v-else>No recent activity</template>
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
