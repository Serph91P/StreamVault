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
        @click="handleDelete(streamer.id)" 
        class="delete-btn"
        :disabled="isDeleting"
      >
        {{ isDeleting ? 'Deleting...' : 'Delete' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch, ref } from 'vue'
import { useStreamers } from '@/composables/useStreamers'
import { useWebSocket } from '@/composables/useWebSocket'

// Define proper interfaces
interface WebSocketMessage {
  type: string
  data: {
    streamer_id: string
    title?: string
    category_name?: string
    language?: string
    [key: string]: any
  }
}

// Define socket as a ref with browser's WebSocket type
const socket = ref<WebSocket | null>(null)

// WebSocket connection function
const connectWebSocket = () => {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${wsProtocol}//${window.location.host}/ws`
  
  socket.value = new WebSocket(wsUrl)
  
  socket.value.onopen = () => {
    console.log('WebSocket connected')
  }

  socket.value.onmessage = (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data)
      console.log('Received message:', data)
      // Handle the message here
    } catch (error) {
      console.error('Error parsing WebSocket message:', error)
    }
  }

  socket.value.onclose = () => {
    console.log('WebSocket disconnected')
  }
}

const { streamers, updateStreamer, fetchStreamers, deleteStreamer } = useStreamers()
const { messages, connectionStatus } = useWebSocket()
const isDeleting = ref(false)

const emit = defineEmits<{
  streamerDeleted: []
}>()

const sortedStreamers = computed(() => {
  return [...streamers.value].sort((a, b) => {
    return a.username.localeCompare(b.username)
  })
})

const formatDate = (date: string | undefined): string => {
  if (!date) return 'Never'
  return new Date(date).toLocaleString()
}

const handleDelete = async (streamerId: string) => {
  if (!confirm('Are you sure you want to delete this streamer?')) return
  
  isDeleting.value = true
  try {
    if (await deleteStreamer(streamerId)) {
      emit('streamerDeleted')
    }
  } finally {
    isDeleting.value = false
  }
}

// Improved message handling
watch(messages, (newMessages: any[]) => {
  const message = newMessages[newMessages.length - 1]
  if (!message) return

  console.log('Processing WebSocket message:', message) // Debug log

  switch (message.type) {
    case 'channel.update':
      const streamerId = message.data.streamer_id
      console.log('Updating streamer:', streamerId, message.data) // Debug log
      updateStreamer(streamerId, {
        title: message.data.title,
        category_name: message.data.category_name,
        last_updated: new Date().toISOString()
      })
      break
    case 'stream.online':
      updateStreamer(message.data.streamer_id, { 
        is_live: true,
        title: message.data.title || '',
        category_name: message.data.category_name || '',
        language: message.data.language || '',
        last_updated: new Date().toISOString()
      })
      break
    case 'stream.offline':
      updateStreamer(message.data.streamer_id, { 
        is_live: false,
        last_updated: new Date().toISOString()
      })
      break
  }
}, { deep: true })

// Improved connection handling
watch(connectionStatus, (status) => {
  if (status === 'connected') {
    void fetchStreamers()
  }
}, { immediate: true })

// Better lifecycle management with proper event type
onMounted(() => {
  console.log('StreamerList mounted')
  connectWebSocket()
  socket.value?.addEventListener('message', (event: MessageEvent) => {
    const data = JSON.parse(event.data)
    console.log('Raw WebSocket message received:', data)
  })
})

onUnmounted(() => {
  if (socket.value) {
    socket.value.close()
  }
})
</script>
