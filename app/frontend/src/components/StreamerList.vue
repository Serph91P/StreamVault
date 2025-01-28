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
    streamer_name: string
    title?: string
    category_name?: string
    language?: string
    is_live?: boolean
  }

  const { messages, connectionStatus } = useWebSocket()
  const streamers = ref<Streamer[]>([])
  const isDeleting = ref(false)
  const sortKey = ref('username')
  const sortDir = ref('asc')

  const emit = defineEmits<{
    streamerDeleted: []
  }>()

  // Enhanced logging for WebSocket messages
  watch(messages, (newMessages) => {
    if (newMessages.length > 0) {
      const message = newMessages[newMessages.length - 1]
      console.log('WebSocket message received:', message)
    
      if (message.type === 'channel.update' || message.type === 'stream.online' || message.type === 'stream.offline') {
        const data = message.data as WebSocketData
        console.log('Updating streamer with data:', data)
      
        streamers.value = streamers.value.map(streamer => {
          if (streamer.twitch_id === data.streamer_id) {
            console.log('Found matching streamer:', streamer)
            return {
              ...streamer,
              title: data.title || streamer.title,
              category_name: data.category_name || streamer.category_name,
              language: data.language || streamer.language,
              is_live: message.type === 'stream.online' ? true : 
                      message.type === 'stream.offline' ? false : 
                      streamer.is_live,
              last_updated: new Date().toISOString()
            }
          }
          return streamer
        })
      }
    }
  }, { deep: true })

  // Monitor connection status
  watch(connectionStatus, (newStatus) => {
    console.log('WebSocket connection status:', newStatus)
    if (newStatus === 'connected') {
      fetchStreamers()
    }
  })

  const fetchStreamers = async () => {
    try {
      const response = await fetch('/api/streamers')
      if (!response.ok) throw new Error('Failed to fetch streamers')
      const data = await response.json()
      console.log('Fetched streamers data:', data)
      streamers.value = data
    } catch (error) {
      console.error('Failed to fetch streamers:', error)
    }
  }

  const sortedStreamers = computed(() => {
    return [...streamers.value].sort((a, b) => {
      const modifier = sortDir.value === 'asc' ? 1 : -1
      const aValue = a[sortKey.value] ?? ''
      const bValue = b[sortKey.value] ?? ''
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

  onMounted(() => {
    fetchStreamers()
    const interval = setInterval(fetchStreamers, 60000)
    onUnmounted(() => clearInterval(interval))
  })
  </script>
