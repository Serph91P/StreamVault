<template>
  <div class="subscriptions-page">
    <h2>Subscription Management</h2>
    
    <div class="controls">
      <button @click="loadSubscriptions" :disabled="loading" class="btn primary">
        {{ loading ? 'Loading...' : 'Refresh Subscriptions' }}
      </button>
      <button @click="deleteAllSubscriptions" :disabled="loading || !subscriptions.length" class="btn danger">
        Delete All Subscriptions
      </button>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading subscriptions...</p>
    </div>

    <div v-else-if="subscriptions.length" class="subscription-table">
      <table>
        <thead>
          <tr>
            <th>Type</th>
            <th>Status</th>
            <th>Created At</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="sub in subscriptions" :key="sub.id">
            <td>{{ sub.type }}</td>
            <td><span :class="['status', sub.status]">{{ sub.status }}</span></td>
            <td>{{ new Date(sub.created_at).toLocaleString() }}</td>
            <td>
              <button @click="deleteSubscription(sub.id)" class="btn danger small">
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="empty-state">
      <p>No subscriptions found</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const subscriptions = ref([])
const loading = ref(false)

async function loadSubscriptions() {
  loading.value = true
  try {
    const response = await fetch('/api/streamers/subscriptions')
    const data = await response.json()
    subscriptions.value = data.subscriptions
  } catch (error) {
    console.error('Failed to load subscriptions:', error)
  } finally {
    loading.value = false
  }
}

async function deleteSubscription(id) {
  try {
    await fetch(`/api/streamers/subscriptions/${id}`, {
      method: 'DELETE'
    })
    await loadSubscriptions()
  } catch (error) {
    console.error('Failed to delete subscription:', error)
  }
}

async function deleteAllSubscriptions() {
  if (!confirm('Are you sure you want to delete all subscriptions?')) return
  
  loading.value = true
  try {
    await fetch('/api/streamers/subscriptions', {
      method: 'DELETE'
    })
    subscriptions.value = []
  } catch (error) {
    console.error('Failed to delete all subscriptions:', error)
  } finally {
    loading.value = false
  }
}

onMounted(loadSubscriptions)
</script>

<style scoped>
.subscriptions-page {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.controls {
  margin-bottom: 2rem;
  display: flex;
  gap: 1rem;
}

.subscription-table {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 1rem;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.status {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.875rem;
}

.status.enabled {
  background: #e6f4ea;
  color: #1e7e34;
}

.status.disabled {
  background: #fce8e8;
  color: #dc3545;
}

.loading-state {
  text-align: center;
  padding: 2rem;
}

.spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #3498db;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-weight: 500;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn.primary {
  background: #3498db;
  color: white;
}

.btn.danger {
  background: #dc3545;
  color: white;
}

.btn.small {
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #666;
}
</style>
