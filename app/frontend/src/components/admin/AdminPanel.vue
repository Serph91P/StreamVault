<template>
  <div class="admin-panel">
    <div class="page-header">
      <h1>StreamVault Admin Panel</h1>
      <p class="subtitle">System Testing & Diagnostics</p>
    </div>

    <!-- Quick Health Check -->
    <GlassCard variant="medium" :padding="true" class="admin-section">
      <div class="section-header">
        <h2>System Health</h2>
        <button 
          @click="runQuickHealthCheck" 
          :disabled="healthCheckLoading"
          class="btn btn-primary"
        >
          <i class="fas fa-heartbeat"></i>
          {{ healthCheckLoading ? 'Checking...' : 'Quick Health Check' }}
        </button>
      </div>

      <div v-if="healthStatus" class="health-status status-border" :class="[healthStatus.overall_status, getHealthBorderClass(healthStatus.overall_status)]">
        <div class="status-indicator">
          <i :class="getHealthIcon(healthStatus.overall_status)"></i>
          <span class="status-text">{{ healthStatus.overall_status.toUpperCase() }}</span>
          <span class="timestamp">{{ formatTime(healthStatus.timestamp) }}</span>
        </div>
        
        <div class="health-legend">
          <div class="legend-item">
            <i class="fas fa-check-circle text-green"></i> Healthy
          </div>
          <div class="legend-item">
            <i class="fas fa-exclamation-triangle text-yellow"></i> Warning
          </div>
          <div class="legend-item">
            <i class="fas fa-times-circle text-red"></i> Error
          </div>
        </div>
        
        <div class="health-checks">
          <div 
            v-for="(check, name) in healthStatus.checks" 
            :key="name"
            class="health-check status-border"
            :class="[check.status, getHealthBorderClass(check.status)]"
          >
            <i :class="getHealthIcon(check.status)"></i>
            <span class="check-name">{{ formatCheckName(String(name)) }}</span>
            <span class="check-message">{{ check.message }}</span>
          </div>
        </div>
      </div>
    </GlassCard>

    <!-- System Information -->
    <GlassCard variant="medium" :padding="true" class="admin-section">
      <div class="section-header">
        <h2>System Information</h2>
        <button @click="loadSystemInfo" :disabled="systemInfoLoading" class="btn btn-secondary">
          <i class="fas fa-info-circle"></i>
          {{ systemInfoLoading ? 'Loading...' : 'Refresh Info' }}
        </button>
      </div>

      <div v-if="systemInfo" class="system-info-grid">
        <div class="info-card status-border status-border-info">
          <h3>System</h3>
          <ul>
            <li><strong>Platform:</strong> {{ systemInfo.system.platform }}</li>
            <li><strong>Python:</strong> {{ systemInfo.system.python_version }}</li>
            <li><strong>Architecture:</strong> {{ systemInfo.system.architecture }}</li>
          </ul>
        </div>

        <div class="info-card">
          <h3>Resources</h3>
          <ul>
            <li><strong>CPU Cores:</strong> {{ systemInfo.resources.cpu_count }}</li>
            <li><strong>CPU Usage:</strong> {{ systemInfo.resources.cpu_percent }}%</li>
            <li><strong>Memory:</strong> {{ systemInfo.resources.memory.available_gb }}GB / {{ systemInfo.resources.memory.total_gb }}GB available</li>
          </ul>
        </div>

        <div class="info-card">
          <h3>Storage</h3>
          <div v-if="systemInfo.storage.recording_drive">
            <ul>
              <li><strong>Recording Drive:</strong></li>
              <li>Total: {{ systemInfo.storage.recording_drive.total_gb }}GB</li>
              <li>Free: {{ systemInfo.storage.recording_drive.free_gb }}GB</li>
              <li>Used: {{ systemInfo.storage.recording_drive.percent_used }}%</li>
            </ul>
          </div>
          <div v-else-if="systemInfo.storage.error" class="error">
            Error: {{ systemInfo.storage.error }}
          </div>
        </div>

        <div class="info-card">
          <h3>Configuration</h3>
          <ul>
            <li><strong>Recording Dir:</strong> {{ systemInfo.settings.recording_directory }}</li>
            <li><strong>VAPID Keys:</strong> {{ systemInfo.settings.vapid_configured ? 'Configured' : 'Not Configured' }}</li>
            <li><strong>Proxy:</strong> {{ systemInfo.settings.proxy_configured ? 'Configured' : 'Direct Connection' }}</li>
          </ul>
        </div>
      </div>
    </GlassCard>

    <!-- WebSocket Monitoring -->
    <GlassCard variant="medium" :padding="true" class="admin-section">
      <div class="section-header">
        <h2>WebSocket Connections</h2>
      </div>
      <WebSocketMonitor />
    </GlassCard>

    <!-- Background Queue Monitoring -->
    <GlassCard variant="medium" :padding="true" class="admin-section">
      <div class="section-header">
        <h2>Background Jobs & Services</h2>
        <p class="section-description">Real-time monitoring of background tasks, recording services, and system processes</p>
      </div>
      <BackgroundQueueMonitor />
    </GlassCard>

    <!-- Background Queue Management & Cleanup -->
    <GlassCard variant="medium" :padding="true" class="admin-section">
      <div class="section-header">
        <h2>🔧 Background Queue Management</h2>
        <p class="section-description">
          Fix Background Queue Problems: Stuck Recording Jobs, Continuous Orphaned Recovery, Unknown Task Names
        </p>
      </div>
      <BackgroundQueueAdmin />
    </GlassCard>

    <!-- Post-Processing Management -->
    <GlassCard variant="medium" :padding="true" class="admin-section">
      <div class="section-header">
        <h2>🔄 Post-Processing Management</h2>
        <p class="section-description">
          Manual Post-Processing for Failed Recordings and Cleanup of Orphaned Files
        </p>
      </div>
      <PostProcessingManagement />
    </GlassCard>

    <!-- Test Suite -->
    <GlassCard variant="medium" :padding="true" class="admin-section">
      <div class="section-header">
        <h2>Comprehensive Test Suite</h2>
        <div class="test-controls">
          <button @click="runAllTests" :disabled="testsLoading" class="btn btn-success">
            <i class="fas fa-play"></i>
            {{ testsLoading ? 'Running Tests...' : 'Run All Tests' }}
          </button>
          <button @click="loadAvailableTests" class="btn btn-secondary">
            <i class="fas fa-list"></i>
            Show Available Tests
          </button>
        </div>
      </div>

      <!-- Test Progress -->
      <div v-if="testsLoading" class="test-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{width: '50%'}"></div>
        </div>
        <p>Running comprehensive tests...</p>
      </div>

      <!-- Test Results -->
      <div v-if="testResults" class="test-results">
        <div class="results-summary">
          <h3 class="summary-title">Test Results Summary</h3>
          <div class="summary-stats">
            <div class="stat passed">
              <i class="fas fa-check-circle"></i>
              <span class="count">{{ testResults.passed }}</span>
              <span class="label">Passed</span>
            </div>
            <div class="stat failed">
              <i class="fas fa-times-circle"></i>
              <span class="count">{{ testResults.failed }}</span>
              <span class="label">Failed</span>
            </div>
            <div class="stat total">
              <i class="fas fa-clipboard-list"></i>
              <span class="count">{{ testResults.total_tests }}</span>
              <span class="label">Total</span>
            </div>
            <div class="stat success-rate">
              <i class="fas fa-percentage"></i>
              <span class="count">{{ Math.round(testResults.success_rate) }}%</span>
              <span class="label">Success Rate</span>
            </div>
          </div>
        </div>

        <div class="detailed-results">
          <div class="results-filters">
            <button 
              @click="resultFilter = 'all'"
              :class="{active: resultFilter === 'all'}"
              class="filter-btn"
            >
              All ({{ testResults.results.length }})
            </button>
            <button 
              @click="resultFilter = 'failed'"
              :class="{active: resultFilter === 'failed'}"
              class="filter-btn"
            >
              Failed ({{ testResults.results.filter((r: any) => !r.success).length }})
            </button>
            <button 
              @click="resultFilter = 'passed'"
              :class="{active: resultFilter === 'passed'}"
              class="filter-btn"
            >
              Passed ({{ testResults.results.filter((r: any) => r.success).length }})
            </button>
          </div>

          <div class="test-results-list">
            <div 
              v-for="result in filteredResults" 
              :key="result.test_name"
              class="test-result-item status-border"
              :class="[
                result.success ? 'passed' : 'failed',
                result.success ? 'status-border-success' : 'status-border-error'
              ]"
            >
              <div class="result-header">
                <i :class="result.success ? 'fas fa-check-circle' : 'fas fa-times-circle'"></i>
                <span class="test-name">{{ formatTestName(result.test_name) }}</span>
                <span class="test-time">{{ formatTime(result.timestamp) }}</span>
              </div>
              <div class="result-message">{{ result.message }}</div>
              <div v-if="result.details && Object.keys(result.details).length > 0" class="result-details">
                <button @click="toggleDetails(result.test_name)" class="details-toggle">
                  <i :class="expandedDetails.includes(result.test_name) ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
                  Details
                </button>
                <div v-if="expandedDetails.includes(result.test_name)" class="details-content">
                  <pre>{{ JSON.stringify(result.details, null, 2) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Available Tests -->
      <div v-if="availableTests && showAvailableTests" class="available-tests">
        <h3>Available Test Categories</h3>
        <div class="test-categories">
          <div v-for="(tests, category) in availableTests" :key="category" class="test-category">
            <h4>{{ formatCategoryName(String(category)) }}</h4>
            <ul>
              <li v-for="test in tests" :key="test">{{ formatTestName(test) }}</li>
            </ul>
          </div>
        </div>
      </div>
    </GlassCard>

    <!-- Maintenance -->
    <GlassCard variant="medium" :padding="true" class="admin-section">
      <div class="section-header">
        <h2>Maintenance</h2>
      </div>

      <div class="maintenance-actions">
        <button @click="cleanupTempFiles" :disabled="cleanupLoading" class="btn btn-warning">
          <i class="fas fa-broom"></i>
          {{ cleanupLoading ? 'Cleaning...' : 'Cleanup Temp Files' }}
        </button>
        
        <button @click="viewLogs" class="btn btn-info">
          <i class="fas fa-file-alt"></i>
          View Recent Logs
        </button>
      </div>

      <div v-if="cleanupResult" class="cleanup-result status-border status-border-success">
        <h4>Cleanup Results</h4>
        <ul>
          <li>Files removed: {{ cleanupResult.files_removed }}</li>
          <li>Space freed: {{ cleanupResult.space_freed_mb }}MB</li>
          <li v-if="cleanupResult.errors.length > 0">
            Errors: {{ cleanupResult.errors.length }}
            <ul class="error-list">
              <li v-for="error in cleanupResult.errors" :key="error">{{ error }}</li>
            </ul>
          </li>
        </ul>
      </div>
    </GlassCard>

    <!-- Video Debug Section -->
    <GlassCard variant="medium" :padding="true" class="admin-section">
      <div class="section-header">
        <h2>Video & Recording Debug</h2>
        <p class="section-description">Debug video availability and recording file system status</p>
      </div>

      <div class="debug-actions">
        <button @click="loadVideosDebug" :disabled="videosDebugLoading" class="btn btn-info">
          <i class="fas fa-database"></i>
          {{ videosDebugLoading ? 'Loading...' : 'Check Videos Database' }}
        </button>
        
        <button @click="loadRecordingsDirectory" :disabled="recordingsDirectoryLoading" class="btn btn-secondary">
          <i class="fas fa-folder-open"></i>
          {{ recordingsDirectoryLoading ? 'Loading...' : 'Scan Recordings Directory' }}
        </button>
        
        <button @click="fixRecordingAvailability" :disabled="fixingRecordings" class="btn btn-warning">
          <i class="fas fa-wrench"></i>
          {{ fixingRecordings ? 'Fixing...' : 'Fix Recording Paths' }}
        </button>
        
        <button @click="cleanupOrphanedRecordings" :disabled="cleaningOrphaned" class="btn btn-danger">
          <i class="fas fa-broom"></i>
          {{ cleaningOrphaned ? 'Cleaning...' : 'Cleanup Orphaned DB' }}
        </button>
        
        <button @click="cleanupProcessOrphanedRecordings" :disabled="cleaningProcessOrphaned" class="btn btn-danger">
          <i class="fas fa-broom"></i>
          {{ cleaningProcessOrphaned ? 'Cleaning...' : 'Cleanup Process Orphaned' }}
        </button>
        
        <button @click="cleanupZombieRecordings" :disabled="cleaningZombies" class="btn btn-warning">
          <i class="fas fa-ghost"></i>
          {{ cleaningZombies ? 'Cleaning...' : 'Cleanup Zombie Recordings' }}
        </button>
      </div>
    </GlassCard>

    <!-- Logs Modal -->
    <div v-if="showLogsModal" class="modal-overlay" @click="showLogsModal = false">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h3>Recent Logs</h3>
          <button @click="showLogsModal = false" class="close-btn">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="modal-body">
          <div class="log-controls">
            <select v-model="logLevel" @change="loadLogs">
              <option value="ALL">All Levels</option>
              <option value="ERROR">Errors Only</option>
              <option value="WARNING">Warnings</option>
              <option value="INFO">Info</option>
              <option value="DEBUG">Debug</option>
            </select>
            <input v-model="logLines" @change="loadLogs" type="number" min="50" max="1000" step="50">
            <button @click="loadLogs" class="btn btn-sm btn-primary">Refresh</button>
          </div>
          <div class="logs-content">
            <pre v-if="logs">{{ logs.logs.join('\n') }}</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- Videos Debug Modal -->
    <div v-if="showVideosDebugModal" class="modal-overlay" @click="showVideosDebugModal = false">
      <div class="modal videos-debug-modal" @click.stop>
        <div class="modal-header">
          <h3>Videos Database Debug</h3>
          <button @click="showVideosDebugModal = false" class="close-btn">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="videosDebugData" class="debug-content">
            <!-- Summary -->
            <div class="debug-section">
              <h4>Summary</h4>
              <div class="summary-stats">
                <div class="stat">
                  <span class="count">{{ videosDebugData.summary.total_streams }}</span>
                  <span class="label">Total Streams</span>
                </div>
                <div class="stat">
                  <span class="count">{{ videosDebugData.summary.total_recordings }}</span>
                  <span class="label">Total Recordings</span>
                </div>
                <div class="stat">
                  <span class="count">{{ videosDebugData.summary.streams_with_recording_path }}</span>
                  <span class="label">Streams with Path</span>
                </div>
                <div class="stat">
                  <span class="count">{{ videosDebugData.summary.mp4_files_found }}</span>
                  <span class="label">MP4 Files Found</span>
                </div>
              </div>
            </div>

            <!-- Streams -->
            <div class="debug-section">
              <h4>Recent Streams ({{ videosDebugData.streams.length }})</h4>
              <div class="debug-table">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Streamer</th>
                      <th>Title</th>
                      <th>Recording Path</th>
                      <th>File Exists</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="stream in videosDebugData.streams.slice(0, 10)" :key="stream.id">
                      <td>{{ stream.id }}</td>
                      <td>{{ stream.streamer_name }}</td>
                      <td>{{ stream.title || 'N/A' }}</td>
                      <td class="path-cell">{{ stream.recording_path || 'None' }}</td>
                      <td>
                        <span v-if="stream.recording_path_exists" class="text-green">
                          <i class="fas fa-check"></i> Yes
                        </span>
                        <span v-else-if="stream.recording_path" class="text-red">
                          <i class="fas fa-times"></i> No
                        </span>
                        <span v-else class="text-gray">N/A</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Recordings -->
            <div class="debug-section">
              <h4>Recent Recordings ({{ videosDebugData.recordings.length }})</h4>
              <div class="debug-table">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Stream ID</th>
                      <th>Streamer</th>
                      <th>Status</th>
                      <th>TS File</th>
                      <th>MP4 File</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="recording in videosDebugData.recordings.slice(0, 10)" :key="recording.id">
                      <td>{{ recording.id }}</td>
                      <td>{{ recording.stream_id }}</td>
                      <td>{{ recording.streamer_name }}</td>
                      <td>{{ recording.status }}</td>
                      <td>
                        <span v-if="recording.ts_path_exists" class="text-green">
                          <i class="fas fa-check"></i>
                        </span>
                        <span v-else class="text-red">
                          <i class="fas fa-times"></i>
                        </span>
                      </td>
                      <td>
                        <span v-if="recording.mp4_path_exists" class="text-green">
                          <i class="fas fa-check"></i>
                        </span>
                        <span v-else class="text-red">
                          <i class="fas fa-times"></i>
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Recordings Directory Modal -->
    <div v-if="showRecordingsDirectoryModal" class="modal-overlay" @click="showRecordingsDirectoryModal = false">
      <div class="modal recordings-directory-modal" @click.stop>
        <div class="modal-header">
          <h3>Recordings Directory Scan</h3>
          <button @click="showRecordingsDirectoryModal = false" class="close-btn">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="recordingsDirectoryData" class="debug-content">
            <div v-if="recordingsDirectoryData.base_recordings_dir_exists">
              <div class="debug-section">
                <h4>Streamer Directories</h4>
                <div v-for="streamer in recordingsDirectoryData.directories" :key="streamer.name" class="streamer-section status-border status-border-primary">
                  <h5>{{ streamer.name }} ({{ streamer.total_files }} files, {{ streamer.total_size_mb }}MB)</h5>
                  <div v-for="season in streamer.subdirectories" :key="season.name" class="season-section">
                    <h6>{{ season.name }} ({{ season.file_count }} files, {{ season.total_size_mb }}MB)</h6>
                    <div class="files-list">
                      <div v-for="file in season.files.slice(0, 5)" :key="file.name" class="file-item">
                        <span class="file-name">{{ file.name }}</span>
                        <span class="file-size">{{ file.size_mb }}MB</span>
                        <span class="file-ext" :class="file.extension">{{ file.extension }}</span>
                      </div>
                      <div v-if="season.files.length > 5" class="more-files">
                        ... and {{ season.files.length - 5 }} more files
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="error">
              Recording directory {{ recordingsDirectoryData.base_recordings_dir }} does not exist!
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import GlassCard from '../cards/GlassCard.vue'
import WebSocketMonitor from '../WebSocketMonitor.vue'
import BackgroundQueueMonitor from '../BackgroundQueueMonitor.vue'
import BackgroundQueueAdmin from './BackgroundQueueAdmin.vue'
import PostProcessingManagement from './PostProcessingManagement.vue'

// Reactive data
const healthStatus = ref<any>(null)
const healthCheckLoading = ref(false)
const systemInfo = ref<any>(null)
const systemInfoLoading = ref(false)
const testResults = ref<any>(null)
const testsLoading = ref(false)
const availableTests = ref<any>(null)
const showAvailableTests = ref(false)
const cleanupResult = ref<any>(null)
const cleanupLoading = ref(false)
const showLogsModal = ref(false)
const logs = ref<any>(null)
const logLevel = ref('INFO')
const logLines = ref(200)
const resultFilter = ref('all')
const expandedDetails = ref<string[]>([])

// Video Debug data
const videosDebugData = ref<any>(null)
const videosDebugLoading = ref(false)
const recordingsDirectoryData = ref<any>(null)
const recordingsDirectoryLoading = ref(false)
const showVideosDebugModal = ref(false)
const fixingRecordings = ref(false)
const cleaningOrphaned = ref(false)
const cleaningProcessOrphaned = ref(false)
const cleaningZombies = ref(false)
const showRecordingsDirectoryModal = ref(false)

// Computed
const filteredResults = computed(() => {
  if (!testResults.value) return []
  
  const results = testResults.value.results
  switch (resultFilter.value) {
    case 'passed':
      return results.filter((r: any) => r.success)
    case 'failed':
      return results.filter((r: any) => !r.success)
    default:
      return results
  }
})

// Methods
const runQuickHealthCheck = async () => {
  healthCheckLoading.value = true
  try {
    const response = await fetch('/api/admin/tests/quick-health', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    healthStatus.value = await response.json()
  } catch (error) {
    console.error('Health check failed:', error)
  } finally {
    healthCheckLoading.value = false
  }
}

const loadSystemInfo = async () => {
  systemInfoLoading.value = true
  try {
    const response = await fetch('/api/admin/system/info', {
      credentials: 'include'
    })
    systemInfo.value = await response.json()
  } catch (error) {
    console.error('Failed to load system info:', error)
  } finally {
    systemInfoLoading.value = false
  }
}

const runAllTests = async () => {
  testsLoading.value = true
  try {
    const response = await fetch('/api/admin/tests/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({})
    })
    testResults.value = await response.json()
  } catch (error) {
    console.error('Tests failed:', error)
  } finally {
    testsLoading.value = false
  }
}

const loadAvailableTests = async () => {
  try {
    const response = await fetch('/api/admin/tests/available', {
      credentials: 'include'
    })
    availableTests.value = await response.json()
    showAvailableTests.value = !showAvailableTests.value
  } catch (error) {
    console.error('Failed to load available tests:', error)
  }
}

const cleanupTempFiles = async () => {
  cleanupLoading.value = true
  try {
    const response = await fetch('/api/admin/maintenance/cleanup-temp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include'
    })
    cleanupResult.value = await response.json()
  } catch (error) {
    console.error('Cleanup failed:', error)
  } finally {
    cleanupLoading.value = false
  }
}

const viewLogs = async () => {
  showLogsModal.value = true
  await loadLogs()
}

const loadLogs = async () => {
  try {
    const response = await fetch(`/api/admin/logs/recent?lines=${logLines.value}&level=${logLevel.value}`, {
      credentials: 'include' // CRITICAL: Required to send session cookie
    })
    logs.value = await response.json()
  } catch (error) {
    console.error('Failed to load logs:', error)
  }
}

const toggleDetails = (testName: string) => {
  const index = expandedDetails.value.indexOf(testName)
  if (index > -1) {
    expandedDetails.value.splice(index, 1)
  } else {
    expandedDetails.value.push(testName)
  }
}

// Video Debug Methods
const loadVideosDebug = async () => {
  videosDebugLoading.value = true
  try {
    const response = await fetch('/api/admin/debug/videos-database', {
      credentials: 'include'
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    const result = await response.json()
    videosDebugData.value = result.data
    showVideosDebugModal.value = true
  } catch (error) {
    console.error('Failed to load videos debug:', error)
    alert('Failed to load videos debug data')
  } finally {
    videosDebugLoading.value = false
  }
}

const loadRecordingsDirectory = async () => {
  recordingsDirectoryLoading.value = true
  try {
    const response = await fetch('/api/admin/debug/recordings-directory', {
      credentials: 'include'
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    const result = await response.json()
    recordingsDirectoryData.value = result.data
    showRecordingsDirectoryModal.value = true
  } catch (error) {
    console.error('Failed to load recordings directory:', error)
    alert('Failed to load recordings directory data')
  } finally {
    recordingsDirectoryLoading.value = false
  }
}

// Recording Fix Methods
const fixRecordingAvailability = async () => {
  if (!confirm('This will scan all streams and fix recording_path fields based on actual files. Continue?')) {
    return
  }
  
  fixingRecordings.value = true
  try {
    // First do a dry run
    const dryRunResponse = await fetch('/api/admin/recordings/fix-availability?dry_run=true', {
      method: 'POST',
      credentials: 'include'
    })
    
    if (!dryRunResponse.ok) {
      throw new Error(`HTTP ${dryRunResponse.status}: ${dryRunResponse.statusText}`)
    }
    
    const dryRunResult = await dryRunResponse.json()
    const message = `Dry run completed:\n- Checked: ${dryRunResult.data.checked} streams\n- Would fix: ${dryRunResult.data.fixed} streams\n- Errors: ${dryRunResult.data.errors}\n\nProceed with actual fix?`
    
    if (!confirm(message)) {
      return
    }
    
    // Do the actual fix
    const fixResponse = await fetch('/api/admin/recordings/fix-availability?dry_run=false', {
      method: 'POST',
      credentials: 'include'
    })
    
    if (!fixResponse.ok) {
      throw new Error(`HTTP ${fixResponse.status}: ${fixResponse.statusText}`)
    }
    
    const fixResult = await fixResponse.json()
    alert(`Recording paths fixed!\n- Checked: ${fixResult.data.checked} streams\n- Fixed: ${fixResult.data.fixed} streams\n- Errors: ${fixResult.data.errors}`)
    
    // Refresh the videos debug data
    await loadVideosDebug()
    
  } catch (error) {
    console.error('Failed to fix recording availability:', error)
    alert('Failed to fix recording availability: ' + String(error))
  } finally {
    fixingRecordings.value = false
  }
}

const cleanupOrphanedRecordings = async () => {
  if (!confirm('This will cleanup database recordings that have been "recording" for more than 48 hours. Continue?')) {
    return
  }
  
  cleaningOrphaned.value = true
  try {
    // First do a dry run
    const dryRunResponse = await fetch('/api/admin/recordings/cleanup-orphaned-db?dry_run=true&max_age_hours=48', {
      method: 'POST',
      credentials: 'include'
    })
    
    if (!dryRunResponse.ok) {
      throw new Error(`HTTP ${dryRunResponse.status}: ${dryRunResponse.statusText}`)
    }
    
    const dryRunResult = await dryRunResponse.json()
    const message = `Dry run completed:\n- Found orphaned recordings: ${dryRunResult.data.checked}\n- Would cleanup: ${dryRunResult.data.cleaned}\n\nProceed with cleanup?`
    
    if (!confirm(message)) {
      return
    }
    
    // Do the actual cleanup
    const cleanupResponse = await fetch('/api/admin/recordings/cleanup-orphaned-db?dry_run=false&max_age_hours=48', {
      method: 'POST',
      credentials: 'include'
    })
    
    if (!cleanupResponse.ok) {
      throw new Error(`HTTP ${cleanupResponse.status}: ${cleanupResponse.statusText}`)
    }
    
    const cleanupResult = await cleanupResponse.json()
    alert(`Orphaned recordings cleaned up!\n- Checked: ${cleanupResult.data.checked} recordings\n- Cleaned: ${cleanupResult.data.cleaned} recordings`)
    
  } catch (error) {
    console.error('Failed to cleanup orphaned recordings:', error)
    alert('Failed to cleanup orphaned recordings: ' + String(error))
  } finally {
    cleaningOrphaned.value = false
  }
}

const cleanupProcessOrphanedRecordings = async () => {
  if (!confirm('This will cleanup database recordings marked as "recording" but without active processes. Continue?')) {
    return
  }
  
  cleaningProcessOrphaned.value = true
  try {
    // First do a dry run
    const dryRunResponse = await fetch('/api/admin/recordings/cleanup-process-orphaned?dry_run=true', {
      method: 'POST',
      credentials: 'include'
    })
    
    if (!dryRunResponse.ok) {
      throw new Error(`HTTP ${dryRunResponse.status}: ${dryRunResponse.statusText}`)
    }
    
    const dryRunResult = await dryRunResponse.json()
    const message = `Dry run completed:\n- Found recordings: ${dryRunResult.data.checked}\n- Would cleanup: ${dryRunResult.data.cleaned}\n\nProceed with cleanup?`
    
    if (!confirm(message)) {
      return
    }
    
    // Do the actual cleanup
    const cleanupResponse = await fetch('/api/admin/recordings/cleanup-process-orphaned?dry_run=false', {
      method: 'POST',
      credentials: 'include'
    })
    
    if (!cleanupResponse.ok) {
      throw new Error(`HTTP ${cleanupResponse.status}: ${cleanupResponse.statusText}`)
    }
    
    const cleanupResult = await cleanupResponse.json()
    alert(`Process orphaned recordings cleaned up!\n- Checked: ${cleanupResult.data.checked} recordings\n- Cleaned: ${cleanupResult.data.cleaned} recordings`)
    
  } catch (error) {
    console.error('Failed to cleanup process orphaned recordings:', error)
    alert('Failed to cleanup process orphaned recordings: ' + String(error))
  } finally {
    cleaningProcessOrphaned.value = false
  }
}

/**
 * Clean up zombie recordings that are stuck in 'recording' status
 * but have no active process running (e.g., after app restart)
 */
const cleanupZombieRecordings = async () => {
  if (!confirm('This will clean up recordings stuck in "recording" status with no active process.\n\nContinue?')) {
    return
  }
  
  cleaningZombies.value = true
  try {
    const response = await fetch('/api/admin/recordings/cleanup-zombies', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    const result = await response.json()
    alert(`Zombie recording cleanup complete!\n\nCleaned: ${result.cleaned_count} recordings`)
    
  } catch (error) {
    console.error('Failed to cleanup zombie recordings:', error)
    alert('Failed to cleanup zombie recordings: ' + String(error))
  } finally {
    cleaningZombies.value = false
  }
}

// Utility functions
const getHealthIcon = (status: string) => {
  switch (status) {
    case 'healthy': return 'fas fa-check-circle text-green'
    case 'warning': return 'fas fa-exclamation-triangle text-yellow'
    case 'error': return 'fas fa-times-circle text-red'
    default: return 'fas fa-question-circle text-gray'
  }
}

const getHealthBorderClass = (status: string) => {
  switch (status) {
    case 'healthy': return 'status-border-success'
    case 'warning': return 'status-border-warning'
    case 'error': return 'status-border-error'
    default: return 'status-border-secondary'
  }
}

const formatTime = (timestamp: string) => {
  return new Date(timestamp).toLocaleTimeString()
}

const formatCheckName = (name: string) => {
  return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const formatTestName = (name: string) => {
  return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const formatCategoryName = (name: string) => {
  return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

// Load initial data
onMounted(() => {
  runQuickHealthCheck()
  loadSystemInfo()
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* ============================================================================
   ADMIN PANEL - Modern Design
   ============================================================================ */

.admin-panel {
  padding: var(--spacing-5);  /* 20px */
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  text-align: center;
  margin-bottom: var(--spacing-8);
}

.page-header h1 {
  color: var(--text-primary);
  margin-bottom: var(--spacing-1);
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
}

.subtitle {
  color: var(--text-secondary);
  font-size: var(--text-lg);
  line-height: var(--leading-normal);
}

/* Admin Sections - GlassCard wrappers */
.admin-section {
  margin-bottom: var(--spacing-6);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-5);
  flex-wrap: wrap;
  gap: var(--spacing-3);
}

.section-header h2 {
  color: var(--text-primary);
  margin: 0;
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
}

/* Buttons use global .btn classes, minimal overrides */
.btn {
  min-height: 44px;  /* Touch target */
}

/* Health Status */
.health-status {
  margin-top: var(--spacing-5);
  padding: var(--spacing-4);
  border-radius: var(--radius-md);
}

.health-status.healthy { 
  background: rgba(39, 174, 96, 0.15); 
  border: 2px solid var(--success-color);
}
.health-status.warning { 
  background: rgba(243, 156, 18, 0.15); 
  border: 2px solid var(--warning-color);
}
.health-status.unhealthy { 
  background: rgba(231, 76, 60, 0.15); 
  border: 2px solid var(--danger-color);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);  /* 12px */
  margin-bottom: var(--spacing-4);  /* 16px */
  font-weight: var(--font-semibold);  /* 600 */
  font-size: var(--text-xl);  /* 20px */
}

.status-text {
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
}

.timestamp {
  font-weight: var(--font-normal);
  font-size: var(--text-xs);  /* 12px */
  opacity: 0.8;
  margin-left: var(--spacing-4);  /* 16px */
}

.health-legend {
  display: flex;
  gap: var(--spacing-4);  /* 16px */
  margin: var(--spacing-1) 0 var(--spacing-4);
  justify-content: flex-end;
  font-size: var(--text-sm);  /* 14px */
}

.legend-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);  /* 8px */
  opacity: 0.8;
}

.health-checks {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: var(--spacing-3);  /* 12px */
}

.health-check {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);  /* 8px */
  padding: var(--spacing-3);  /* 12px */
  border-radius: var(--radius-md);  /* 10px */
  margin-bottom: var(--spacing-1);  /* 4px */
}

.check-name {
  font-weight: var(--font-semibold);  /* 600 */
  margin-right: var(--spacing-2);  /* 8px */
  font-size: var(--text-sm);  /* 14px */
}

.check-message {
  opacity: 0.9;
  font-size: var(--text-sm);  /* 14px */
}

.health-check.healthy { 
  background: rgba(39, 174, 96, 0.1); 
  border-left: 3px solid var(--success-color);
}
.health-check.warning { 
  background: rgba(243, 156, 18, 0.1); 
  border-left: 3px solid var(--warning-color);
}
.health-check.error { 
  background: rgba(231, 76, 60, 0.1); 
  border-left: 3px solid var(--danger-color);
}

/* System Info */
.system-info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--spacing-5);  /* 20px */
}

.info-card {
  background: var(--background-darker);
  padding: var(--spacing-4);  /* 16px */
  border-radius: var(--radius-md);  /* 10px */
  border: 1px solid var(--border-color);
}

.info-card h3 {
  margin-top: 0;
  color: var(--text-primary);
  font-size: var(--text-lg);  /* 18px */
  font-weight: var(--font-semibold);  /* 600 */
  margin-bottom: var(--spacing-3);  /* 12px */
}

.info-card ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.info-card li {
  padding: var(--spacing-1) 0;  /* 4px vertical */
  font-size: var(--text-sm);  /* 14px */
  line-height: var(--leading-relaxed);
}

/* Test Suite - no wrapper class needed, GlassCard handles it */

/* WebSocket and Background Queue - no wrapper classes needed, GlassCard handles it */

.section-description {
  color: var(--text-secondary);
  font-size: var(--text-sm);  /* 14px */
  margin: var(--spacing-1) 0 0 0;
  font-style: italic;
  line-height: var(--leading-relaxed);
}

.test-controls {
  display: flex;
  gap: var(--spacing-3);  /* 12px */
  flex-wrap: wrap;
}

.test-progress {
  margin: var(--spacing-5) 0;  /* 20px vertical */
}

.progress-bar {
  width: 100%;
  height: 20px;
  background: var(--background-darker);
  border-radius: var(--radius-full);
  overflow: hidden;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.2);
}

.progress-fill {
  height: 100%;
  background: var(--primary-color);
  transition: width var(--duration-300) var(--ease-out);
}

.results-summary {
  margin-bottom: var(--spacing-5);  /* 20px */
}

.summary-title {
  color: var(--text-primary);
  font-size: var(--text-2xl);  /* 24px */
  margin-bottom: var(--spacing-4);  /* 16px */
  font-weight: var(--font-semibold);  /* 600 */
}

.summary-stats {
  display: flex;
  gap: var(--spacing-5);  /* 20px */
  margin-top: var(--spacing-4);  /* 16px */
  flex-wrap: wrap;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-4);  /* 16px */
  border-radius: var(--radius-md);  /* 10px */
  min-width: 80px;
  font-weight: var(--font-medium);  /* 500 */
  box-shadow: var(--shadow-sm);
}

.stat.passed { 
  background: rgba(39, 174, 96, 0.2); 
  border: 2px solid var(--success-color);
}
.stat.failed { 
  background: rgba(231, 76, 60, 0.2);
  border: 2px solid var(--danger-color);
}
.stat.total { 
  background: rgba(52, 73, 94, 0.2);
  border: 2px solid var(--text-secondary);
}
.stat.success-rate { 
  background: rgba(52, 152, 219, 0.2);
  border: 2px solid var(--info-color);
}

.stat .count {
  font-size: var(--text-3xl);  /* 30px */
  font-weight: var(--font-bold);  /* 700 */
  margin: var(--spacing-1) 0;
  color: var(--text-primary);
}

.stat .label {
  font-weight: var(--font-semibold);  /* 600 */
  text-transform: uppercase;
  font-size: var(--text-xs);  /* 12px */
  letter-spacing: var(--tracking-wide);
  color: var(--text-secondary);
}

.results-filters {
  display: flex;
  gap: var(--spacing-3);  /* 12px */
  margin-bottom: var(--spacing-4);  /* 16px */
  flex-wrap: wrap;
}

.filter-btn {
  padding: var(--spacing-2) var(--spacing-4);  /* 8px 16px */
  border: 1px solid var(--border-color);
  background: var(--background-card);
  color: var(--text-primary);
  border-radius: var(--radius-md);  /* 10px */
  cursor: pointer;
  font-weight: var(--font-medium);  /* 500 */
  font-size: var(--text-sm);  /* 14px */
  transition: var(--transition-all);
  min-height: 44px;  /* Touch target */
}

.filter-btn:hover {
  background: var(--background-hover);
  border-color: var(--primary-color);
}

.filter-btn.active {
  background: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
  box-shadow: var(--shadow-primary);
}

.test-results-list {
  max-height: 600px;
  overflow-y: auto;
}

/* Custom scrollbar */
.test-results-list::-webkit-scrollbar {
  width: 8px;
}

.test-results-list::-webkit-scrollbar-track {
  background: var(--background-darker);
  border-radius: var(--radius-full);
}

.test-results-list::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: var(--radius-full);
}

.test-results-list::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

.test-result-item {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);  /* 10px */
  margin-bottom: var(--spacing-4);  /* 16px */
  overflow: hidden;
  transition: transform var(--duration-200) var(--ease-out);
  box-shadow: var(--shadow-sm);
}

.test-result-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.test-result-item.passed { 
  border-left: 4px solid var(--success-color);
}
.test-result-item.failed { 
  border-left: 4px solid var(--danger-color);
}

.result-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);  /* 12px */
  padding: var(--spacing-3) var(--spacing-4);  /* 12px 16px */
  background: var(--background-darker);
}

.test-name {
  font-weight: var(--font-semibold);  /* 600 */
  flex: 1;
  color: var(--text-primary);
  font-size: var(--text-base);  /* 16px */
}

.test-time {
  font-size: var(--text-sm);  /* 14px */
  color: var(--text-secondary);
  font-weight: var(--font-medium);  /* 500 */
}

.result-message {
  padding: var(--spacing-3) var(--spacing-4);  /* 12px 16px */
  font-size: var(--text-base);  /* 16px */
  background: var(--background-card);
  border-bottom: 1px solid var(--border-color);
  line-height: var(--leading-relaxed);
}

.result-details {
  border-top: 1px solid var(--border-color);
}

.details-toggle {
  width: 100%;
  padding: var(--spacing-2) var(--spacing-4);  /* 8px 16px */
  border: none;
  background: var(--background-darker);
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  font-size: var(--text-sm);  /* 14px */
  font-weight: var(--font-medium);  /* 500 */
  transition: var(--transition-colors);
  min-height: 44px;  /* Touch target */
}

.details-toggle:hover {
  background: var(--background-hover);
}

/* Debugging Modal Sections */
.debug-content {
  font-family: var(--font-mono);
  font-size: var(--text-sm);  /* 14px */
  line-height: var(--leading-relaxed);
}

.streamer-section {
  margin-bottom: var(--spacing-5);  /* 20px */
  padding: var(--spacing-4);  /* 16px */
  background: var(--background-darker);
  border-radius: var(--radius-md);  /* 10px */
  border: 1px solid var(--border-color);
}

.streamer-section h5 {
  margin: 0 0 var(--spacing-4) 0;  /* 16px bottom */
  color: var(--text-primary);
  font-weight: var(--font-semibold);  /* 600 */
  font-size: var(--text-base);  /* 16px */
}

.season-section {
  margin-bottom: var(--spacing-4);  /* 16px */
  padding: var(--spacing-3);  /* 12px */
  background: var(--background-card);
  border-radius: var(--radius-sm);  /* 6px */
  border: 1px solid var(--border-color);
}

.season-section h6 {
  margin: 0 0 var(--spacing-3) 0;  /* 12px bottom */
  color: var(--text-primary);
  font-weight: var(--font-medium);  /* 500 */
  font-size: var(--text-sm);  /* 14px */
}

.files-list {
  display: grid;
  gap: var(--spacing-2);  /* 8px */
}

.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-2) var(--spacing-3);  /* 8px 12px */
  background: var(--background-darker);
  border-radius: var(--radius-sm);  /* 6px */
  font-size: var(--text-xs);  /* 12px */
}

.file-name {
  flex: 1;
  font-family: var(--font-mono);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  color: var(--text-secondary);
  margin-right: var(--spacing-3);  /* 12px */
  font-size: var(--text-xs);  /* 12px */
}

.file-ext {
  background: var(--background-card);
  color: var(--text-primary);
  padding: var(--spacing-0-5) var(--spacing-2);  /* 2px 8px */
  border-radius: var(--radius-sm);  /* 6px */
  font-weight: var(--font-medium);  /* 500 */
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
}

.file-ext.mp4 {
  background: var(--success-color);
  color: white;
}

.file-ext.ts {
  background: var(--info-color);
  color: white;
}

.more-files {
  color: var(--text-secondary);
  font-style: italic;
  text-align: center;
  padding: var(--spacing-2);  /* 8px */
  font-size: var(--text-sm);  /* 14px */
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Utility classes */
.text-green { color: var(--success-color); font-weight: var(--font-semibold); }
.text-yellow { color: var(--warning-color); }
.text-red { color: var(--danger-color); font-weight: var(--font-semibold); }
.text-gray { color: var(--text-secondary); }

.error {
  background: rgba(220, 38, 38, 0.1);
  color: var(--danger-color);
  padding: var(--spacing-4);  /* 16px */
  border-radius: var(--radius-md);  /* 10px */
  border: 1px solid var(--danger-color);
  font-weight: var(--font-medium);  /* 500 */
  font-size: var(--text-sm);  /* 14px */
  line-height: var(--leading-relaxed);
}

/* Mobile Responsive - Use SCSS mixins for breakpoints */

@include m.respond-below('md') {  // < 768px
  .admin-panel {
    padding: var(--spacing-3);  /* 12px */
  }

  .summary-stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .test-controls {
    flex-direction: column;
  }

  .test-controls .btn {
    width: 100%;
    min-height: 44px;  /* Touch-friendly */
  }
  
  .section-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-3);
  }
  
  .section-header .btn {
    width: 100%;
    justify-content: center;
  }
}

@include m.respond-below('sm') {  // < 640px
  .admin-panel {
    padding: var(--spacing-2);
  }
  
  .page-header h1 {
    font-size: var(--text-2xl);
  }
  
  .subtitle {
    font-size: var(--text-sm);
  }

  .summary-stats {
    grid-template-columns: 1fr;  /* Single column on small mobile */
    gap: var(--spacing-2);
  }
  
  .system-info-grid {
    grid-template-columns: 1fr;  /* Single column */
    gap: var(--spacing-3);
  }
  
  .health-checks {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }
  
  .health-check {
    padding: var(--spacing-3);
  }
  
  .btn {
    min-height: 44px;  /* Touch-friendly */
    padding: var(--spacing-3) var(--spacing-4);
    font-size: var(--text-sm);
  }
  
  .test-item {
    padding: var(--spacing-3);
  }
  
  .results-table {
    font-size: var(--text-xs);
  }
}
</style>
