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
        <span class="queue-count">{{ queueStats.active_tasks }}</span>
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
            <div v-for="task in activeTasks" :key="task.id" class="task-item">
              <div class="task-header">
                <span class="task-type">{{ formatTaskType(task.task_type) }}</span>
                <span class="task-streamer">{{ task.payload.streamer_name }}</span>
              </div>
              
              <div class="task-progress">
                <div class="progress-bar">
                  <div class="progress-fill" :style="{ width: `${task.progress}%` }"></div>
                </div>
                <span class="progress-text">{{ Math.round(task.progress) }}%</span>
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
            <div v-for="task in recentTasks.slice(0, 10)" :key="task.id" class="task-item">
              <div class="task-header">
                <span class="task-type">{{ formatTaskType(task.task_type) }}</span>
                <span class="task-streamer">{{ task.payload.streamer_name }}</span>
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

const { 
  activeTasks, 
  recentTasks, 
  queueStats, 
  hasActiveTasks, 
  totalProgress 
} = useBackgroundQueue()

const showPanel = ref(false)

const statusIconClass = computed(() => {
  if (queueStats.value.active_tasks > 0) return 'status-active'
  if (queueStats.value.failed_tasks > 0) return 'status-error'
  return 'status-idle'
})

const togglePanel = () => {
  showPanel.value = !showPanel.value
}

const formatTaskType = (taskType: string) => {
  const types: Record<string, string> = {
    'video_conversion': 'Video Conversion',
    'metadata_generation': 'Metadata',
    'chapters_generation': 'Chapters',
    'mp4_remux': 'MP4 Remux',
    'thumbnail_generation': 'Thumbnail',
    'cleanup': 'Cleanup'
  }
  return types[taskType] || taskType
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
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.queue-status-indicator:hover {
  background: rgba(255, 255, 255, 0.2);
}

.status-icon {
  width: 16px;
  height: 16px;
  transition: color 0.2s ease;
}

.status-icon.status-idle {
  color: #64748b;
}

.status-icon.status-active {
  color: #3b82f6;
  animation: pulse 2s infinite;
}

.status-icon.status-error {
  color: #ef4444;
}

.queue-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.queue-label {
  font-size: 12px;
  color: #94a3b8;
}

.queue-count {
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
}

.progress-bar {
  width: 40px;
  height: 4px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #3b82f6;
  transition: width 0.3s ease;
}

.queue-panel {
  position: absolute;
  top: 100%;
  right: 0;
  width: 400px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
  z-index: 1000;
  margin-top: 8px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #334155;
}

.panel-header h3 {
  margin: 0;
  color: #ffffff;
  font-size: 16px;
}

.close-btn {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 20px;
  cursor: pointer;
  padding: 4px;
}

.close-btn:hover {
  color: #ffffff;
}

.panel-content {
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}

.stats-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
}

.stat-label {
  font-size: 12px;
  color: #94a3b8;
}

.stat-value {
  font-weight: 600;
  color: #ffffff;
}

.text-green { color: #22c55e; }
.text-red { color: #ef4444; }
.text-yellow { color: #eab308; }

.active-tasks-section,
.recent-tasks-section {
  margin-bottom: 16px;
}

.active-tasks-section h4,
.recent-tasks-section h4 {
  margin: 0 0 8px 0;
  color: #ffffff;
  font-size: 14px;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-item {
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  border-left: 3px solid transparent;
}

.task-item.status-running {
  border-left-color: #3b82f6;
}

.task-item.status-completed {
  border-left-color: #22c55e;
}

.task-item.status-failed {
  border-left-color: #ef4444;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.task-type {
  font-weight: 600;
  color: #ffffff;
  font-size: 13px;
}

.task-streamer {
  color: #94a3b8;
  font-size: 12px;
}

.task-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.task-progress .progress-bar {
  flex: 1;
  height: 4px;
}

.progress-text {
  font-size: 12px;
  color: #94a3b8;
  min-width: 35px;
}

.task-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
}

.status-badge.status-pending {
  background: rgba(234, 179, 8, 0.2);
  color: #eab308;
}

.status-badge.status-running {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
}

.status-badge.status-completed {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.status-badge.status-failed {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.status-badge.status-retrying {
  background: rgba(249, 115, 22, 0.2);
  color: #f97316;
}

.task-time {
  font-size: 11px;
  color: #64748b;
}

.task-error {
  margin-top: 8px;
  padding: 8px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 4px;
  color: #ef4444;
  font-size: 12px;
}

.no-tasks {
  text-align: center;
  padding: 32px;
  color: #64748b;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
