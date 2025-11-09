<template>
  <div class="admin-panel">
    <div class="header">
      <h1>StreamVault Admin Panel</h1>
      <p class="subtitle">System Testing & Diagnostics</p>
    </div>

    <!-- Quick Health Check -->
    <div class="health-section">
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
    </div>

    <!-- System Information -->
    <div class="system-info-section">
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

        <div class="info-card status-border status-border-info">
          <h3>Resources</h3>
          <ul>
            <li><strong>CPU Cores:</strong> {{ systemInfo.resources.cpu_count }}</li>
            <li><strong>CPU Usage:</strong> {{ systemInfo.resources.cpu_percent }}%</li>
            <li><strong>Memory:</strong> {{ systemInfo.resources.memory.available_gb }}GB / {{ systemInfo.resources.memory.total_gb }}GB available</li>
          </ul>
        </div>

        <div class="info-card status-border status-border-info">
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

        <div class="info-card status-border status-border-info">
          <h3>Configuration</h3>
          <ul>
            <li><strong>Recording Dir:</strong> {{ systemInfo.settings.recording_directory }}</li>
            <li><strong>VAPID Keys:</strong> {{ systemInfo.settings.vapid_configured ? 'Configured' : 'Not Configured' }}</li>
            <li><strong>Proxy:</strong> {{ systemInfo.settings.proxy_configured ? 'Configured' : 'Direct Connection' }}</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- WebSocket Monitoring -->
    <div class="websocket-section">
      <div class="section-header">
        <h2>WebSocket Connections</h2>
      </div>
      <WebSocketMonitor />
    </div>

    <!-- Background Queue Monitoring -->
    <div class="background-queue-section">
      <div class="section-header">
        <h2>Background Jobs & Services</h2>
        <p class="section-description">Real-time monitoring of background tasks, recording services, and system processes</p>
      </div>
      <BackgroundQueueMonitor />
    </div>

    <!-- Background Queue Management & Cleanup -->
    <div class="background-queue-admin-section">
      <div class="section-header">
        <h2>🔧 Background Queue Management</h2>
        <p class="section-description">
          Fix Background Queue Problems: Stuck Recording Jobs, Continuous Orphaned Recovery, Unknown Task Names
        </p>
      </div>
      <BackgroundQueueAdmin />
    </div>

    <!-- Post-Processing Management -->
    <div class="post-processing-admin-section">
      <div class="section-header">
        <h2>🔄 Post-Processing Management</h2>
        <p class="section-description">
          Manual Post-Processing for Failed Recordings and Cleanup of Orphaned Files
        </p>
      </div>
      <PostProcessingManagement />
    </div>

    <!-- Test Suite -->
    <div class="test-suite-section">
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
    </div>

    <!-- Maintenance -->
    <div class="maintenance-section">
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
    </div>

    <!-- Video Debug Section -->
    <div class="video-debug-section">
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
      </div>
    </div>    <!-- Logs Modal -->
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
    const response = await fetch('/api/admin/system/info')
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
    const response = await fetch('/api/admin/tests/available')
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
      headers: { 'Content-Type': 'application/json' }
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
    const response = await fetch(`/api/admin/logs/recent?lines=${logLines.value}&level=${logLevel.value}`)
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

<style scoped>
:root {
  --color-border-light: rgba(127, 127, 127, 0.2);
  --color-text-dark: #222;
}

.admin-panel {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.header h1 {
  color: var(--color-heading);
  margin-bottom: 5px;
}

.subtitle {
  color: var(--color-text-light);
  font-size: 1.1em;
}

.section-header {
  display: flex;
  justify-content: between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h2 {
  color: var(--color-heading);
  margin: 0;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: var(--border-radius, 8px);
  cursor: pointer;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Button colors handled by global .btn-* classes in _components.scss */

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* Health Status */
.health-section {
  background: var(--color-background-soft);
  border-radius: var(--border-radius, 8px);
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.health-status {
  margin-top: 20px;
  padding: 15px;
  border-radius: var(--border-radius, 8px);
}

.health-status.healthy { 
  background: rgba(39, 174, 96, 0.2); 
  /* Border color handled by .status-border-* classes */
  color: var(--color-text);
}
.health-status.warning { 
  background: rgba(243, 156, 18, 0.2); 
  /* Border color handled by .status-border-* classes */
  color: var(--color-text);
}
.health-status.unhealthy { 
  background: rgba(231, 76, 60, 0.2); 
  /* Border color handled by .status-border-* classes */
  color: var(--color-text);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
  font-weight: 600;
  font-size: 1.2em;
}

.status-text {
  text-transform: uppercase;
  letter-spacing: 1px;
}

.timestamp {
  font-weight: normal;
  font-size: 0.8em;
  opacity: 0.8;
  margin-left: 15px;
}

.health-legend {
  display: flex;
  gap: 15px;
  margin: 5px 0 15px;
  justify-content: flex-end;
  font-size: 0.9em;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  opacity: 0.8;
}

.health-checks {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 10px;
}

.health-check {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border-radius: var(--border-radius-sm, 4px);
  margin-bottom: 5px;
}

.check-name {
  font-weight: 600;
  margin-right: 8px;
}

.check-message {
  opacity: 0.9;
}

.health-check.healthy { 
  background: rgba(39, 174, 96, 0.15); 
  /* Border color handled by .status-border-* classes */
  padding-left: 10px;
}
.health-check.warning { 
  background: rgba(243, 156, 18, 0.15); 
  /* Border color handled by .status-border-* classes */
  padding-left: 10px;
}
.health-check.error { 
  background: rgba(231, 76, 60, 0.15); 
  /* Border color handled by .status-border-* classes */
  padding-left: 10px;
}

/* System Info */
.system-info-section {
  background: var(--color-background-soft);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.system-info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.info-card {
  background: var(--color-background-mute);
  padding: 15px;
  border-radius: var(--border-radius, 8px);
  /* Border color handled by .status-border-* classes */
}

.info-card h3 {
  margin-top: 0;
  color: var(--color-heading);
}

.info-card ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.info-card li {
  padding: 4px 0;
}

/* Test Suite */
.test-suite-section {
  background: var(--color-background-soft);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

/* WebSocket and Background Queue Sections */
.websocket-section,
.background-queue-section {
  background: var(--color-background-soft);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.section-description {
  color: var(--color-text-light);
  font-size: 0.9em;
  margin: 5px 0 0 0;
  font-style: italic;
}

.test-controls {
  display: flex;
  gap: 10px;
}

.test-progress {
  margin: 20px 0;
}

.progress-bar {
  width: 100%;
  height: 20px;
  background: var(--color-background-mute);
  border-radius: var(--border-radius-lg, 12px);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--info-color);
  transition: width 0.3s;
}

.results-summary {
  margin-bottom: 20px;
}

.summary-title {
  color: var(--color-heading);
  font-size: 1.4em;
  margin-bottom: 15px;
  font-weight: 600;
}

.summary-stats {
  display: flex;
  gap: 20px;
  margin-top: 15px;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 15px;
  border-radius: var(--border-radius, 8px);
  min-width: 80px;
  color: var(--color-text-dark);
  font-weight: 500;
}

.stat.passed { 
  background: rgba(39, 174, 96, 0.25); 
  border: 1px solid rgba(39, 174, 96, 0.5);
}
.stat.failed { 
  background: rgba(231, 76, 60, 0.25);
  border: 1px solid rgba(231, 76, 60, 0.5);
}
.stat.total { 
  background: rgba(52, 73, 94, 0.25);
  border: 1px solid rgba(52, 73, 94, 0.5);
}
.stat.success-rate { 
  background: rgba(52, 152, 219, 0.25);
  border: 1px solid rgba(52, 152, 219, 0.5);
}

.stat .count {
  font-size: 1.8em;
  font-weight: bold;
  margin: 5px 0;
  color: var(--color-text-dark);
  text-shadow: 0 1px 1px rgba(255, 255, 255, 0.2);
}

.stat .label {
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.8em;
  letter-spacing: 0.5px;
}

.results-filters {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
}

.filter-btn {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  background: var(--color-background);
  color: var(--color-text);
  border-radius: var(--border-radius-sm, 4px);
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s ease;
}

.filter-btn:hover {
  background: var(--color-background-soft);
}

.filter-btn.active {
  background: var(--info-color);
  color: var(--text-primary);
  border-color: var(--info-color);
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}

.test-results-list {
  max-height: 600px;
  overflow-y: auto;
}

.test-result-item {
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius, 8px);
  margin-bottom: 15px;
  overflow: hidden;
  transition: transform 0.2s ease-in-out;
}

.test-result-item:hover {
  transform: translateY(-2px);
}

.test-result-item.passed { 
  /* Border color handled by .status-border-* classes */
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.test-result-item.failed { 
  /* Border color handled by .status-border-* classes */
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 15px;
  background: var(--color-background-mute);
}

.test-name {
  font-weight: 600;
  flex: 1;
  color: var(--color-heading);
}

.test-time {
  font-size: 0.9em;
  color: var(--color-text-light);
  font-weight: 500;
}

.result-message {
  padding: 12px 15px;
  font-size: 1.05em;
  background: var(--color-background);
  border-bottom: 1px solid var(--color-border-light);
}

.result-details {
  border-top: 1px solid var(--color-border-light);
}

.details-toggle {
  width: 100%;
  padding: 8px 15px;
  border: none;
  background: var(--color-background-mute);
  color: var(--color-text);
  text-align: left;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 5px;
}

.details-content {
  padding: 15px;
  background: var(--color-background-mute);
  max-height: 300px;
  overflow-y: auto;
}

.details-content pre {
  margin: 0;
  font-size: 0.9em;
}

/* Available Tests */
.available-tests {
  margin-top: 20px;
  padding: 20px;
  background: var(--color-background-mute);
  border-radius: var(--border-radius, 8px);
}

.test-categories {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
}

.test-category h4 {
  color: var(--color-heading);
  margin-bottom: 10px;
}

.test-category ul {
  list-style: none;
  padding: 0;
}

.test-category li {
  padding: 3px 0;
  font-size: 0.9em;
}

/* Maintenance */
.maintenance-section {
  background: var(--color-background-soft);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.maintenance-actions {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
}

.cleanup-result {
  background: rgba(46, 204, 113, 0.15);
  padding: 15px;
  border-radius: var(--border-radius, 8px);
  /* Border color handled by .status-border-* classes */
  color: var(--color-text);
}

.error-list {
  margin-top: 10px;
  padding-left: 20px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--color-background);
  border-radius: 8px;
  width: 90%;
  max-width: 800px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  color: var(--color-text);
  border: 1px solid var(--border-color);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
  background: var(--color-background-soft);
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.2em;
  cursor: pointer;
  color: var(--color-text-light);
}

.modal-body {
  padding: 20px;
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  color: var(--color-text);
}

.log-controls {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
  align-items: center;
}

.log-controls select,
.log-controls input {
  padding: 5px 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm, 4px);
  background: var(--color-background);
  color: var(--color-text);
}

.logs-content {
  flex: 1;
  overflow-y: auto;
  background: var(--color-background-mute);
  color: var(--color-text);
  padding: 15px;
  border-radius: var(--border-radius-sm, 4px);
  font-family: 'Courier New', monospace;
  border: 1px solid var(--border-color);
}

.logs-content pre {
  margin: 0;
  font-size: 0.85em;
  line-height: 1.4;
}

/* Video Debug Section */
.video-debug-section {
  background: rgba(29, 78, 216, 0.1);
  border: 2px solid rgba(29, 78, 216, 0.3);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.video-debug-actions {
  display: flex;
  gap: 15px;
  margin-bottom: 15px;
}

.debug-btn {
  background: linear-gradient(145deg, var(--info-color), var(--primary-color));
  color: var(--text-primary);
  border: none;
  padding: 10px 20px;
  border-radius: var(--border-radius, 8px);
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

.debug-btn:hover {
  background: linear-gradient(145deg, var(--primary-color), var(--info-color));
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(66, 184, 131, 0.4);
}

.debug-btn:disabled {
  background: var(--text-secondary);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.debug-btn.loading {
  position: relative;
  color: transparent;
}

.debug-btn.loading::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 16px;
  height: 16px;
  margin: -8px 0 0 -8px;
  border: 2px solid transparent;
  border-top: 2px solid white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--color-background);
  border-radius: 12px;
  max-width: 90vw;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  border: 1px solid var(--border-color);
}

.videos-debug-modal {
  width: 1200px;
}

.recordings-directory-modal {
  width: 1000px;
}

.modal-header {
  background: var(--color-background-soft);
  color: var(--color-text);
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text);
}

.close-btn {
  background: none;
  border: none;
  color: var(--color-text);
  font-size: 20px;
  cursor: pointer;
  padding: 5px;
  border-radius: var(--border-radius-sm, 4px);
  transition: background 0.2s;
}

.close-btn:hover {
  background: var(--color-background-mute);
}

.modal-body {
  padding: 20px;
  max-height: calc(90vh - 80px);
  overflow-y: auto;
}

.debug-content {
  color: var(--color-text);
}

.debug-section {
  margin-bottom: 30px;
}

.debug-section h4 {
  color: var(--color-text);
  margin-bottom: 15px;
  font-size: 18px;
  font-weight: 600;
  border-bottom: 2px solid var(--border-color);
  padding-bottom: 8px;
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.stat {
  background: var(--color-background-mute);
  padding: 15px;
  border-radius: 8px;
  text-align: center;
  border: 1px solid var(--border-color);
}

.stat .count {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 5px;
}

.stat .label {
  font-size: 12px;
  color: var(--color-text-light);
  text-transform: uppercase;
  font-weight: 500;
}

.debug-table {
  background: var(--color-background);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.debug-table table {
  width: 100%;
  border-collapse: collapse;
}

.debug-table th {
  background: var(--color-background-soft);
  padding: 12px;
  text-align: left;
  font-weight: 600;
  color: var(--color-text);
  border-bottom: 1px solid var(--border-color);
  font-size: 14px;
}

.debug-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border-light);
  font-size: 13px;
  color: var(--color-text);
}

.debug-table tr:hover {
  background: var(--color-background-soft);
}

.path-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'Courier New', monospace;
  font-size: 11px;
}

.text-green {
  color: var(--success-color);
  font-weight: 600;
}

.text-red {
  color: var(--danger-color);
  font-weight: 600;
}

.text-gray {
  color: var(--text-secondary);
}

.streamer-section {
  margin-bottom: 20px;
  padding: 15px;
  background: var(--color-background-soft);
  border-radius: 8px;
  /* Border color handled by .status-border-* classes */
}

.streamer-section h5 {
  margin: 0 0 15px 0;
  color: var(--color-text);
  font-weight: 600;
}

.season-section {
  margin-bottom: 15px;
  padding: 12px;
  background: var(--color-background);
  border-radius: 6px;
  border: 1px solid var(--border-color);
}

.season-section h6 {
  margin: 0 0 10px 0;
  color: var(--color-text);
  font-weight: 500;
  font-size: 14px;
}

.files-list {
  display: grid;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--color-background-mute);
  border-radius: 4px;
  font-size: 12px;
}

.file-name {
  flex: 1;
  font-family: 'Courier New', monospace;
  color: var(--color-text);
}

.file-size {
  color: var(--color-text-light);
  margin-right: 10px;
}

.file-ext {
  background: var(--color-background-soft);
  color: var(--color-text);
  padding: 2px 6px;
  border-radius: var(--border-radius-sm, 4px);
  font-weight: 500;
  font-size: 10px;
  text-transform: uppercase;
}

.file-ext.mp4 {
  background: var(--success-color);
  color: var(--background-darker);
  opacity: 0.8;
}

.file-ext.ts {
  background: var(--info-color);
  color: var(--background-darker);
  opacity: 0.8;
}

.more-files {
  color: var(--color-text-light);
  font-style: italic;
  text-align: center;
  padding: 8px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Utility classes */
.text-green { color: var(--success-color); font-weight: 600; }
.text-yellow { color: var(--warning-color); }
.text-red { color: var(--danger-color); font-weight: 600; }
.text-gray { color: var(--color-text-light); }

.error {
  background: rgba(220, 38, 38, 0.1);
  color: var(--danger-color);
  padding: 15px;
  border-radius: var(--border-radius, 8px);
  border: 1px solid rgba(220, 38, 38, 0.3);
  font-weight: 500;
}
</style>
