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

    <div v-else-if="subscriptions.length" class="streamer-table-container">
      <table class="streamer-table">
        <thead>
          <tr>
            <th>Streamer</th>
            <th>Type</th>
            <th>Status</th>
            <th>Created At</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="sub in subscriptions" :key="sub.id">
            <td>{{ sub.broadcaster_name || sub.condition?.broadcaster_user_id }}</td>
            <td>{{ sub.type }}</td>
            <td>
              <span class="status-badge" :class="sub.status">
                {{ sub.status }}
              </span>
            </td>
            <td>{{ new Date(sub.created_at).toLocaleString() }}</td>
            <td>
              <button @click="deleteSubscription(sub.id)" 
                      class="delete-btn" 
                      :disabled="loading">
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
  <script setup lang="ts">
  import { ref, onMounted } from 'vue'

  interface Subscription {
    id: string
    type: string
    status: string
    created_at: string
    broadcaster_id?: string
    broadcaster_name?: string
    condition: {
      broadcaster_user_id: string
    }
  }

  const subscriptions = ref<Subscription[]>([])
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

  async function deleteSubscription(id: string) {
    try {
      const response = await fetch(`/api/streamers/subscriptions/${id}`, {
        method: 'DELETE'
      })
      if (!response.ok) throw new Error('Failed to delete subscription')
    
      subscriptions.value = subscriptions.value.filter(sub => sub.id !== id)
    } catch (error) {
      console.error('Failed to delete subscription:', error)
    }
  }

  async function deleteAllSubscriptions() {
    if (!confirm('Are you sure you want to delete all subscriptions?')) return
  
    loading.value = true
    try {
      const response = await fetch('/api/streamers/subscriptions', {
        method: 'DELETE',
        headers: {
          'Accept': 'application/json'
        }
      })
    
      const data = await response.json()
    
      if (!response.ok) {
        throw new Error(data.error || 'Failed to delete subscriptions')
      }
    
      subscriptions.value = []
      await loadSubscriptions()
    } catch (error) {
      console.error('Failed to delete all subscriptions:', error.message)
    } finally {
      loading.value = false
    }
  }

  onMounted(loadSubscriptions)
  </script>
<style scoped>