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
import { ref, onMounted } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

const streamers = ref([])
const { messages } = useWebSocket()

onMounted(async () => {
  await fetchStreamers()
  setInterval(fetchStreamers, 60000)
})

async function fetchStreamers() {
  const response = await fetch('/api/streamers')
  streamers.value = await response.json()
}

function formatDate(date) {
  return date ? new Date(date).toLocaleString() : 'Never'
}
</script>
