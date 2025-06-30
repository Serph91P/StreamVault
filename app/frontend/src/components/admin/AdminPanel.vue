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

      <div v-if="healthStatus" class="health-status" :class="healthStatus.overall_status">
        <div class="status-indicator">
          <i :class="getHealthIcon(healthStatus.overall_status)"></i>
          <span class="status-text">{{ healthStatus.overall_status.toUpperCase() }}</span>
          <span class="timestamp">{{ formatTime(healthStatus.timestamp) }}</span>
        </div>
        
        <div class="health-checks">
          <div 
            v-for="(check, name) in healthStatus.checks" 
            :key="name"
            class="health-check"
            :class="check.status"
          >
            <i :class="getHealthIcon(check.status)"></i>
            <span class="check-name">{{ formatCheckName(name) }}</span>
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
        <div class="info-card">
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
          <h3>Test Results Summary</h3>
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
              Failed ({{ testResults.results.filter(r => !r.success).length }})
            </button>
            <button 
              @click="resultFilter = 'passed'"
              :class="{active: resultFilter === 'passed'}"
              class="filter-btn"
            >
              Passed ({{ testResults.results.filter(r => r.success).length }})
            </button>
          </div>

          <div class="test-results-list">
            <div 
              v-for="result in filteredResults" 
              :key="result.test_name"
              class="test-result-item"
              :class="result.success ? 'passed' : 'failed'"
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
            <h4>{{ formatCategoryName(category) }}</h4>
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

      <div v-if="cleanupResult" class="cleanup-result">
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

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

// Utility functions
const getHealthIcon = (status: string) => {
  switch (status) {
    case 'healthy': return 'fas fa-check-circle text-green'
    case 'warning': return 'fas fa-exclamation-triangle text-yellow'
    case 'error': return 'fas fa-times-circle text-red'
    default: return 'fas fa-question-circle text-gray'
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
  color: #2c3e50;
  margin-bottom: 5px;
}

.subtitle {
  color: #7f8c8d;
  font-size: 1.1em;
}

.section-header {
  display: flex;
  justify-content: between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h2 {
  color: #34495e;
  margin: 0;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 5px;
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

.btn-primary { background: #3498db; color: white; }
.btn-secondary { background: #95a5a6; color: white; }
.btn-success { background: #27ae60; color: white; }
.btn-warning { background: #f39c12; color: white; }
.btn-info { background: #17a2b8; color: white; }

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* Health Status */
.health-section {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.health-status {
  margin-top: 20px;
  padding: 15px;
  border-radius: 5px;
}

.health-status.healthy { background: #d4edda; border-left: 4px solid #27ae60; }
.health-status.warning { background: #fff3cd; border-left: 4px solid #f39c12; }
.health-status.unhealthy { background: #f8d7da; border-left: 4px solid #e74c3c; }

.status-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
  font-weight: 600;
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
  padding: 8px;
  border-radius: 4px;
}

.health-check.healthy { background: rgba(39, 174, 96, 0.1); }
.health-check.warning { background: rgba(243, 156, 18, 0.1); }
.health-check.error { background: rgba(231, 76, 60, 0.1); }

/* System Info */
.system-info-section {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.system-info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.info-card {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 5px;
  border-left: 4px solid #3498db;
}

.info-card h3 {
  margin-top: 0;
  color: #2c3e50;
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
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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
  background: #ecf0f1;
  border-radius: 10px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #3498db;
  transition: width 0.3s;
}

.results-summary {
  margin-bottom: 20px;
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
  border-radius: 5px;
  min-width: 80px;
}

.stat.passed { background: #d4edda; }
.stat.failed { background: #f8d7da; }
.stat.total { background: #e2e3e5; }
.stat.success-rate { background: #cce5ff; }

.stat .count {
  font-size: 1.5em;
  font-weight: bold;
  margin: 5px 0;
}

.results-filters {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
}

.filter-btn {
  padding: 8px 16px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.filter-btn.active {
  background: #3498db;
  color: white;
  border-color: #3498db;
}

.test-results-list {
  max-height: 600px;
  overflow-y: auto;
}

.test-result-item {
  border: 1px solid #ddd;
  border-radius: 5px;
  margin-bottom: 10px;
  overflow: hidden;
}

.test-result-item.passed { border-left: 4px solid #27ae60; }
.test-result-item.failed { border-left: 4px solid #e74c3c; }

.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 15px;
  background: #f8f9fa;
}

.test-name {
  font-weight: 500;
  flex: 1;
}

.test-time {
  font-size: 0.9em;
  color: #6c757d;
}

.result-message {
  padding: 10px 15px;
}

.result-details {
  border-top: 1px solid #eee;
}

.details-toggle {
  width: 100%;
  padding: 8px 15px;
  border: none;
  background: #f8f9fa;
  text-align: left;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 5px;
}

.details-content {
  padding: 15px;
  background: #f1f3f4;
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
  background: #f8f9fa;
  border-radius: 5px;
}

.test-categories {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
}

.test-category h4 {
  color: #2c3e50;
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
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.maintenance-actions {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
}

.cleanup-result {
  background: #e8f5e8;
  padding: 15px;
  border-radius: 5px;
  border-left: 4px solid #27ae60;
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
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 800px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.2em;
  cursor: pointer;
  color: #6c757d;
}

.modal-body {
  padding: 20px;
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
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
  border: 1px solid #ddd;
  border-radius: 4px;
}

.logs-content {
  flex: 1;
  overflow-y: auto;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 15px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
}

.logs-content pre {
  margin: 0;
  font-size: 0.85em;
  line-height: 1.4;
}

/* Utility classes */
.text-green { color: #27ae60; }
.text-yellow { color: #f39c12; }
.text-red { color: #e74c3c; }
.text-gray { color: #6c757d; }

.error {
  color: #e74c3c;
  font-style: italic;
}
</style>
