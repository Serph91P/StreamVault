<template>
  <div class="post-processing-management">
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

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.post-processing-management {
  width: 100%;
}

.card {
  background: var(--background-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-5);
}

.card-header {
  padding: var(--spacing-4) var(--spacing-5);
  border-bottom: 1px solid var(--border-color);
  background: var(--background-card);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h4 {
  margin: 0;
  color: var(--text-primary);
}

.card-body {
  padding: var(--spacing-5);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: var(--spacing-4);
  background: var(--background-card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.stat-value {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-1);
}

.stat-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.streamer-breakdown {
  margin-top: var(--spacing-5);
  padding-top: var(--spacing-5);
  border-top: 1px solid var(--border-color);
}

.streamer-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: var(--spacing-3);
  margin-top: var(--spacing-3);
}

.streamer-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--background-card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.streamer-name {
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.streamer-stats {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-5);
}

.settings-row {
  display: flex;
  gap: var(--spacing-5);
  align-items: center;
  padding-top: var(--spacing-4);
  border-top: 1px solid var(--border-color);
}

.settings-row label {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.form-input {
  padding: var(--spacing-2) var(--spacing-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  width: 80px;
  background: var(--background-card);
  color: var(--text-primary);
}

/* Using global .btn classes from main.scss */

.btn {
  padding: var(--spacing-2_5) var(--spacing-5);
  border: none;
  border-radius: var(--radius-sm);
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

/* Bootstrap button colors removed - using global .btn-* classes from main.scss */

.btn-sm {
  padding: var(--spacing-1_5) var(--spacing-3);
  font-size: 0.8em;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}

.list-controls {
  display: flex;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-4);
  padding-bottom: var(--spacing-4);
  border-bottom: 1px solid var(--border-color);
}

.recordings-list {
  max-height: 600px;
  overflow-y: auto;
}

.recording-item {
  margin-bottom: var(--spacing-3);
}

.recording-checkbox {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-3);
  padding: var(--spacing-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s;
  background: var(--background-card);
}

.recording-checkbox:hover {
  background: var(--background-tertiary);
  border-color: var(--primary-color);
}

.recording-checkbox input[type="checkbox"] {
  margin-top: var(--spacing-1);
}

.recording-info {
  flex: 1;
}

.recording-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-4);
  margin-bottom: var(--spacing-2);
}

.recording-id {
  font-weight: var(--font-bold);
  color: var(--primary-color);
}

.streamer-name {
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.file-size {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  background: var(--background-tertiary);
  padding: var(--spacing-1) var(--spacing-2);
  border-radius: var(--radius-sm);
}

.recording-details {
  font-size: var(--text-sm);
}

.stream-title {
  color: var(--text-primary);
  margin-bottom: var(--spacing-1);
  font-weight: var(--font-medium);
}

.file-path {
  color: var(--text-secondary);
  font-family: var(--font-mono);
  margin-bottom: var(--spacing-1);
  word-break: break-all;
}

.recording-meta {
  color: var(--text-secondary);
}

.text-success { color: var(--success-color) !important; }
.text-danger { color: var(--danger-color) !important; }

.result-summary {
  margin-bottom: var(--spacing-5);
}

.result-message {
  padding: var(--spacing-4);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-3);
  font-weight: var(--font-medium);
}

.result-message.success {
  background: var(--success-bg-color);
  color: var(--success-color);
  border: 1px solid var(--success-border-color);
}

.result-message.error {
  background: var(--danger-bg-color);
  color: var(--danger-color);
  border: 1px solid var(--danger-border-color);
}

.result-stats {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.errors-list {
  margin-bottom: var(--spacing-5);
}

.errors-list ul {
  margin: var(--spacing-3) 0;
  padding-left: var(--spacing-5);
}

.errors-list li {
  color: var(--danger-color);
  margin-bottom: var(--spacing-1);
}

.details-grid {
  display: grid;
  gap: var(--spacing-2);
}

.detail-item {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  gap: var(--spacing-4);
  align-items: center;
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--background-card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.detail-id {
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.detail-streamer {
  color: var(--text-primary);
}

.detail-status.success {
  color: var(--success-color);
}

.detail-status.error {
  color: var(--danger-color);
}

.detail-error {
  font-size: var(--text-xs);
  color: var(--danger-color);
}

.loading {
  text-align: center;
  padding: var(--spacing-10);
  color: var(--text-secondary);
}

.no-data {
  text-align: center;
  padding: var(--spacing-10);
  color: var(--text-secondary);
  font-style: italic;
}

@include m.respond-below('md') {
  .action-buttons {
    flex-direction: column;
  }
  
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .recording-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-1);
  }
  
  .detail-item {
    grid-template-columns: 1fr;
    gap: var(--spacing-1);
  }
}
</style>
