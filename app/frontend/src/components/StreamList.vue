<template>
  <div class="streams-container">
    <div v-if="isLoading" class="loading-container">
      <span>Loading streams...</span>
    </div>
    <div v-else-if="streams.length === 0" class="no-data-container">
      <p>No streams found for this streamer.</p>
      <button 
        @click="handleBack" 
        class="btn btn-primary back-btn"
      >
        Back to streamers
      </button>
    </div>
    <div v-else>
      <div class="back-btn-container">
        <button 
          @click="handleBack" 
          class="btn btn-primary back-btn"
        >
          Back to streamers
        </button>
      </div>
      
      <div class="streams-summary">
        <p>Found {{ streams.length }} streams</p>
      </div>
      
      <div class="stream-list">
        <div v-for="stream in streams" 
             :key="stream.id"
             class="stream-card">
          <div class="stream-header">
            <div class="stream-info">
              <span class="status-badge" :class="{ 'live': !stream.ended_at }">
                {{ !stream.ended_at ? 'LIVE' : 'ENDED' }}
              </span>
              <h3>{{ formatDate(stream.started_at) }}</h3>
            </div>
          </div>
          <div class="stream-content">
            <p><strong>Title:</strong> {{ stream.title || '-' }}</p>
            <p><strong>Category:</strong> {{ stream.category_name || '-' }}</p>
            <p><strong>Duration:</strong> {{ calculateDuration(stream.started_at, stream.ended_at) }}</p>
            <p v-if="stream.ended_at"><strong>Ended:</strong> {{ formatDate(stream.ended_at) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStreams } from '@/composables/useStreams'

const route = useRoute()
const router = useRouter()
const streamerId = computed(() => route.params.id as string || route.query.id as string)
const streamerName = computed(() => route.query.name as string)

const { streams, isLoading, fetchStreams } = useStreams()

const formatDate = (date: string | undefined | null): string => {
  if (!date) return 'Unknown'
  return new Date(date).toLocaleString()
}

const calculateDuration = (start: string | undefined | null, end: string | undefined | null): string => {
  if (!start) return 'Unknown'
  
  const startTime = new Date(start).getTime()
  const endTime = end ? new Date(end).getTime() : Date.now()
  
  const durationMs = endTime - startTime
  
  if (durationMs < 0) return 'Invalid time'
  
  const seconds = Math.floor(durationMs / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  
  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`
  } else {
    return `${minutes}m ${seconds % 60}s`
  }
}

const handleBack = () => {
  router.push('/')
}

const loadStreams = async () => {
  if (streamerId.value) {
    await fetchStreams(streamerId.value)
  }
}

onMounted(loadStreams)

// Re-fetch when the streamer ID changes
watch(streamerId, (newId, oldId) => {
  if (newId && newId !== oldId) {
    loadStreams()
  }
})
</script>
