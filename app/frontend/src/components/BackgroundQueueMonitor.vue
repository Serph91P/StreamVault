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
    'mp4_validation': 'MP4 Validation',
    'thumbnail_generation': 'Thumbnail',
    'cleanup': 'Cleanup',
    'recording': 'Recording Stream',
    'migration': 'Database Migration'
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
  border-radius: 6px;
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
  color: #aaa;
}

.status-icon.status-active {
  color: #3b82f6;
  animation: pulse 2s infinite;
}

.status-icon.status-error {
  color: #dc3545;
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
  color: #aaa;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.queue-count {
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
}

.progress-bar {
  width: 30px;
  height: 4px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
  overflow: hidden;
  flex-shrink: 0;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6 0%, #1d4ed8 100%);
  transition: width 0.3s ease;
  border-radius: 2px;
}

.queue-panel {
  position: absolute;
  top: 100%;
  right: 0;
  width: 450px;
  background: #1f1f23;
  border: 1px solid #333;
  border-radius: 12px;
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
  border-bottom: 1px solid #333;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px 12px 0 0;
}

.panel-header h3 {
  margin: 0;
  color: #ffffff;
  font-size: 18px;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  color: #aaa;
  font-size: 24px;
  cursor: pointer;
  padding: 8px;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.close-btn:hover {
  color: #ffffff;
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
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
}

.stat-item:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateY(-1px);
}

.stat-label {
  font-size: 13px;
  color: #aaa;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-weight: 700;
  color: #ffffff;
  font-size: 16px;
}

.text-green { color: #28a745; }
.text-red { color: #dc3545; }
.text-yellow { color: #eab308; }

.active-tasks-section,
.recent-tasks-section {
  margin-bottom: 24px;
}

.active-tasks-section h4,
.recent-tasks-section h4 {
  margin: 0 0 16px 0;
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.active-tasks-section h4::before {
  content: "⚡";
  color: #3b82f6;
}

.recent-tasks-section h4::before {
  content: "📝";
  color: #aaa;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-item {
  padding: 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-left: 4px solid transparent;
  transition: all 0.3s ease;
}

.task-item:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

.task-item.status-running {
  border-left-color: #3b82f6;
}

.task-item.status-completed {
  border-left-color: #28a745;
}

.task-item.status-failed {
  border-left-color: #dc3545;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-type {
  font-weight: 600;
  color: #ffffff;
  font-size: 14px;
}

.task-streamer {
  color: #aaa;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
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
  border-radius: 3px;
}

.task-progress .progress-fill {
  background: linear-gradient(90deg, #3b82f6 0%, #1d4ed8 100%);
}

.progress-text {
  font-size: 12px;
  color: #aaa;
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
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
}

.status-badge.status-pending {
  background: rgba(234, 179, 8, 0.2);
  color: #eab308;
  border: 1px solid rgba(234, 179, 8, 0.3);
}

.status-badge.status-running {
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
  border: 1px solid rgba(59, 130, 246, 0.3);
  animation: pulse 2s infinite;
}

.status-badge.status-completed {
  background: rgba(40, 167, 69, 0.2);
  color: #28a745;
  border: 1px solid rgba(40, 167, 69, 0.3);
}

.status-badge.status-failed {
  background: rgba(220, 53, 69, 0.2);
  color: #dc3545;
  border: 1px solid rgba(220, 53, 69, 0.3);
}

.status-badge.status-retrying {
  background: rgba(249, 115, 22, 0.2);
  color: #f97316;
  border: 1px solid rgba(249, 115, 22, 0.3);
}

.task-time {
  font-size: 11px;
  color: #aaa;
  background: rgba(255, 255, 255, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
}

.task-error {
  margin-top: 12px;
  padding: 12px;
  background: rgba(220, 53, 69, 0.1);
  border-radius: 6px;
  color: #dc3545;
  font-size: 12px;
  border: 1px solid rgba(220, 53, 69, 0.2);
}

.no-tasks {
  text-align: center;
  padding: 48px 24px;
  color: #aaa;
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
