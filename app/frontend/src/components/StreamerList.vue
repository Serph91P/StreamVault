<template>
  <div class="streamer-grid">
    <div v-for="streamer in sortedStreamers" 
         :key="streamer.id"
         class="streamer-card">
      <div class="streamer-header">
        <div class="streamer-info">
          <span class="status-dot" :class="{ 'live': streamer.is_live }"></span>
          <h3>{{ streamer.username }}</h3>
        </div>
        <span class="status-badge" :class="{ 'live': streamer.is_live }">
          {{ streamer.is_live ? 'LIVE' : 'OFFLINE' }}
        </span>
      </div>
      <div class="streamer-content">
        <p><strong>Title:</strong> {{ streamer.title || '-' }}</p>
        <p><strong>Category:</strong> {{ streamer.category_name || '-' }}</p>
        <p><strong>Language:</strong> {{ streamer.language || '-' }}</p>
        <p><strong>Last Updated:</strong> {{ formatDate(streamer.last_updated) }}</p>
      </div>
      <button 
        @click="deleteStreamer(streamer.id)" 
        class="delete-btn"
        :disabled="isDeleting"
      >
        {{ isDeleting ? 'Deleting...' : 'Delete' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import type { Ref } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

interface Streamer {
  id: string
  twitch_id: string
  username: string
  is_live: boolean
  title?: string
  category_name?: string
  language?: string
  last_updated?: string
  [key: string]: string | boolean | undefined
}

interface WebSocketData {
  streamer_id: string
  title?: string
  category_name?: string
  language?: string
  last_updated?: string
}

const { messages } = useWebSocket()
const streamers = ref<Streamer[]>([])
const isDeleting = ref(false)
const sortKey = ref('username')
const sortDir = ref('asc')

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

const formatDate = (date: string | undefined): string => {
  if (!date) return 'Never'
  return new Date(date).toLocaleString()
}

function updateStreamerInfo(data: WebSocketData) {
  streamers.value = streamers.value.map(streamer => {
    if (streamer.twitch_id === data.streamer_id) {
      return {
        ...streamer,
        title: data.title,
        category_name: data.category_name,
        language: data.language,
        last_updated: data.last_updated
      }
    }
    return streamer
  })
}

const deleteStreamer = async (streamerId: string) => {
  if (!confirm('Are you sure you want to delete this streamer?')) return

  isDeleting.value = true
  try {
    const response = await fetch(`/api/streamers/${streamerId}`, {
      method: 'DELETE'
    })
    if (!response.ok) throw new Error('Failed to delete streamer')
  
    streamers.value = streamers.value.filter(s => s.id !== streamerId)
    emit('streamerDeleted')
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

// Watch for WebSocket messages
watch(messages, (newMessages) => {
  if (newMessages.length > 0) {
    const message = newMessages[newMessages.length - 1]
    
    // Handle different event types
    switch (message.type) {
      case 'channel.update':
        updateStreamerInfo(message.data)
        break
      case 'stream.online':
      case 'stream.offline':
        fetchStreamers() // Refresh full list for status changes
        break
    }
  }
}, { deep: true })

onMounted(() => {
  fetchStreamers()
  const interval = setInterval(fetchStreamers, 60000)
  onUnmounted(() => clearInterval(interval))
})
</script>
