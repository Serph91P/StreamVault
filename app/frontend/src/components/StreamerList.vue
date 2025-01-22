<template>
  <div class="container">
    <div class="streamer-grid">
      <div v-for="streamer in sortedStreamers" 
           :key="streamer.id"
           class="streamer-card">
        <div class="streamer-header">
          <div class="streamer-info">
            <span class="status-dot" :class="{ 'live': streamer.is_live }"></span>
            <h3>{{ streamer.username }}</h3>
          </div>
          <span class="status-badge interactive-element" :class="{ 'live': streamer.is_live }">
            {{ streamer.is_live ? 'LIVE' : 'OFFLINE' }}
          </span>
        </div>
        <div class="streamer-content">
          <p class="title">{{ streamer.title || '-' }}</p>
          <p class="category">{{ streamer.category || '-' }}</p>
          <p class="language">{{ streamer.language || '-' }}</p>
          <p class="last-update">{{ formatDate(streamer.last_updated) }}</p>
        </div>
        <button 
          @click="deleteStreamer(streamer.id)" 
          class="delete-btn interactive-element"
          :disabled="isDeleting"
        >
          {{ isDeleting ? 'Deleting...' : 'Delete' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

interface Streamer {
  id: string
  username: string
  is_live: boolean
  title: string
  category: string
  language: string
  last_updated: string
  [key: string]: string | boolean
}

const streamers = ref<Streamer[]>([])
const sortKey = ref('username')
const sortDir = ref('asc')
const isDeleting = ref(false)

// Define emit types
const emit = defineEmits<{
  streamerDeleted: []
}>()

const sortedStreamers = computed(() => {
  return [...streamers.value].sort((a, b) => {
    const modifier = sortDir.value === 'asc' ? 1 : -1
    const aValue = a[sortKey.value]
    const bValue = b[sortKey.value]
    if (aValue < bValue) return -1 * modifier
    if (aValue > bValue) return 1 * modifier
    return 0
  })
})

const sortBy = (key: string) => {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

const formatDate = (date: string) => {
  if (!date) return 'Never'
  return new Date(date).toLocaleString()
}

const deleteStreamer = async (streamerId: string) => {
  if (!confirm('Are you sure you want to delete this streamer?')) return
  
  isDeleting.value = true
  try {
    const response = await fetch(`/api/streamers/${streamerId}`, {
      method: 'DELETE'
    })
    if (!response.ok) throw new Error('Failed to delete streamer')
    
    // Remove from local list immediately
    streamers.value = streamers.value.filter(s => s.id !== streamerId)
    
    // Emit event for parent components
    emit('streamerDeleted')
    
    // Refresh the full list
    await fetchStreamers()
  } catch (error) {
    console.error('Failed to delete streamer:', error)
  } finally {
    isDeleting.value = false
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

onMounted(() => {
  fetchStreamers()
  const interval = setInterval(fetchStreamers, 60000)
  onUnmounted(() => clearInterval(interval))
})
</script>
