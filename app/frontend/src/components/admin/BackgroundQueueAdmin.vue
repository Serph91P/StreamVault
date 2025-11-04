<template>
  <div class="background-queue-admin">
    <div class="admin-section">
      <div class="section-header">
        <h3>🔧 Background Queue Management</h3>
        <p class="section-description">
          Automatically fix Background Queue issues:
          Recording jobs that get stuck, continuous Orphaned Recovery, and "Unknown" task names.
        </p>
      </div>

      <!-- Status Overview -->
      <div class="status-card" v-if="status">
        <h4>📊 Current Status</h4>
        <div class="status-grid">
          <div class="status-item">
            <span class="label">External Tasks:</span>
            <span class="value">{{ status.total_external_tasks }}</span>
          </div>
          <div class="status-item">
            <span class="label">Active Tasks:</span>
            <span class="value">{{ status.total_active_tasks }}</span>
          </div>
          <div class="status-item error status-border status-border-error" v-if="status.stuck_recordings > 0">
            <span class="label">Stuck Recordings:</span>
            <span class="value">{{ status.stuck_recordings }}</span>
          </div>
          <div class="status-item error status-border status-border-error" v-if="status.continuous_orphaned > 0">
            <span class="label">Continuous Orphaned:</span>
            <span class="value">{{ status.continuous_orphaned }}</span>
          </div>
          <div class="status-item error status-border status-border-error" v-if="status.unknown_tasks > 0">
            <span class="label">Unknown Tasks:</span>
            <span class="value">{{ status.unknown_tasks }}</span>
          </div>
        </div>
        
        <div class="total-issues" v-if="status.total_issues > 0">
          <span class="issues-badge error">
            ⚠️ {{ status.total_issues }} Issues Detected
          </span>
        </div>
        <div class="total-issues" v-else>
          <span class="issues-badge success">
            ✅ No Issues Detected
          </span>
        </div>
      </div>

      <!-- Problem Details -->
      <div class="problem-details" v-if="status && status.total_issues > 0">
        <h4>🔍 Problem Details</h4>
        
        <div class="problem-section" v-if="status.stuck_recording_tasks.length > 0">
          <h5>Stuck Recording Jobs:</h5>
          <div class="task-list">
            <div class="task-item" v-for="taskId in status.stuck_recording_tasks" :key="taskId">
              {{ taskId }}
            </div>
          </div>
        </div>
        
        <div class="problem-section" v-if="status.orphaned_recovery_tasks.length > 0">
          <h5>Continuous Orphaned Recovery:</h5>
          <div class="task-list">
            <div class="task-item" v-for="taskId in status.orphaned_recovery_tasks" :key="taskId">
              {{ taskId }}
            </div>
          </div>
        </div>
        
        <div class="problem-section" v-if="status.unknown_task_names.length > 0">
          <h5>Unknown Task Names:</h5>
          <div class="task-list">
            <div class="task-item" v-for="taskId in status.unknown_task_names" :key="taskId">
              {{ taskId }}
            </div>
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="action-buttons">
        <button 
          @click="refreshStatus" 
          :disabled="loading"
          class="btn btn-secondary"
        >
          <span v-if="loading">🔄</span>
          <span v-else>🔄</span>
          Refresh Status
        </button>

        <button 
          @click="fixAllIssues" 
          :disabled="loading || !status || status.total_issues === 0"
          class="btn btn-primary"
        >
          <span v-if="loading">⏳</span>
          <span v-else>🧹</span>
          Fix All Issues
        </button>

        <button 
          @click="fixStuckRecordings" 
          :disabled="loading || !status || status.stuck_recordings === 0"
          class="btn btn-warning"
        >
          <span v-if="loading">⏳</span>
          <span v-else>🔧</span>
          Fix Stuck Recordings Only
        </button>

        <button 
          @click="stopOrphanedRecovery" 
          :disabled="loading || !status || status.continuous_orphaned === 0"
          class="btn btn-warning"
        >
          <span v-if="loading">⏳</span>
          <span v-else>🛑</span>
          Stop Orphaned Recovery
        </button>

        <button 
          @click="fixTaskNames" 
          :disabled="loading || !status || status.unknown_tasks === 0"
          class="btn btn-warning"
        >
          <span v-if="loading">⏳</span>
          <span v-else>🏷️</span>
          Fix Task Names
        </button>
      </div>

      <!-- Result Messages -->
      <div class="result-messages" v-if="lastResult">
        <div 
          class="result-message status-border"
          :class="[
            { success: lastResult.success, error: !lastResult.success },
            lastResult.success ? 'status-border-success' : 'status-border-error'
          ]"
        >
          <h5>{{ lastResult.success ? '✅' : '❌' }} Result</h5>
          <p>{{ lastResult.message }}</p>
          
          <div class="result-details" v-if="lastResult.success">
            <div v-if="lastResult.stuck_recordings_fixed > 0">
              🔧 Stuck Recordings Fixed: {{ lastResult.stuck_recordings_fixed }}
            </div>
            <div v-if="lastResult.orphaned_recovery_stopped > 0">
              🛑 Orphaned Recovery Stopped: {{ lastResult.orphaned_recovery_stopped }}
            </div>
            <div v-if="lastResult.task_names_fixed > 0">
              🏷️ Task Names Fixed: {{ lastResult.task_names_fixed }}
            </div>
            <div v-if="lastResult.total_issues_fixed > 0" class="total-fixed">
              <strong>🎯 Total Fixed: {{ lastResult.total_issues_fixed }}</strong>
            </div>
          </div>
          
          <div class="error-details" v-if="lastResult.errors && lastResult.errors.length > 0">
            <h6>Errors:</h6>
            <ul>
              <li v-for="error in lastResult.errors" :key="error">{{ error }}</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'

export default {
  name: 'BackgroundQueueAdmin',
  setup() {
    const status = ref(null)
    const lastResult = ref(null)
    const loading = ref(false)

    const refreshStatus = async () => {
      loading.value = true
      try {
        const response = await fetch('/api/admin/background-queue/status')
        if (response.ok) {
          status.value = await response.json()
          console.log('Background queue status refreshed:', status.value)
        } else {
          throw new Error('Failed to fetch status')
        }
      } catch (error) {
        console.error('Error fetching background queue status:', error)
        lastResult.value = {
          success: false,
          message: 'Error loading status: ' + error.message
        }
      } finally {
        loading.value = false
      }
    }

    const performCleanup = async (endpoint, actionName) => {
      loading.value = true
      lastResult.value = null
      
      try {
        const response = await fetch(`/api/admin/background-queue/cleanup/${endpoint}`, {
          method: 'POST'
        })
        
        if (response.ok) {
          const result = await response.json()
          lastResult.value = result
          console.log(`${actionName} completed:`, result)
          
          // Refresh status after successful cleanup
          setTimeout(() => {
            refreshStatus()
          }, 1000)
        } else {
          const errorText = await response.text()
          throw new Error(`HTTP ${response.status}: ${errorText}`)
        }
      } catch (error) {
        console.error(`Error in ${actionName}:`, error)
        lastResult.value = {
          success: false,
          message: `Error in ${actionName}: ${error.message}`,
          errors: [error.message]
        }
      } finally {
        loading.value = false
      }
    }

    const fixAllIssues = () => performCleanup('all', 'Complete Cleanup')
    const fixStuckRecordings = () => performCleanup('stuck-recordings', 'Stuck Recordings Fix')
    const stopOrphanedRecovery = () => performCleanup('orphaned-recovery', 'Orphaned Recovery Stop')
    const fixTaskNames = () => performCleanup('task-names', 'Task Names Fix')

    // Load status on component mount
    onMounted(() => {
      refreshStatus()
      
      // Auto-refresh every 30 seconds
      setInterval(refreshStatus, 30000)
    })

    return {
      status,
      lastResult,
      loading,
      refreshStatus,
      fixAllIssues,
      fixStuckRecordings,
      stopOrphanedRecovery,
      fixTaskNames
    }
  }
}
</script>

<style scoped>
.background-queue-admin {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
}

.admin-section {
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 20px;
}

.section-header {
  margin-bottom: 24px;
}

.section-header h3 {
  margin: 0 0 8px 0;
  color: var(--text-primary);
  font-size: 1.5rem;
}

.section-description {
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.status-card {
  background: var(--bg-primary);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  border: 1px solid var(--border-color);
}

.status-card h4 {
  margin: 0 0 16px 0;
  color: var(--text-primary);
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 4px;
}

.status-item.error {
  background: var(--error-bg, #fee);
  /* Border color handled by .status-border-* classes */
}

.status-item .label {
  color: var(--text-secondary);
  font-weight: 500;
}

.status-item .value {
  color: var(--text-primary);
  font-weight: bold;
}

.total-issues {
  text-align: center;
  margin-top: 16px;
}

.issues-badge {
  display: inline-block;
  padding: 8px 16px;
  border-radius: 20px;
  font-weight: bold;
}

.issues-badge.error {
  background: var(--error-color, #dc3545);
  color: white;
}

.issues-badge.success {
  background: var(--success-color, #28a745);
  color: white;
}

.problem-details {
  background: var(--bg-primary);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  border: 1px solid var(--border-color);
}

.problem-details h4 {
  margin: 0 0 16px 0;
  color: var(--text-primary);
}

.problem-section {
  margin-bottom: 16px;
}

.problem-section h5 {
  margin: 0 0 8px 0;
  color: var(--text-primary);
  font-size: 1rem;
}

.task-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.task-item {
  background: var(--bg-secondary);
  padding: 4px 8px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
}

.btn {
  padding: 10px 16px;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 140px;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--primary-color, #007bff);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover, #0056b3);
}

.btn-secondary {
  background: var(--secondary-color, #6c757d);
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background: var(--secondary-hover, #545b62);
}

.btn-warning {
  background: var(--warning-color, #ffc107);
  color: #212529;
}

.btn-warning:hover:not(:disabled) {
  background: var(--warning-hover, #e0a800);
}

.result-messages {
  margin-top: 20px;
}

.result-message {
  padding: 16px;
  border-radius: 8px;
  /* Border color handled by .status-border-* classes */
}

.result-message.success {
  background: var(--success-bg, #d4edda);
  /* Border color handled by .status-border-* classes */
}

.result-message.error {
  background: var(--error-bg, #f8d7da);
  /* Border color handled by .status-border-* classes */
}

.result-message h5 {
  margin: 0 0 8px 0;
  color: var(--text-primary);
}

.result-message p {
  margin: 0 0 12px 0;
  color: var(--text-primary);
}

.result-details {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.result-details > div {
  margin-bottom: 4px;
}

.total-fixed {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
}

.error-details {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.error-details h6 {
  margin: 0 0 8px 0;
  color: var(--error-color, #dc3545);
}

.error-details ul {
  margin: 0;
  padding-left: 20px;
}

.error-details li {
  color: var(--text-secondary);
  font-size: 0.9rem;
}
</style>
