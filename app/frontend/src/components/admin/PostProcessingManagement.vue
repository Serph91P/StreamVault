<template>
  <div class="post-processing-management">
    <div class="section-header">
      <h3>🔄 Post-Processing Management</h3>
      <p>Manually restart post-processing for failed recordings and cleanup orphaned files.</p>
    </div>

    <!-- Statistics Card -->
    <div class="stats-section">
      <div class="card stats-card">
        <div class="card-header">
          <h4>📊 Orphaned Files Statistics</h4>
          <button @click="refreshStats" :disabled="loadingStats" class="btn btn-sm btn-secondary">
            <span v-if="loadingStats">🔄</span>
            <span v-else>🔄</span>
            Refresh
          </button>
        </div>
        <div class="card-body">
          <div v-if="loadingStats" class="loading">Loading statistics...</div>
          <div v-else-if="stats" class="stats-grid">
            <div class="stat-item">
              <div class="stat-value">{{ stats.orphaned_recordings }}</div>
              <div class="stat-label">Orphaned .ts Files</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ stats.orphaned_segments }}</div>
              <div class="stat-label">Orphaned Segments</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ stats.total_size_gb.toFixed(2) }} GB</div>
              <div class="stat-label">Total Size</div>
            </div>
          </div>
          
          <!-- By Streamer Breakdown -->
          <div v-if="stats && Object.keys(stats.by_streamer).length > 0" class="streamer-breakdown">
            <h5>By Streamer:</h5>
            <div class="streamer-list">
              <div v-for="(data, streamer) in stats.by_streamer" :key="streamer" class="streamer-item">
                <span class="streamer-name">{{ streamer }}</span>
                <span class="streamer-stats">{{ data.count }} files ({{ (data.size / (1024**3)).toFixed(2) }} GB)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="actions-section">
      <div class="card">
        <div class="card-header">
          <h4>🛠️ Actions</h4>
        </div>
        <div class="card-body">
          <div class="action-buttons">
            <button 
              @click="retryAllPostProcessing(true)" 
              :disabled="processing"
              class="btn btn-primary"
            >
              🔍 Preview All Changes
            </button>
            
            <button 
              @click="retryAllPostProcessing(false)" 
              :disabled="processing || (stats && stats.orphaned_recordings === 0)"
              class="btn btn-success"
            >
              🔄 Retry All Post-Processing
            </button>
            
            <button 
              @click="cleanupSegments(true)" 
              :disabled="processing"
              class="btn btn-warning"
            >
              🧹 Preview Segment Cleanup
            </button>
            
            <button 
              @click="cleanupSegments(false)" 
              :disabled="processing || (stats && stats.orphaned_segments === 0)"
              class="btn btn-danger"
            >
              🧹 Clean Orphaned Segments
            </button>
          </div>
          
          <div class="settings-row">
            <label>
              Max Age (hours):
              <input 
                v-model.number="maxAgeHours" 
                type="number" 
                min="1" 
                max="168" 
                class="form-input"
                :disabled="processing"
              />
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- Orphaned Recordings List -->
    <div class="recordings-section">
      <div class="card">
        <div class="card-header">
          <h4>📋 Orphaned Recordings</h4>
          <button @click="loadOrphanedList" :disabled="loadingList" class="btn btn-sm btn-secondary">
            <span v-if="loadingList">🔄</span>
            <span v-else>📋</span>
            Load List
          </button>
        </div>
        <div class="card-body">
          <div v-if="loadingList" class="loading">Loading recordings list...</div>
          <div v-else-if="orphanedList.length > 0">
            <div class="list-controls">
              <button 
                @click="selectAll" 
                class="btn btn-sm btn-secondary"
                :disabled="processing"
              >
                Select All
              </button>
              <button 
                @click="selectNone" 
                class="btn btn-sm btn-secondary"
                :disabled="processing"
              >
                Select None
              </button>
              <button 
                @click="retrySelected" 
                :disabled="processing || selectedRecordings.length === 0"
                class="btn btn-sm btn-success"
              >
                🔄 Retry Selected ({{ selectedRecordings.length }})
              </button>
            </div>
            
            <div class="recordings-list">
              <div v-for="recording in orphanedList" :key="recording.recording_id" class="recording-item">
                <label class="recording-checkbox">
                  <input 
                    type="checkbox" 
                    :value="recording.recording_id"
                    v-model="selectedRecordings"
                    :disabled="!recording.valid_for_recovery || processing"
                  />
                  <div class="recording-info">
                    <div class="recording-header">
                      <span class="recording-id">#{{ recording.recording_id }}</span>
                      <span class="streamer-name">{{ recording.streamer_name }}</span>
                      <span class="file-size">{{ recording.file_size_mb.toFixed(1) }} MB</span>
                    </div>
                    <div class="recording-details">
                      <div class="stream-title">{{ recording.stream_title }}</div>
                      <div class="file-path">{{ recording.file_path }}</div>
                      <div class="recording-meta">
                        Age: {{ recording.file_age_hours.toFixed(1) }}h | 
                        Status: {{ recording.status }} |
                        <span :class="{'text-success': recording.valid_for_recovery, 'text-danger': !recording.valid_for_recovery}">
                          {{ recording.valid_for_recovery ? 'Ready' : recording.validation_reason }}
                        </span>
                      </div>
                    </div>
                  </div>
                </label>
              </div>
            </div>
          </div>
          <div v-else-if="orphanedList.length === 0 && !loadingList">
            <div class="no-data">No orphaned recordings found.</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Results Section -->
    <div v-if="lastResult" class="results-section">
      <div class="card">
        <div class="card-header">
          <h4>📋 Last Operation Results</h4>
        </div>
        <div class="card-body">
          <div class="result-summary">
            <div :class="['result-message', lastResult.success ? 'success' : 'error']">
              {{ lastResult.message }}
            </div>
            <div v-if="lastResult.recovery_triggered > 0" class="result-stats">
              ✅ Triggered: {{ lastResult.recovery_triggered }} |
              ❌ Failed: {{ lastResult.recovery_failed }} |
              🧹 Segments: {{ lastResult.segments_cleaned }}
            </div>
          </div>
          
          <div v-if="lastResult.errors && lastResult.errors.length > 0" class="errors-list">
            <h5>Errors:</h5>
            <ul>
              <li v-for="error in lastResult.errors" :key="error">{{ error }}</li>
            </ul>
          </div>
          
          <div v-if="lastResult.details && lastResult.details.length > 0" class="details-list">
            <h5>Details:</h5>
            <div class="details-grid">
              <div v-for="detail in lastResult.details" :key="detail.recording_id" class="detail-item">
                <span class="detail-id">#{{ detail.recording_id }}</span>
                <span class="detail-streamer">{{ detail.streamer_name }}</span>
                <span :class="['detail-status', detail.recovery_triggered ? 'success' : 'error']">
                  {{ detail.recovery_triggered ? '✅ Triggered' : '❌ Failed' }}
                </span>
                <span v-if="detail.error" class="detail-error">{{ detail.error }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

// Reactive data
const loadingStats = ref(false)
const loadingList = ref(false)
const processing = ref(false)
const stats = ref(null)
const orphanedList = ref([])
const selectedRecordings = ref([])
const lastResult = ref(null)
const maxAgeHours = ref(48)

// Methods
const refreshStats = async () => {
  loadingStats.value = true
  try {
    const response = await fetch(`/api/admin/post-processing/stats?max_age_hours=${maxAgeHours.value}`, {
      credentials: 'include'
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    stats.value = await response.json()
  } catch (error) {
    console.error('Failed to load stats:', error)
    alert('Failed to load statistics: ' + String(error))
  } finally {
    loadingStats.value = false
  }
}

const loadOrphanedList = async () => {
  loadingList.value = true
  try {
    const response = await fetch(`/api/admin/post-processing/orphaned-list?max_age_hours=${maxAgeHours.value}&limit=100`, {
      credentials: 'include'
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    const result = await response.json()
    orphanedList.value = result.recordings || []
    selectedRecordings.value = []
  } catch (error) {
    console.error('Failed to load orphaned list:', error)
    alert('Failed to load orphaned recordings: ' + String(error))
  } finally {
    loadingList.value = false
  }
}

const retryAllPostProcessing = async (dryRun = false) => {
  if (!dryRun && !confirm(`This will restart post-processing for all orphaned recordings (${stats.value?.orphaned_recordings || 0} files). Continue?`)) {
    return
  }
  
  processing.value = true
  try {
    const response = await fetch(`/api/admin/post-processing/retry-all?max_age_hours=${maxAgeHours.value}&dry_run=${dryRun}&cleanup_segments=true`, {
      method: 'POST',
      credentials: 'include'
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    lastResult.value = await response.json()
    
    if (!dryRun) {
      // Refresh stats and list after successful operation
      await refreshStats()
      await loadOrphanedList()
    }
  } catch (error) {
    console.error('Failed to retry post-processing:', error)
    alert('Failed to retry post-processing: ' + String(error))
  } finally {
    processing.value = false
  }
}

const retrySelected = async () => {
  if (selectedRecordings.value.length === 0) return
  
  if (!confirm(`This will restart post-processing for ${selectedRecordings.value.length} selected recordings. Continue?`)) {
    return
  }
  
  processing.value = true
  try {
    const response = await fetch('/api/admin/post-processing/retry-specific', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include',
      body: JSON.stringify({
        recording_ids: selectedRecordings.value,
        dry_run: false
      })
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    lastResult.value = await response.json()
    
    // Refresh stats and list after successful operation
    await refreshStats()
    await loadOrphanedList()
    selectedRecordings.value = []
  } catch (error) {
    console.error('Failed to retry selected recordings:', error)
    alert('Failed to retry selected recordings: ' + String(error))
  } finally {
    processing.value = false
  }
}

const cleanupSegments = async (dryRun = false) => {
  if (!dryRun && !confirm(`This will delete orphaned segment directories (${stats.value?.orphaned_segments || 0} directories). This cannot be undone. Continue?`)) {
    return
  }
  
  processing.value = true
  try {
    const response = await fetch(`/api/admin/post-processing/cleanup-segments?max_age_hours=${maxAgeHours.value}&dry_run=${dryRun}`, {
      method: 'POST',
      credentials: 'include'
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    const result = await response.json()
    lastResult.value = {
      success: result.success,
      message: result.message,
      recovery_triggered: 0,
      recovery_failed: 0,
      segments_cleaned: result.data?.segments_cleaned || 0,
      details: result.data?.segments_cleaned_list || [],
      errors: result.data?.errors || []
    }
    
    if (!dryRun) {
      // Refresh stats after successful cleanup
      await refreshStats()
    }
  } catch (error) {
    console.error('Failed to cleanup segments:', error)
    alert('Failed to cleanup segments: ' + String(error))
  } finally {
    processing.value = false
  }
}

const selectAll = () => {
  selectedRecordings.value = orphanedList.value
    .filter(r => r.valid_for_recovery)
    .map(r => r.recording_id)
}

const selectNone = () => {
  selectedRecordings.value = []
}

// Initialize
onMounted(() => {
  refreshStats()
})
</script>

<style scoped>
.post-processing-management {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.section-header {
  margin-bottom: 30px;
}

.section-header h3 {
  margin: 0 0 10px 0;
  color: var(--color-heading);
}

.section-header p {
  margin: 0;
  color: var(--color-text-light);
}

.card {
  background: var(--color-background-soft);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin-bottom: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.card-header {
  padding: 15px 20px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-background-mute);
  border-radius: 8px 8px 0 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h4 {
  margin: 0;
  color: var(--color-text);
}

.card-body {
  padding: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 15px;
  background: var(--color-background-mute);
  border-radius: 6px;
  border: 1px solid var(--color-border);
}

.stat-value {
  font-size: 2em;
  font-weight: bold;
  color: var(--color-heading);
  margin-bottom: 5px;
}

.stat-label {
  font-size: 0.9em;
  color: var(--color-text-light);
}

.streamer-breakdown {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border);
}

.streamer-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 10px;
  margin-top: 10px;
}

.streamer-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--color-background-mute);
  border-radius: 4px;
  border: 1px solid var(--color-border);
}

.streamer-name {
  font-weight: 500;
  color: var(--color-text);
}

.streamer-stats {
  font-size: 0.9em;
  color: var(--color-text-light);
}

.action-buttons {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.settings-row {
  display: flex;
  gap: 20px;
  align-items: center;
  padding-top: 15px;
  border-top: 1px solid var(--color-border);
}

.settings-row label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: var(--color-text);
}

.form-input {
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  width: 80px;
  background: var(--color-background);
  color: var(--color-text);
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9em;
  font-weight: 500;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  transition: all 0.2s;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary { background: #007bff; color: white; }
.btn-success { background: #28a745; color: white; }
.btn-warning { background: #ffc107; color: #212529; }
.btn-danger { background: #dc3545; color: white; }
.btn-secondary { background: #6c757d; color: white; }

.btn-sm {
  padding: 6px 12px;
  font-size: 0.8em;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}

.list-controls {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--color-border);
}

.recordings-list {
  max-height: 600px;
  overflow-y: auto;
}

.recording-item {
  margin-bottom: 10px;
}

.recording-checkbox {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--color-background);
}

.recording-checkbox:hover {
  background: var(--color-background-soft);
  border-color: #007bff;
}

.recording-checkbox input[type="checkbox"] {
  margin-top: 4px;
}

.recording-info {
  flex: 1;
}

.recording-header {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 8px;
}

.recording-id {
  font-weight: bold;
  color: #007bff;
}

.streamer-name {
  font-weight: 500;
  color: var(--color-text);
}

.file-size {
  font-size: 0.9em;
  color: var(--color-text-light);
  background: var(--color-background-mute);
  padding: 2px 6px;
  border-radius: 3px;
}

.recording-details {
  font-size: 0.9em;
}

.stream-title {
  color: var(--color-text);
  margin-bottom: 4px;
  font-weight: 500;
}

.file-path {
  color: var(--color-text-light);
  font-family: monospace;
  margin-bottom: 4px;
  word-break: break-all;
}

.recording-meta {
  color: var(--color-text-light);
}

.text-success { color: var(--success-color) !important; }
.text-danger { color: var(--danger-color) !important; }

.result-summary {
  margin-bottom: 20px;
}

.result-message {
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 10px;
  font-weight: 500;
}

.result-message.success {
  background: rgba(40, 167, 69, 0.1);
  color: #28a745;
  border: 1px solid rgba(40, 167, 69, 0.3);
}

.result-message.error {
  background: rgba(220, 53, 69, 0.1);
  color: #dc3545;
  border: 1px solid rgba(220, 53, 69, 0.3);
}

.result-stats {
  font-size: 0.9em;
  color: var(--color-text-light);
}

.errors-list {
  margin-bottom: 20px;
}

.errors-list ul {
  margin: 10px 0;
  padding-left: 20px;
}

.errors-list li {
  color: #dc3545;
  margin-bottom: 5px;
}

.details-grid {
  display: grid;
  gap: 8px;
}

.detail-item {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  gap: 15px;
  align-items: center;
  padding: 8px 12px;
  background: var(--color-background-mute);
  border-radius: 4px;
  border: 1px solid var(--color-border);
}

.detail-id {
  font-weight: bold;
  color: var(--color-heading);
}

.detail-streamer {
  color: var(--color-text);
}

.detail-status.success {
  color: #28a745;
}

.detail-status.error {
  color: #dc3545;
}

.detail-error {
  font-size: 0.8em;
  color: #dc3545;
}

.loading {
  text-align: center;
  padding: 40px;
  color: var(--color-text-light);
}

.no-data {
  text-align: center;
  padding: 40px;
  color: var(--color-text-light);
  font-style: italic;
}

@media (max-width: 768px) {
  .action-buttons {
    grid-template-columns: 1fr;
  }
  
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .recording-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 5px;
  }
  
  .detail-item {
    grid-template-columns: 1fr;
    gap: 5px;
  }
}
</style>
