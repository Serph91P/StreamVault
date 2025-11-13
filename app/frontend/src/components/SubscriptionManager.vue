<template>
  <div class="subscription-manager">
    <div class="controls">
      <button @click="loadSubscriptions" class="btn btn-primary">
        Check Subscriptions
      </button>
      <button @click="deleteAllSubscriptions" class="btn btn-danger">
        Delete All Subscriptions
      </button>
      <button @click="resubscribeAll" class="btn btn-success">
        Resubscribe All
      </button>
    </div>

    <div v-if="subscriptions.length" class="subscription-list">
      <div v-for="sub in subscriptions" :key="sub.id" class="subscription-item card">
        <div class="subscription-info">
          <span>Type: {{ formatType(sub.type) }}</span>
          <span class="status-badge" :class="sub.status">
            {{ sub.status }}
          </span>
          <span>Created: {{ new Date(sub.created_at).toLocaleString() }}</span>
        </div>
        <button @click="deleteSubscription(sub.id)" class="btn btn-danger">
          Delete
        </button>
      </div>
    </div>
    <div v-else class="empty-state">
      No subscriptions found
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const subscriptions = ref([])

async function loadSubscriptions() {
  const response = await fetch('/api/streamers/subscriptions')
  const data = await response.json()
  subscriptions.value = data.subscriptions
}

async function deleteSubscription(id) {
  await fetch(`/api/streamers/subscriptions/${id}`, {
    method: 'DELETE'
  })
  await loadSubscriptions()
}

async function deleteAllSubscriptions() {
  if (!confirm('Are you sure you want to delete all subscriptions?')) return
  
  await fetch('/api/streamers/subscriptions', {
    method: 'DELETE'
  })
  subscriptions.value = []
}

async function resubscribeAll() {
  if (!confirm('Are you sure you want to resubscribe to all streamers?')) return
  
  try {
    const response = await fetch('/api/streamers/resubscribe-all', {
      method: 'POST'
    })
    
    if (response.ok) {
      const data = await response.json()
      const count = data.total_processed || data.success_count || data.count || 'all'
      const message = data.message || `Resubscribed to ${count} streamers successfully`
      alert(`Success: ${message}`)
      await loadSubscriptions()
    } else {
      const error = await response.json()
      alert('Error resubscribing: ' + error.detail)
    }
  } catch (error) {
    alert('Error resubscribing: ' + error.message)
  }
}

function formatType(type) {
  switch (type) {
    case 'stream.online':
      return 'Stream Start'
    case 'stream.offline':
      return 'Stream End'
    case 'channel.update':
      return 'Channel Update'
    default:
      return type
  }
}
</script>

<style scoped lang="scss">
.subscription-manager {
  max-width: 1000px;
  margin: 0 auto;
}

.controls {
  display: flex;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  flex-wrap: wrap;
}

.subscription-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.subscription-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
}

.subscription-info {
  display: flex;
  gap: var(--spacing-lg);
  align-items: center;
  flex-wrap: wrap;
}

.empty-state {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-secondary);
}
</style>
