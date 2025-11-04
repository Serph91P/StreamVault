<template>
  <div class="background-queue-monitor">
    <!-- Queue Status Indicator -->
    <div class="queue-status-indicator" @click="togglePanel">
      <div class="status-icon" :class="statusIconClass">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 2a6 6 0 100 12A6 6 0 008 2zM2 8a6 6 0 1112 0A6 6 0 012 8z"/>
          <path d="M8 4a.5.5 0 01.5.5v3h3a.5.5 0 010 1h-3v3a.5.5 0 01-1 0v-3h-3a.5.5 0 010-1h3v-3A.5.5 0 018 4z"/>
        </svg>
      </div>
      
      <div class="queue-info">
        <span class="queue-label">Jobs</span>
  <span class="queue-count">{{ combinedActiveTasks.length }}</span>
      </div>
      
      <!-- Progress Bar -->
      <div v-if="hasActiveTasks" class="progress-bar">
        <div class="progress-fill" :style="{ width: `${totalProgress}%` }"></div>
      </div>
    </div>

    <!-- Expandable Panel -->
    <div v-if="showPanel" class="queue-panel">
      <div class="panel-header">
        <h3>Background Jobs</h3>
        <button @click="togglePanel" class="close-btn">×</button>
      </div>
      
      <div class="panel-content">
        <!-- Queue Statistics -->
        <div class="stats-section">
          <div class="stat-item">
            <span class="stat-label">Total:</span>
            <span class="stat-value">{{ queueStats.total_tasks }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Completed:</span>
            <span class="stat-value text-green">{{ queueStats.completed_tasks }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Failed:</span>
            <span class="stat-value text-red">{{ queueStats.failed_tasks }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Pending:</span>
            <span class="stat-value text-yellow">{{ queueStats.pending_tasks }}</span>
          </div>
        </div>

        <!-- Active Tasks -->
    <div v-if="hasActiveTasks" class="active-tasks-section">
          <h4>Active Tasks</h4>
          <div class="task-list">
      <div v-for="task in combinedActiveTasks" :key="task.id" class="task-item status-border status-border-primary">
              <div class="task-header">
                <span class="task-type">{{ formatTaskType(task.task_type, task) }}</span>
                <span class="task-streamer">{{ getStreamerName(task) }}</span>
              </div>
              
              <div class="task-progress">
                <div v-if="task.task_type === 'recording'" class="recording-indicator">
                  <div class="pulse-indicator"></div>
                  <span class="recording-text">Recording Live</span>
                </div>
                <div v-else class="progress-bar">
                  <div class="progress-fill" :style="{ width: `${task.progress}%` }"></div>
                  <span class="progress-text">{{ Math.round(task.progress) }}%</span>
                </div>
              </div>
              
              <div class="task-status">
                <span class="status-badge" :class="getStatusClass(task.status)">
                  {{ task.status }}
                </span>
                <span class="task-time">{{ formatTime(task.started_at) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Recent Tasks -->
        <div v-if="recentTasks.length > 0" class="recent-tasks-section">
          <h4>Recent Tasks</h4>
          <div class="task-list">
            <div v-for="task in recentTasks.slice(0, 10)" :key="task.id" class="task-item status-border" :class="getStatusBorderClass(task.status)">
              <div class="task-header">
                <span class="task-type">{{ formatTaskType(task.task_type, task) }}</span>
                <span class="task-streamer">{{ getStreamerName(task) }}</span>
              </div>
              
              <div class="task-status">
                <span class="status-badge" :class="getStatusClass(task.status)">
                  {{ task.status }}
                </span>
                <span class="task-time">{{ formatTime(task.completed_at || task.started_at) }}</span>
              </div>
              
              <div v-if="task.error_message" class="task-error">
                {{ task.error_message }}
              </div>
            </div>
          </div>
        </div>

        <!-- No Tasks Message -->
        <div v-if="!hasActiveTasks && recentTasks.length === 0" class="no-tasks">
          <p>No background tasks running</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useBackgroundQueue } from '@/composables/useBackgroundQueue'
import { useSystemAndRecordingStatus } from '@/composables/useSystemAndRecordingStatus'

// Constants
const STALE_RECORDING_THRESHOLD_HOURS = 24; // Hours before a recording is considered stale

// Use WebSocket-only background queue
const {
  queueStats,
  activeTasks,
  recentTasks,
  isLoading,
  connectionStatus,
  forceRefreshFromAPI,
  cancelStreamTasks
} = useBackgroundQueue()

// Also track active recordings (they may not appear as queue tasks)
const { activeRecordings } = useSystemAndRecordingStatus()

// UI State
const showPanel = ref(false)

// Additional computed properties
// Helper to decide if a task should be treated as "active" in the UI
function isTaskActive(task: any): boolean {
  const activeStatuses = ['running', 'pending', 'retrying']
  if (activeStatuses.includes(task.status)) return true
  return false
}

// Merge active queue tasks with live recordings into a unified list for display (only truly active ones)
const combinedActiveTasks = computed(() => {
  // No time-based auto-pruning (24h+ streams should remain visible)

  // Use a map to avoid duplicates and prefer queue-provided tasks when available
  const map = new Map<string, any>()

  // 1. Add queue tasks
  for (const t of activeTasks.value) {
    // Filter out tasks that report completed/failed/etc. but are still in activeTasks because backend hasn't pruned
    if (!isTaskActive(t)) continue
    map.set(String(t.id), t)
  }

  // 2. Merge synthetic recording tasks for currently active recordings (exclude ones that seem finished/stale)
  for (const rec of activeRecordings.value) {
    const queueId = `recording_${rec.id}`

    // If recording status indicates completion (and we don't have explicit ended_at), treat as not active
    if (rec.status === 'completed' || rec.status === 'failed') continue

    // Filter out stale/zombie recordings older than threshold
    if (rec.started_at) {
      const recordingAge = Date.now() - new Date(rec.started_at).getTime()
      const maxAge = STALE_RECORDING_THRESHOLD_HOURS * 60 * 60 * 1000 // Convert hours to milliseconds
      if (recordingAge > maxAge) {
        console.debug(`Filtering out stale recording ${rec.id} (age: ${Math.round(recordingAge / 3600000)}h)`)
        continue
      }
    }


    // Avoid duplicates if queue already provides a recording task for this recording
    const existsById = map.has(queueId) || map.has(`recording-${rec.id}`)
    const existsByPayload = Array.from(map.values()).some(
      (t: any) => t.task_type === 'recording' && (t.payload?.recording_id === rec.id || t.recording_id === rec.id)
    )
    if (existsById || existsByPayload) continue

    map.set(queueId, {
      id: queueId,
      task_type: 'recording',
      status: 'running',
      progress: 0,
      created_at: rec.started_at,
      started_at: rec.started_at,
      payload: {
        streamer_name: rec.streamer_name,
        stream_id: rec.stream_id,
        recording_id: rec.id
      }
    } as any)
  }

  return Array.from(map.values())
})

const hasActiveTasks = computed(() => combinedActiveTasks.value.length > 0)
const isConnected = computed(() => connectionStatus.value === 'connected')

const totalProgress = computed(() => {
  if (!hasActiveTasks.value) return 0
  
  const valid = combinedActiveTasks.value.filter(t => typeof t.progress === 'number')
  if (valid.length === 0) return 0
  const total = valid.reduce((sum, task) => sum + (task.progress || 0), 0)
  return Math.round(total / valid.length)
})

const statusIconClass = computed(() => {
  if (isLoading.value) return 'status-loading'
  if (!isConnected.value) return 'status-error'
  if (queueStats.value.failed_tasks > 0) return 'status-error'
  if (hasActiveTasks.value) return 'status-active'
  return 'status-idle'
})

const togglePanel = () => {
  showPanel.value = !showPanel.value
  
  // Refresh data when panel is opened
  if (showPanel.value) {
    forceRefreshFromAPI() // Force refresh via API fallback
  }
}

const formatTaskType = (taskType: string, task?: any) => {
  const types: Record<string, string> = {
    'video_conversion': 'Video Conversion',
    'metadata_generation': 'Metadata',
    'chapters_generation': 'Chapters',
    'mp4_remux': 'MP4 Remux',
    'mp4_validation': 'MP4 Validation',
    'thumbnail_generation': 'Thumbnail',
    'cleanup': 'Cleanup',
  'file_cleanup': 'Cleanup',
  'segment_concatenation': 'Segment Concatenation',
    'recording': 'Recording Stream',
    'migration': 'Database Migration',
    'image_download': 'Image Download',
    'profile_image_sync': 'Profile Image Sync',
    'category_image_sync': 'Category Image Sync',
    'image_cleanup': 'Image Cleanup',
    'stream_processing': 'Stream Processing',
    'recording_post_processing': 'Recording Post-Processing',
    'file_conversion': 'File Conversion',
    'database_update': 'Database Update',
    'notification_send': 'Send Notification',
    'image_refresh': 'Image Refresh',
    'image_migration': 'Image Migration',
    'orphaned_recovery_check': 'Orphaned Recovery Check'
  }
  
  // If task type is empty/undefined, try to get it from task structure
  if (!taskType && task) {
    taskType = task.task_type || task.type || 'unknown'
  }
  
  return types[taskType] || (taskType ? taskType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Unknown Task')
}

const getStreamerName = (task: any) => {
  // Try multiple possible field names for streamer name
  return task.payload?.streamer_name || 
         task.streamer_name || 
         task.payload?.username ||
         task.username ||
         'Unknown'
}

const getStatusClass = (status: string) => {
  const classes: Record<string, string> = {
    'pending': 'status-pending',
    'running': 'status-running',
    'completed': 'status-completed',
    'failed': 'status-failed',
    'retrying': 'status-retrying'
  }
  return classes[status] || 'status-unknown'
}

// Map status to border class
const getStatusBorderClass = (status: string) => {
  if (status === 'completed') return 'status-border-success'
  if (status === 'failed') return 'status-border-error'
  if (status === 'running' || status === 'retrying') return 'status-border-primary'
  return 'status-border-secondary'
}

const formatTime = (timestamp?: string) => {
  if (!timestamp) return ''
  
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  if (diff < 60000) return 'just now'
  if (diff < 3600000) return `${Math.round(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.round(diff / 3600000)}h ago`
  
  return date.toLocaleDateString()
}
</script>

<style scoped>
.background-queue-monitor {
  position: relative;
}

.queue-status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: var(--border-radius, 8px);
  cursor: pointer;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  height: 36px;
  min-width: auto;
}

.queue-status-indicator:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.status-icon {
  width: 16px;
  height: 16px;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.status-icon.status-idle {
  color: var(--text-secondary);
}

.status-icon.status-active {
  color: var(--info-color);
  animation: pulse 2s infinite;
}

.status-icon.status-error {
  color: var(--danger-color);
}

.queue-info {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.queue-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.queue-count {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.progress-bar {
  width: 30px;
  height: 4px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: var(--border-radius-sm, 4px);
  overflow: hidden;
  flex-shrink: 0;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--info-color) 0%, var(--primary-color) 100%);
  transition: width 0.3s ease;
  border-radius: var(--border-radius-sm, 4px);
}

.queue-panel {
  position: absolute;
  top: 100%;
  right: 0;
  width: 450px;
  background: var(--background-card);
  border: 1px solid var(--color-border);
  border-radius: var(--border-radius-lg, 12px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
  z-index: 1000;
  margin-top: 12px;
  backdrop-filter: blur(10px);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.05);
  border-radius: var(--border-radius-lg, 12px) var(--border-radius-lg, 12px) 0 0;
}

.panel-header h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 24px;
  cursor: pointer;
  padding: 8px;
  border-radius: var(--border-radius, 8px);
  transition: all 0.2s ease;
}

.close-btn:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.1);
}

.panel-content {
  padding: 24px;
  max-height: 500px;
  overflow-y: auto;
}

.stats-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: var(--border-radius, 8px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
}

.stat-item:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateY(-1px);
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-weight: 700;
  color: var(--text-primary);
  font-size: 16px;
}

.text-green { color: var(--success-color); }
.text-red { color: var(--danger-color); }
.text-yellow { color: var(--warning-color); }

.active-tasks-section,
.recent-tasks-section {
  margin-bottom: 24px;
}

.active-tasks-section h4,
.recent-tasks-section h4 {
  margin: 0 0 16px 0;
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.active-tasks-section h4::before {
  content: "⚡";
  color: var(--info-color);
}

.recent-tasks-section h4::before {
  content: "📝";
  color: var(--text-secondary);
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-item {
  padding: 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: var(--border-radius, 8px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all var(--transition-base, 0.3s ease);
  /* Border colors handled by .status-border-* classes */
}

.task-item:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-type {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 14px;
}

.task-streamer {
  color: var(--text-secondary);
  font-size: 12px;
  background: rgba(255, 255, 255, 0.1);
  padding: 4px 8px;
  border-radius: var(--border-radius-sm, 4px);
}

.task-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.task-progress .progress-bar {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: var(--border-radius-sm, 4px);
}

.task-progress .progress-fill {
  background: linear-gradient(90deg, var(--info-color) 0%, var(--primary-color) 100%);
}

.progress-text {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 40px;
  font-weight: 600;
}

.task-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-badge {
  padding: 6px 12px;
  border-radius: var(--border-radius, 8px);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
}

.status-badge.status-pending {
  background: rgba(234, 179, 8, 0.2);
  color: var(--warning-color);
  border: 1px solid rgba(234, 179, 8, 0.3);
}

.status-badge.status-running {
  background: rgba(59, 130, 246, 0.2);
  color: var(--info-color);
  border: 1px solid rgba(59, 130, 246, 0.3);
  animation: pulse 2s infinite;
}

.status-badge.status-completed {
  background: rgba(40, 167, 69, 0.2);
  color: var(--success-color);
  border: 1px solid rgba(40, 167, 69, 0.3);
}

.status-badge.status-failed {
  background: rgba(220, 53, 69, 0.2);
  color: var(--danger-color);
  border: 1px solid rgba(220, 53, 69, 0.3);
}

.status-badge.status-retrying {
  background: rgba(249, 115, 22, 0.2);
  color: var(--warning-color);
  border: 1px solid rgba(249, 115, 22, 0.3);
}

.task-time {
  font-size: 11px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.1);
  padding: 4px 8px;
  border-radius: var(--border-radius-sm, 4px);
}

.task-error {
  margin-top: 12px;
  padding: 12px;
  background: rgba(220, 53, 69, 0.1);
  border-radius: var(--border-radius, 8px);
  color: var(--danger-color);
  font-size: 12px;
  border: 1px solid rgba(220, 53, 69, 0.2);
}

.no-tasks {
  text-align: center;
  padding: 48px 24px;
  color: var(--text-secondary);
}

.no-tasks p {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.recording-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(34, 197, 94, 0.1);
  border-radius: var(--border-radius, 8px);
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.pulse-indicator {
  width: 8px;
  height: 8px;
  background: var(--success-color);
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
}

.recording-text {
  color: var(--success-color);
  font-size: 12px;
  font-weight: 500;
}

/* Responsive Design */
@media (max-width: 768px) {
  .queue-status-indicator {
    padding: 6px 10px;
    gap: 6px;
    height: 32px;
    min-width: 60px;
  }
  
  .queue-label {
    font-size: 10px;
  }
  
  .queue-count {
    font-size: 12px;
  }
  
  .progress-bar {
    width: 25px;
    height: 3px;
  }
  
  .status-icon {
    width: 14px;
    height: 14px;
  }
  
  .queue-panel {
    width: 95vw;
    max-width: 400px;
    right: 50%;
    transform: translateX(50%);
  }
  
  .stats-section {
    grid-template-columns: 1fr;
  }
  
  .task-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .task-streamer {
    align-self: flex-end;
  }
}
</style>
