<template>
  <div class="logging-panel">
    <h2>Logging & Monitoring</h2>
    
    <!-- Logging Statistics -->
    <div class="stats-section content-section">
      <h3>Logging Statistics</h3>
      <div class="stats-grid">
        <div class="stat-card">
          <h4>Streamlink Logs</h4>
          <div class="stat-value">{{ stats.streamlink?.count || 0 }}</div>
          <div class="stat-size">{{ formatBytes(stats.streamlink?.total_size || 0) }}</div>
        </div>
        <div class="stat-card">
          <h4>FFmpeg Logs</h4>
          <div class="stat-value">{{ stats.ffmpeg?.count || 0 }}</div>
          <div class="stat-size">{{ formatBytes(stats.ffmpeg?.total_size || 0) }}</div>
        </div>
        <div class="stat-card">
          <h4>App Logs</h4>
          <div class="stat-value">{{ stats.app?.count || 0 }}</div>
          <div class="stat-size">{{ formatBytes(stats.app?.total_size || 0) }}</div>
        </div>
      </div>
    </div>

    <!-- Log Files -->
    <div class="logs-section content-section">
      <div class="section-header">
        <h3>Log Files</h3>
        <div class="actions">
          <button @click="refreshLogs" class="btn btn-secondary" :disabled="isLoading">
            <span v-if="isLoading" class="loader"></span>
            {{ isLoading ? 'Loading...' : 'Refresh' }}
          </button>
          <button @click="showCleanupDialog = true" class="btn btn-warning">
            Cleanup Old Logs
          </button>
        </div>
      </div>

      <!-- Log Type Tabs -->
      <div class="tabs">
        <button 
          v-for="logType in logTypes" 
          :key="logType"
          @click="activeTab = logType"
          :class="['tab', { active: activeTab === logType }]"
        >
          {{ logType.charAt(0).toUpperCase() + logType.slice(1) }} 
          ({{ getLogCount(logType) }})
        </button>
      </div>

      <!-- Log Files List -->
      <div class="log-files-list">
        <div v-if="getCurrentLogs().length === 0" class="no-logs">
          No {{ activeTab }} logs found
        </div>
        <div v-else>
          <div 
            v-for="logFile in getCurrentLogs().slice(0, showAllLogs ? undefined : 10)" 
            :key="logFile.filename"
            class="log-file-item"
          >
            <div class="file-info">
              <div class="filename">{{ logFile.filename }}</div>
              <div class="file-meta">
                <span class="size">{{ formatBytes(logFile.size) }}</span>
                <span class="date">{{ formatDate(logFile.last_modified) }}</span>
              </div>
            </div>
            <div class="file-actions">
              <button @click="viewLogFile(logFile)" class="btn btn-sm btn-secondary">
                View
              </button>
              <button @click="downloadLogFile(logFile)" class="btn btn-sm btn-primary">
                Download
              </button>
              <button @click="deleteLogFile(logFile)" class="btn btn-sm btn-danger">
                Delete
              </button>
            </div>
          </div>
          
          <div v-if="getCurrentLogs().length > 10 && !showAllLogs" class="show-more">
            <button @click="showAllLogs = true" class="btn btn-outline">
              Show {{ getCurrentLogs().length - 10 }} more files
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Log Viewer Modal -->
    <div v-if="showLogViewer" class="modal-overlay" @click="closeLogViewer">
      <div class="modal-content log-viewer-modal" @click.stop>
        <div class="modal-header">
          <h3>{{ viewingLogFile?.filename }}</h3>
          <div class="log-controls">
            <select v-model="tailLines" @change="refreshLogContent">
              <option value="50">Last 50 lines</option>
              <option value="100">Last 100 lines</option>
              <option value="500">Last 500 lines</option>
              <option value="1000">Last 1000 lines</option>
            </select>
            <button @click="refreshLogContent" class="btn btn-sm btn-secondary">
              Refresh
            </button>
          </div>
          <button @click="closeLogViewer" class="close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div class="log-content">
            <pre v-if="logContent">{{ logContent }}</pre>
            <div v-else-if="isLoadingContent" class="loading">Loading log content...</div>
            <div v-else class="no-content">No content available</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Cleanup Dialog -->
    <div v-if="showCleanupDialog" class="modal-overlay" @click="showCleanupDialog = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Cleanup Old Logs</h3>
          <button @click="showCleanupDialog = false" class="close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label for="daysToKeep">Keep logs for how many days?</label>
            <input 
              id="daysToKeep"
              type="number" 
              v-model="daysToKeep" 
              min="1" 
              max="365"
              class="input-field"
            >
            <div class="help-text">
              Logs older than {{ daysToKeep }} days will be permanently deleted.
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showCleanupDialog = false" class="btn btn-secondary">
            Cancel
          </button>
          <button @click="cleanupLogs" class="btn btn-danger" :disabled="isCleaningUp">
            <span v-if="isCleaningUp" class="loader"></span>
            {{ isCleaningUp ? 'Cleaning...' : 'Delete Old Logs' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'

interface LogFile {
  filename: string
  size: number
  last_modified: string
  type: string
}

interface LogStats {
  streamlink: { count: number; total_size: number }
  ffmpeg: { count: number; total_size: number }
  app: { count: number; total_size: number }
}

interface LogsData {
  streamlink_logs: LogFile[]
  ffmpeg_logs: LogFile[]
  app_logs: LogFile[]
  total_size: number
}

const isLoading = ref(false)
const isLoadingContent = ref(false)
const isCleaningUp = ref(false)
const stats = ref<LogStats>({} as LogStats)
const logsData = ref<LogsData>({} as LogsData)
const activeTab = ref('streamlink')
const showAllLogs = ref(false)
const showLogViewer = ref(false)
const showCleanupDialog = ref(false)
const viewingLogFile = ref<LogFile | null>(null)
const logContent = ref('')
const tailLines = ref(100)
const daysToKeep = ref(30)

const logTypes = ['streamlink', 'ffmpeg', 'app']

const getCurrentLogs = () => {
  switch (activeTab.value) {
    case 'streamlink':
      return logsData.value.streamlink_logs || []
    case 'ffmpeg':
      return logsData.value.ffmpeg_logs || []
    case 'app':
      return logsData.value.app_logs || []
    default:
      return []
  }
}

const getLogCount = (logType: string) => {
  switch (logType) {
    case 'streamlink':
      return logsData.value.streamlink_logs?.length || 0
    case 'ffmpeg':
      return logsData.value.ffmpeg_logs?.length || 0
    case 'app':
      return logsData.value.app_logs?.length || 0
    default:
      return 0
  }
}

const formatBytes = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString()
}

const fetchStats = async () => {
  try {
    const response = await fetch('/api/logging/stats')
    if (response.ok) {
      stats.value = await response.json()
    }
  } catch (error) {
    console.error('Error fetching logging stats:', error)
  }
}

const fetchLogs = async () => {
  try {
    isLoading.value = true
    const response = await fetch('/api/logging/files')
    if (response.ok) {
      logsData.value = await response.json()
    }
  } catch (error) {
    console.error('Error fetching log files:', error)
  } finally {
    isLoading.value = false
  }
}

const refreshLogs = async () => {
  await Promise.all([fetchStats(), fetchLogs()])
}

const viewLogFile = async (logFile: LogFile) => {
  viewingLogFile.value = logFile
  showLogViewer.value = true
  await refreshLogContent()
}

const refreshLogContent = async () => {
  if (!viewingLogFile.value) return
  
  try {
    isLoadingContent.value = true
    const response = await fetch(
      `/api/logging/files/${viewingLogFile.value.type}/${viewingLogFile.value.filename}/tail?lines=${tailLines.value}`
    )
    if (response.ok) {
      const data = await response.json()
      logContent.value = data.content
    }
  } catch (error) {
    console.error('Error fetching log content:', error)
    logContent.value = 'Error loading log content'
  } finally {
    isLoadingContent.value = false
  }
}

const downloadLogFile = async (logFile: LogFile) => {
  try {
    const response = await fetch(`/api/logging/files/${logFile.type}/${logFile.filename}`)
    if (response.ok) {
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = logFile.filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    }
  } catch (error) {
    console.error('Error downloading log file:', error)
    alert('Error downloading log file')
  }
}

const deleteLogFile = async (logFile: LogFile) => {
  if (!confirm(`Are you sure you want to delete ${logFile.filename}?`)) return
  
  try {
    const response = await fetch(`/api/logging/files/${logFile.type}/${logFile.filename}`, {
      method: 'DELETE'
    })
    if (response.ok) {
      await refreshLogs()
    } else {
      throw new Error('Failed to delete log file')
    }
  } catch (error) {
    console.error('Error deleting log file:', error)
    alert('Error deleting log file')
  }
}

const cleanupLogs = async () => {
  if (!confirm(`This will permanently delete all logs older than ${daysToKeep.value} days. Continue?`)) return
  
  try {
    isCleaningUp.value = true
    const response = await fetch(`/api/logging/cleanup?days_to_keep=${daysToKeep.value}`, {
      method: 'POST'
    })
    if (response.ok) {
      showCleanupDialog.value = false
      await refreshLogs()
      alert('Log cleanup completed successfully')
    } else {
      throw new Error('Failed to cleanup logs')
    }
  } catch (error) {
    console.error('Error cleaning up logs:', error)
    alert('Error cleaning up logs')
  } finally {
    isCleaningUp.value = false
  }
}

const closeLogViewer = () => {
  showLogViewer.value = false
  viewingLogFile.value = null
  logContent.value = ''
}

onMounted(() => {
  refreshLogs()
})
</script>

<style scoped>
.logging-panel {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.stats-section {
  margin-bottom: 2rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.stat-card {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  padding: 1.5rem;
  text-align: center;
}

.stat-card h4 {
  margin: 0 0 0.5rem 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
  font-weight: 500;
}

.stat-value {
  font-size: 2rem;
  font-weight: bold;
  color: var(--text-primary);
  margin-bottom: 0.25rem;
}

.stat-size {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
}

.tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 1.5rem;
}

.tab {
  padding: 0.75rem 1.5rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.tab:hover {
  color: var(--text-primary);
}

.tab.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
}

.log-files-list {
  max-height: 600px;
  overflow-y: auto;
}

.log-file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  margin-bottom: 0.5rem;
  background: var(--background-card);
}

.file-info {
  flex: 1;
}

.filename {
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 0.25rem;
}

.file-meta {
  display: flex;
  gap: 1rem;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.file-actions {
  display: flex;
  gap: 0.5rem;
}

.no-logs {
  text-align: center;
  color: var(--text-secondary);
  padding: 2rem;
}

.show-more {
  text-align: center;
  margin-top: 1rem;
}

.log-viewer-modal {
  width: 90vw;
  height: 80vh;
  max-width: none;
}

.log-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.log-controls select {
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  background: var(--background-primary);
  color: var(--text-primary);
}

.log-content {
  height: 60vh;
  overflow: auto;
  background: var(--background-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  padding: 1rem;
}

.log-content pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 0.8rem;
  line-height: 1.4;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.loading,
.no-content {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-secondary);
}

.modal-footer {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
}
</style>
