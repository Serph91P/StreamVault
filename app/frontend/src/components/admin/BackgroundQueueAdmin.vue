<template>
  <div class="background-queue-admin">
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
        const response = await fetch('/api/admin/background-queue/status', {
          credentials: 'include' // CRITICAL: Required to send session cookie
        })
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
          method: 'POST',
          credentials: 'include' // CRITICAL: Required to send session cookie
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

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.background-queue-admin {
  width: 100%;
}

.status-card {
  background: var(--background-tertiary);
  border-radius: var(--radius-md);
  padding: var(--spacing-5);
  margin-bottom: var(--spacing-5);
  border: 1px solid var(--border-color);
}

.status-card h4 {
  margin: 0 0 var(--spacing-4) 0;
  color: var(--text-primary);
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-4);
}

.status-item {
  display: flex;
  justify-content: space-between;
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--background-card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.status-item.error {
  background: var(--danger-bg-color);
  border-color: var(--danger-border-color);
}

.status-item .label {
  color: var(--text-secondary);
  font-weight: var(--font-medium);
}

.status-item .value {
  color: var(--text-primary);
  font-weight: var(--font-bold);
}

.total-issues {
  text-align: center;
  margin-top: var(--spacing-4);
}

.issues-badge {
  display: inline-block;
  padding: var(--spacing-2) var(--spacing-4);
  border-radius: var(--radius-full);
  font-weight: var(--font-bold);
}

.issues-badge.error {
  background: var(--danger-color);
  color: var(--text-on-primary);
}

.issues-badge.success {
  background: var(--success-color);
  color: var(--text-on-primary);
}

.problem-details {
  background: var(--background-tertiary);
  border-radius: var(--radius-md);
  padding: var(--spacing-5);
  margin-bottom: var(--spacing-5);
  border: 1px solid var(--border-color);
}

.problem-details h4 {
  margin: 0 0 var(--spacing-4) 0;
  color: var(--text-primary);
}

.problem-section {
  margin-bottom: var(--spacing-4);
}

.problem-section h5 {
  margin: 0 0 var(--spacing-2) 0;
  color: var(--text-primary);
  font-size: var(--text-base);
}

.task-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.task-item {
  background: var(--background-card);
  padding: var(--spacing-1) var(--spacing-2);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-5);
}

/* Using global .btn classes from main.scss */

.result-messages {
  margin-top: var(--spacing-5);
}

.result-message {
  padding: var(--spacing-4);
  border-radius: var(--radius-md);
}

.result-message.success {
  background: var(--success-bg-color);
  border: 1px solid var(--success-border-color);
}

.result-message.error {
  background: var(--danger-bg-color);
  border: 1px solid var(--danger-border-color);
}

.result-message h5 {
  margin: 0 0 var(--spacing-2) 0;
  color: var(--text-primary);
}

.result-message p {
  margin: 0 0 var(--spacing-3) 0;
  color: var(--text-primary);
}

.result-details {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.result-details > div {
  margin-bottom: var(--spacing-1);
}

.total-fixed {
  margin-top: var(--spacing-2);
  padding-top: var(--spacing-2);
  border-top: 1px solid var(--border-color);
}

.error-details {
  margin-top: var(--spacing-3);
  padding-top: var(--spacing-3);
  border-top: 1px solid var(--border-color);
}

.error-details h6 {
  margin: 0 0 var(--spacing-2) 0;
  color: var(--danger-color);
}

.error-details ul {
  margin: 0;
  padding-left: var(--spacing-5);
}

.error-details li {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

@include m.respond-below('md') {
  .action-buttons {
    flex-direction: column;
  }
  
  .status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
