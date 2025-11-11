<template>
  <div class="status-dashboard">
    <!-- Header with connection status -->
    <div class="status-header">
      <h2>System Status</h2>
      <div class="connection-status">
        <div 
          class="status-indicator"
          :class="{
            'connected': isOnline,
            'disconnected': !isOnline,
            'loading': isLoading
          }"
        >
          <span class="status-dot"></span>
          <span class="status-text">
            {{ isOnline ? 'Connected' : 'Offline' }}
            {{ isLoading ? '(Updating...)' : '' }}
          </span>
        </div>
        <button 
          class="refresh-button"
          @click="handleRefresh"
          :disabled="isLoading"
          title="Force refresh status"
        >
          <RefreshIcon :class="{ spinning: isLoading }" />
        </button>
      </div>
    </div>

    <!-- Error display -->
    <div v-if="error" class="error-banner">
      <AlertIcon />
      <span>{{ error }}</span>
      <button @click="clearError" class="close-button">×</button>
    </div>

    <!-- Last update timestamp -->
    <div v-if="lastUpdate" class="last-update">
      Last updated: {{ formatTimestamp(lastUpdate) }}
    </div>

    <!-- System Overview Cards -->
    <div class="status-grid">
      <!-- Active Recordings Card -->
      <div class="status-card recording-card">
        <div class="card-header">
          <RecordIcon />
          <h3>Active Recordings</h3>
        </div>
        <div class="card-content">
          <div class="stat-number">{{ activeRecordingsCount }}</div>
          <div class="stat-label">Currently Recording</div>
          
          <!-- Recording List -->
          <div v-if="hasActiveRecordings" class="recording-list">
            <div 
              v-for="recording in activeRecordings" 
              :key="recording.id"
              class="recording-item status-border status-border-primary"
            >
              <div class="recording-info">
                <div class="streamer-name">{{ recording.streamer_name }}</div>
                <div class="recording-title">{{ recording.title || 'Untitled Stream' }}</div>
                <div class="recording-duration">
                  Duration: {{ formatDuration(recording.duration) }}
                </div>
              </div>
              <div 
                class="recording-status"
                :class="recording.status"
              >
                {{ recording.status }}
              </div>
            </div>
          </div>
          
          <div v-else class="no-recordings">
            No active recordings
          </div>
        </div>
      </div>

      <!-- System Stats Card -->
      <div class="status-card stats-card" v-if="systemStatus">
        <div class="card-header">
          <StatsIcon />
          <h3>System Statistics</h3>
        </div>
        <div class="card-content">
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-number">{{ systemStatus.total_streamers }}</div>
              <div class="stat-label">Total Streamers</div>
            </div>
            <div class="stat-item">
              <div class="stat-number">{{ systemStatus.live_streamers }}</div>
              <div class="stat-label">Live Streamers</div>
            </div>
            <div class="stat-item">
              <div class="stat-number">{{ systemStatus.active_recordings }}</div>
              <div class="stat-label">Recording Count</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Background Queue Card -->
      <div class="status-card queue-card" v-if="backgroundQueue">
        <div class="card-header">
          <QueueIcon />
          <h3>Background Tasks</h3>
        </div>
        <div class="card-content">
          <div class="queue-stats">
            <div class="stat-item">
              <div class="stat-number">{{ backgroundQueue.stats?.pending || 0 }}</div>
              <div class="stat-label">Pending</div>
            </div>
            <div class="stat-item">
              <div class="stat-number">{{ backgroundQueue.stats?.running || 0 }}</div>
              <div class="stat-label">Running</div>
            </div>
            <div class="stat-item">
              <div class="stat-number">{{ backgroundQueue.stats?.completed || 0 }}</div>
              <div class="stat-label">Completed</div>
            </div>
          </div>
          
          <!-- Active Tasks -->
          <div v-if="backgroundQueue.active_tasks?.length" class="active-tasks">
            <h4>Active Tasks</h4>
            <div 
              v-for="task in backgroundQueue.active_tasks" 
              :key="task.id"
              class="task-item"
            >
              <div class="task-name">{{ task.payload?.streamer_name || task.task_type || 'Unknown Task' }}</div>
              <div class="task-progress" v-if="task.progress !== undefined">
                Progress: {{ Math.round(task.progress) }}%
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="quick-actions">
      <button 
        class="action-button"
        @click="forceRefresh"
        :disabled="isLoading"
      >
        Force Refresh All
      </button>
      <button 
        class="action-button"
        @click="() => fetchActiveRecordings()"
        :disabled="isLoading"
      >
        Refresh Recordings
      </button>
      <button 
        class="action-button"
        @click="() => forceRefreshFromAPI()"
        :disabled="isLoading"
      >
        Refresh Queue
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSystemAndRecordingStatus } from '@/composables/useSystemAndRecordingStatus'
import { useBackgroundQueue } from '@/composables/useBackgroundQueue'

// Icons (you can replace these with your preferred icon library)
const RefreshIcon = { template: '<div class="icon refresh-icon">↻</div>' }
const AlertIcon = { template: '<div class="icon alert-icon">⚠</div>' }
const RecordIcon = { template: '<div class="icon record-icon">●</div>' }
const StatsIcon = { template: '<div class="icon stats-icon">📊</div>' }
const QueueIcon = { template: '<div class="icon queue-icon">📋</div>' }

// Use separate composables for different data
const {
  systemStatus,
  activeRecordings,
  isLoading: recordingsLoading,
  error: recordingsError,
  lastUpdate,
  isOnline,
  hasActiveRecordings,
  activeRecordingsCount,
  fetchActiveRecordings,
  forceRefresh
} = useSystemAndRecordingStatus()

// Use WebSocket-only background queue
const {
  queueStats,
  activeTasks,
  recentTasks,
  isLoading: queueLoading,
  connectionStatus,
  forceRefreshFromAPI
} = useBackgroundQueue()

// Combine loading states
const isLoading = computed(() => recordingsLoading.value || queueLoading.value)
const error = computed(() => recordingsError.value)

// Background queue computed properties for template compatibility
const backgroundQueue = computed(() => ({
  stats: {
    pending: queueStats.value.pending_tasks,
    running: queueStats.value.active_tasks,
    completed: queueStats.value.completed_tasks
  },
  active_tasks: activeTasks.value
}))

// Local state
const internalError = ref<string | null>(null)

// Computed
const displayError = computed(() => error.value || internalError.value)

// Methods
const handleRefresh = async () => {
  try {
    await forceRefresh()
    internalError.value = null
  } catch (err) {
    internalError.value = err instanceof Error ? err.message : 'Refresh failed'
  }
}

const clearError = () => {
  internalError.value = null
}

const formatTimestamp = (date: Date): string => {
  return new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(date)
}

const formatDuration = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  
  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`
  } else {
    return `${secs}s`
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.status-dashboard {
  padding: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-color);
}

.status-header h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.5rem;
  font-weight: 600;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.status-indicator.connected {
  background-color: rgba(34, 197, 94, 0.1);
  color: var(--success-color);
}

.status-indicator.disconnected {
  background-color: rgba(239, 68, 68, 0.1);
  color: var(--danger-color);
}

.status-indicator.loading {
  background-color: rgba(255, 193, 7, 0.1);
  color: var(--warning-color);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: currentColor;
}

.refresh-button {
  padding: 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background-color: var(--background-card);
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-button:hover:not(:disabled) {
  background-color: var(--background-darker);
  border-color: var(--text-secondary);
}

.refresh-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 0.375rem;
  color: var(--danger-color);
}

.close-button {
  margin-left: auto;
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  color: var(--danger-color);
}

.last-update {
  margin-bottom: 1.5rem;
  font-size: 0.875rem;
  color: var(--text-secondary);
  text-align: center;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.status-card {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.card-header h3 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.icon {
  font-size: 1.25rem;
}

.stat-number {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.stat-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 1rem;
}

.stat-item {
  text-align: center;
}

.recording-list {
  margin-top: 1rem;
  max-height: 300px;
  overflow-y: auto;
}

.recording-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  background-color: var(--background-darker);
  border-radius: 0.375rem;
  /* Border color handled by .status-border-* classes */
}

.recording-info {
  flex: 1;
}

.streamer-name {
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.25rem;
}

.recording-title {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
}

.recording-duration {
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.recording-status {
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: uppercase;
  background-color: var(--danger-color);
  color: white;
}

.no-recordings {
  text-align: center;
  color: var(--text-secondary);
  font-style: italic;
  padding: 2rem;
}

.queue-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-bottom: 1rem;
}

.active-tasks h4 {
  margin: 0 0 0.75rem 0;
  font-size: 1rem;
  color: var(--text-primary);
}

.task-item {
  padding: 0.5rem 0.75rem;
  background-color: var(--background-darker);
  border-radius: 0.375rem;
  margin-bottom: 0.5rem;
}

.task-name {
  font-weight: 500;
  color: var(--text-primary);
}

.task-progress {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.quick-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}

.action-button {
  padding: 0.75rem 1.5rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background-color: var(--background-card);
  color: var(--text-primary);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.action-button:hover:not(:disabled) {
  background-color: var(--background-darker);
  border-color: var(--text-secondary);
}

.action-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Responsive adjustments */
@include m.respond-below('md') {  // < 768px
  .status-dashboard {
    padding: 1rem;
  }
  
  .status-header {
    flex-direction: column;
    gap: 1rem;
    align-items: stretch;
  }
  
  .connection-status {
    justify-content: center;
  }
  
  .status-grid {
    grid-template-columns: 1fr;
  }
  
  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  
  .queue-stats {
    grid-template-columns: repeat(3, 1fr);
  }
  
  .quick-actions {
    flex-direction: column;
  }
}
</style>
