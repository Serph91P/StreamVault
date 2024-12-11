<template>
  <div class="streamer-table-container">
    <table class="streamer-table">
      <thead>
        <tr>
          <th @click="sortBy('username')">
            Streamer
            <span class="sort-icon">{{ sortKey === 'username' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
          </th>
          <th @click="sortBy('status')">
            Status
            <span class="sort-icon">{{ sortKey === 'status' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
          </th>
          <th>Title</th>
          <th>Category</th>
          <th>Language</th>
          <th @click="sortBy('lastUpdate')">
            Last Update
            <span class="sort-icon">{{ sortKey === 'lastUpdate' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
          </th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="streamer in sortedStreamers" 
            :key="streamer.id"
            :class="{ 'live': streamer.is_live }">
          <td>
            <div class="streamer-info">
              <span class="status-dot" :class="{ 'live': streamer.is_live }"></span>
              {{ streamer.username }}
            </div>
          </td>
          <td>
            <span class="status-badge" :class="{ 'live': streamer.is_live }">
              {{ streamer.is_live ? 'LIVE' : 'OFFLINE' }}
            </span>
          </td>
          <td>{{ streamer.title || '-' }}</td>
          <td>{{ streamer.category || '-' }}</td>
          <td>{{ streamer.language || '-' }}</td>
          <td>{{ formatDate(streamer.last_updated) }}</td>
          <td>
            <button 
              @click.prevent="deleteStreamer(streamer.id)" 
              class="delete-btn"
              :disabled="isDeleting"
            >
              {{ isDeleting ? 'Deleting...' : 'Delete' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const streamers = ref([])
const sortKey = ref('username')
const sortDir = ref('asc')
const isDeleting = ref(false)

const sortedStreamers = computed(() => {
  return [...streamers.value].sort((a, b) => {
    const modifier = sortDir.value === 'asc' ? 1 : -1
    if (a[sortKey.value] < b[sortKey.value]) return -1 * modifier
    if (a[sortKey.value] > b[sortKey.value]) return 1 * modifier
    return 0
  })
})

const sortBy = (key) => {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

const fetchStreamers = async () => {
  try {
    const response = await fetch('/api/streamers')
    if (!response.ok) throw new Error('Failed to fetch streamers')
    const data = await response.json()
    streamers.value = data
  } catch (error) {
    console.error('Failed to fetch streamers:', error)
  }
}

const deleteStreamer = async (streamerId) => {
  if (!streamerId || isDeleting.value) return
  
  if (window.confirm('Are you sure you want to delete this streamer?')) {
    isDeleting.value = true
    try {
      const response = await fetch(`/api/streamers/${streamerId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      })
      
      if (response.ok) {
        console.log('Streamer deleted successfully')
        await fetchStreamers()
      } else {
        const errorData = await response.json()
        console.error('Failed to delete streamer:', errorData)
      }
    } catch (error) {
      console.error('Error deleting streamer:', error)
    } finally {
      isDeleting.value = false
    }
  }
}

const formatDate = (date) => {
  if (!date) return 'Never'
  return new Date(date).toLocaleString()
}

// Initial load and polling setup
onMounted(() => {
  fetchStreamers()
  const pollInterval = setInterval(fetchStreamers, 60000)
  
  // Cleanup on component unmount
  onUnmounted(() => {
    clearInterval(pollInterval)
  })
})
</script>

<style scoped>
.streamer-table-container {
  overflow-x: auto;
  background: #242424;
  border-radius: 8px;
  border: 1px solid #383838;
  margin: 20px 0;
}

.streamer-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  color: #fff;
}

th {
  background: #2f2f2f;
  padding: 12px;
  cursor: pointer;
  border-bottom: 1px solid #383838;
  user-select: none;
}

th:hover {
  background: #383838;
}

td {
  padding: 12px;
  border-bottom: 1px solid #383838;
}

.sort-icon {
  font-size: 0.8em;
  margin-left: 4px;
  opacity: 0.7;
}

.streamer-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ff4444;
  transition: background-color 0.3s;
}

.status-dot.live {
  background: #44ff44;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.8em;
  font-weight: bold;
  background: #dc3545;
  color: #fff;
}

.status-badge.live {
  background: #28a745;
}

tr {
  transition: background-color 0.2s;
}

tr:hover {
  background: #2f2f2f;
}

.delete-btn {
  background: #dc3545;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.delete-btn:hover:not(:disabled) {
  background: #c82333;
}

.delete-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.6; }
  100% { opacity: 1; }
}

tr.live {
  animation: pulse 2s infinite;
}
</style>
