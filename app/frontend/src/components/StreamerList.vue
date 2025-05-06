<template>
  <div class="streamer-grid">
    <div v-for="streamer in sortedStreamers" 
         :key="streamer.id"
         class="streamer-card">
      <div class="streamer-header">
        <div class="streamer-info">
          <img 
            v-if="streamer.profile_image_url" 
            :src="streamer.profile_image_url" 
            class="profile-image" 
            :alt="streamer.username"
          />
          <span class="status-dot" :class="{ 'live': streamer.is_live }"></span>
          <!-- Mache den Benutzernamen auf Twitch klickbar -->
          <h3 class="streamer-name-link" @click="navigateToTwitch(streamer.username)">{{ streamer.username }}</h3>
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
      <div class="streamer-footer">
        <button 
          @click="handleDelete(streamer.id)" 
          class="btn btn-danger"
          :disabled="isDeleting"
        >
          {{ isDeleting ? 'Deleting...' : 'Delete' }}
        </button>
        <button 
          @click="navigateToStreamerDetail(streamer.id, streamer.username)" 
          class="btn btn-success"
        >
          View Streams
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch, ref } from 'vue'
import { useStreamers } from '@/composables/useStreamers'
import { useWebSocket } from '@/composables/useWebSocket'
import { useRouter } from 'vue-router'
import type { Ref } from 'vue'

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

interface StreamerUpdateData {
  is_live?: boolean
  title?: string
  category_name?: string
  language?: string
  last_updated: string
}

const { streamers, updateStreamer, fetchStreamers, deleteStreamer } = useStreamers()
const { messages, connectionStatus } = useWebSocket()
const router = useRouter()
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

const navigateToTwitch = (username: string) => {
  window.open(`https://twitch.tv/${username}`, '_blank');
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

const navigateToStreamerDetail = (streamerId: string, username: string) => {
  router.push({
    name: 'streamer-detail',
    params: { id: streamerId },
    query: { name: username }
  })
}

watch(messages, (newMessages) => {
  const message = newMessages[newMessages.length - 1]
  if (!message) return

  console.log('StreamerList: New message detected:', message)

  switch (message.type) {
    case 'channel.update': {
      console.log('StreamerList: Processing channel update:', message.data)
      const streamerId = message.data.streamer_id
      const streamer = streamers.value.find(s => s.id === streamerId)
      
      const updateData: StreamerUpdateData = {
        title: message.data.title || '',
        category_name: message.data.category_name || '',
        language: message.data.language || '',
        last_updated: new Date().toISOString()
        // Behalte den aktuellen Live-Status bei
        // is_live: streamer ? streamer.is_live : false
      }
      console.log('StreamerList: Updating streamer with data:', updateData)
      updateStreamer(streamerId, updateData)
      break
    }
    case 'stream.online': {
      console.log('StreamerList: Processing stream online:', message.data)
      const updateData: StreamerUpdateData = {
        is_live: true,
        title: message.data.title || '',
        category_name: message.data.category_name || '',
        language: message.data.language || '',
        last_updated: new Date().toISOString()
      }
      updateStreamer(message.data.streamer_id, updateData)
      break
    }
    case 'stream.offline': {
      console.log('StreamerList: Processing stream offline:', message.data)
      const updateData: StreamerUpdateData = {
        is_live: false,
        last_updated: new Date().toISOString()
      }
      updateStreamer(message.data.streamer_id, updateData)
      break
    }
  }
}, { deep: true })

// Verbesserte Verbindungsbehandlung
watch(connectionStatus, (status) => {
  if (status === 'connected') {
    void fetchStreamers()
  }
}, { immediate: true })

onMounted(() => {
  console.log('StreamerList mounted')
  void fetchStreamers()
})

onUnmounted(() => {
  // Die Bereinigung wird von useWebSocket's onUnmounted übernommen
})
</script>

<style scoped>
.streamer-name-link {
  cursor: pointer;
  color: var(--text-primary);
  transition: color 0.2s;
}

.streamer-name-link:hover {
  color: var(--primary-color);
  text-decoration: underline;
}

.streamer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}
</style>
