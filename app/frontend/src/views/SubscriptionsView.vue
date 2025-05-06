<template>
  <div class="subscriptions-view">
    <div class="subscriptions-container">
      <div class="page-header">
        <h2>Subscription Management</h2>
      </div>
      
      <div class="content-section">
        <div class="controls">
          <button @click="loadSubscriptions" :disabled="loading" class="btn btn-primary">
            {{ loading ? 'Loading...' : 'Refresh Subscriptions' }}
          </button>
          <button @click="deleteAllSubscriptions" :disabled="loading || !subscriptions.length" class="btn btn-danger">
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

        <div v-else-if="subscriptions.length" class="table-container">
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
                          class="btn btn-danger" 
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'

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
  profile_image_url?: string
}

const subscriptions = ref<Subscription[]>([])
const streamers = ref<Streamer[]>([])
const streamerMap = ref<Record<string, Streamer>>({})
const loadingResubscribe = ref(false)
const loading = ref(false)

// Create a computed map of twitch_id to streamer object for easier lookup
const twitchIdToStreamerMap = computed(() => {
  const map: Record<string, Streamer> = {}
  streamers.value.forEach(streamer => {
    map[streamer.twitch_id] = streamer
  })
  return map
})

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
  if (!twitchId) return 'Unknown'
  
  // Use the computed map for faster lookup
  const streamer = twitchIdToStreamerMap.value[twitchId]
  
  if (streamer) {
    return streamer.username
  }
  
  // Log this issue for debugging
  console.log(`Could not find streamer for ID: ${twitchId}`)
  console.log("Available streamers:", streamers.value)
  
  // Return a formatted version of the ID as fallback
  return `Unknown (${twitchId})`
}

async function loadStreamers() {
  try {
    const response = await fetch('/api/streamers')
    const data = await response.json()
    
    if (Array.isArray(data)) {
      // If the API returns an array directly
      streamers.value = data
    } else if (data.streamers && Array.isArray(data.streamers)) {
      // If the API returns {streamers: [...]}
      streamers.value = data.streamers
    } else {
      console.error('Unexpected streamer data format:', data)
      streamers.value = []
    }
    
    console.log("Loaded streamers:", streamers.value)
    
    // Create a map for easier lookup
    streamers.value.forEach(streamer => {
      streamerMap.value[streamer.twitch_id] = streamer
    })
    
    // Force a reactive update if needed
    if (subscriptions.value.length > 0) {
      subscriptions.value = [...subscriptions.value]
    }
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
    
    // Load streamers after subscriptions
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