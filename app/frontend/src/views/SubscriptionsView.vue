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

      <button 
          @click="resubscribeAll" 
          class="btn btn-success" 
          :disabled="loadingResubscribe"
        >
          {{ loadingResubscribe ? 'Resubscribing...' : 'Resubscribe All Streamers' }}
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
            <td>
              <div class="streamer-info">
                <span class="streamer-name">
                  {{ getStreamerName(sub.condition?.broadcaster_user_id) }}
                </span>
              </div>
            </td>
            <td>{{ formatEventType(sub.type) }}</td>
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

interface Streamer {
  id: number
  twitch_id: string
  username: string
}

const subscriptions = ref<Subscription[]>([])
const streamers = ref<Streamer[]>([])
const streamerMap = ref<Record<string, string>>({})
const loadingResubscribe = ref(false)
const loading = ref(false)

function formatEventType(type: string): string {
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

function getStreamerName(twitchId: string): string {
  if (!twitchId) return 'Unknown';
  
  // Try finding the streamer by exact match first
  let streamer = streamers.value.find(s => String(s.twitch_id) === String(twitchId));
  
  if (streamer) {
    return streamer.username;
  }
  
  // Log this issue for debugging
  console.log(`Could not find streamer for ID: ${twitchId}`);
  console.log("Available streamers:", streamers.value);
  
  // Return a formatted version of the ID as fallback
  return `Unknown (${twitchId})`;
}

async function loadStreamers() {
  try {
    const response = await fetch('/api/streamers')
    const data = await response.json()
    streamers.value = data.streamers || []
    
    // Refresh subscriptions after streamers are loaded
    // to ensure streamer names can be displayed
    if (subscriptions.value.length > 0) {
      // Force a reactive update
      subscriptions.value = [...subscriptions.value];
    }
    
    console.log("Loaded streamers:", streamers.value)
  } catch (error) {
    console.error('Failed to load streamers:', error)
  }
}

async function loadSubscriptions() {
  loading.value = true
  try {
    const response = await fetch('/api/streamers/subscriptions')
    const data = await response.json()
    subscriptions.value = data.subscriptions
    
    // Wichtig: Lade Streamer erst nachdem Subscriptions geladen wurden
    await loadStreamers()
  } catch (error) {
    console.error('Failed to load subscriptions:', error)
  } finally {
    loading.value = false
  }
}

async function resubscribeAll() {
  loadingResubscribe.value = true
  try {
    const response = await fetch('/api/streamers/resubscribe-all', {
      method: 'POST',
      headers: {
        'Accept': 'application/json'
      }
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error('Server response:', errorText)
      throw new Error(`Failed to resubscribe: ${response.status}`)
    }
    
    const data = await response.json()
    alert(`Success: ${data.message}`)
    
    await loadSubscriptions()
    
  } catch (error: any) {
    console.error('Failed to resubscribe all:', error.message)
    alert(`Error: ${error.message}`)
  } finally {
    loadingResubscribe.value = false
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
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error('Server response:', errorText)
      throw new Error(`Failed to delete subscriptions: ${response.status}`)
    }
    
    const data = await response.json()
    console.log('Deleted subscriptions:', data)
    alert('All subscriptions successfully deleted!')
    
    subscriptions.value = []
    await loadSubscriptions()
  } catch (error: any) {
    console.error('Failed to delete all subscriptions:', error.message)
    alert(`Error: ${error.message}`)
  } finally {
    loading.value = false
  }
}

onMounted(loadSubscriptions)
</script>