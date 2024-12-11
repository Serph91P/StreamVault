<template>
  <div class="streamer-grid">
    <div v-for="streamer in streamers" :key="streamer.id" 
         :class="['streamer-card', streamer.is_live ? 'live' : 'offline']">
      <h3>{{ streamer.username }}</h3>
      <div class="status">
        <span :class="['status-dot', streamer.is_live ? 'live' : 'offline']"></span>
        {{ streamer.is_live ? 'Live' : 'Offline' }}
      </div>
      <p class="last-seen">Last update: {{ formatDate(streamer.last_event) }}</p>
    </div>
  </div>
</template>
  <script setup>
  import { ref, onMounted, watch } from 'vue'
  import { useWebSocket } from '@/composables/useWebSocket'

  const streamers = ref([])
  const { messages } = useWebSocket()

  const fetchStreamers = async () => {
    try {
      const response = await fetch('/api/streamers')
      const data = await response.json()
      streamers.value = data
    } catch (error) {
      console.error('Failed to fetch streamers:', error)
    }
  }

  // Fetch immediately after adding a streamer
  watch(() => props.refreshTrigger, () => {
    fetchStreamers()
  })

  // Regular polling
  onMounted(() => {
    fetchStreamers()
    setInterval(fetchStreamers, 60000)
  })

  function formatDate(date) {
    return date ? new Date(date).toLocaleString() : 'Never'
  }
  </script>
