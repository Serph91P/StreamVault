<template>
  <div class="streamer-grid">
    <TransitionGroup name="streamer-card">
      <div v-for="streamer in sortedStreamers" 
           :key="streamer.id"
           class="streamer-card"
           :class="{ 'live': streamer.is_live }">
        <div class="streamer-header">
          <div class="streamer-info">
            <div class="profile-image-wrapper">
              <img 
                v-if="streamer.profile_image_url"
                :src="streamer.profile_image_url"
                class="profile-image"
                :alt="streamer.name"
                loading="lazy"
                @error="handleImageError"
              />
              <div v-else class="profile-image-placeholder">
                {{ streamer.name.charAt(0).toUpperCase() }}
              </div>
              <span class="status-dot" :class="{ 'live': streamer.is_live }"></span>
            </div>
            <h3 class="streamer-name-link" @click="navigateToTwitch(streamer.name)">
              {{ streamer.name }}
            </h3>
          </div>
          <div class="status-badges">
            <span class="status-badge" :class="{ 'live': streamer.is_live }">
              {{ streamer.is_live ? 'LIVE' : 'OFFLINE' }}
            </span>
            <span 
              v-if="streamer.is_live && streamer.is_recording" 
              class="status-badge recording"
              title="Currently recording"
            >
              REC
            </span>
            <span 
              v-else-if="streamer.is_live && !streamer.auto_record" 
              class="status-badge not-recording"
              title="Recording disabled for this streamer"
            >
              NO REC
            </span>
          </div>
        </div>
        <div class="streamer-content">
          <p v-if="streamer.current_title"><strong>Title:</strong> {{ streamer.current_title || '-' }}</p>
          <p v-if="streamer.current_category"><strong>Category:</strong> {{ streamer.current_category || '-' }}</p>
          <p><strong>Language:</strong> {{ (streamer as any).language || '-' }}</p>
          <p><strong>Last Updated:</strong> {{ formatDate(streamer.last_seen || undefined) }}</p>
        </div>
        <div class="streamer-footer">
          <button 
            @click="handleDelete(String(streamer.id))" 
            class="btn btn-danger"
            :disabled="isDeleting === String(streamer.id)"
          >
            <span v-if="isDeleting === String(streamer.id)" class="loader"></span>
            {{ isDeleting === String(streamer.id) ? '' : 'Remove' }}
          </button>
          <button 
                        @click="navigateToStreamerDetail(String(streamer.id), streamer.name)" 
            class="btn btn-primary"
          >
            View Streams
          </button>
        </div>
      </div>
    </TransitionGroup>
    
    <div v-if="!sortedStreamers.length" class="empty-state">
      <div class="empty-state-content">
        <div class="empty-state-icon">🎬</div>
        <h3>No Streamers Yet</h3>
        <p>Add your favorite Twitch streamers to get started</p>
        <!-- Removed Add Streamer button as per the change request -->
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch, ref } from 'vue'
import { useHybridStatus } from '@/composables/useHybridStatus'
import { useStreamers } from '@/composables/useStreamers'
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

// Use hybrid status for real-time streamer updates
const {
  streamersStatus,
  isLoading,
  error,
  fetchStreamersStatus,
  isOnline: connectionStatus
} = useHybridStatus()

// Keep useStreamers for delete operations
const { deleteStreamer } = useStreamers()

const router = useRouter()
const isDeleting = ref<string | null>(null)

const emit = defineEmits<{
  streamerDeleted: []
}>()

// Use streamers from hybrid status
const streamers = computed(() => streamersStatus.value || [])

const sortedStreamers = computed(() => {
  return [...streamers.value].sort((a, b) => {
    // Sort by live status first (live streamers at top)
    if (a.is_live && !b.is_live) return -1
    if (!a.is_live && b.is_live) return 1
    
    // Then sort by username alphabetically  
    return a.name.localeCompare(b.name)
  })
})

const formatDate = (date: string | undefined): string => {
  if (!date) return 'Never'
  
  const now = new Date()
  const updated = new Date(date)
  const diff = now.getTime() - updated.getTime()
  
  // Less than a minute ago
  if (diff < 60 * 1000) {
    return 'Just now'
  }
  
  // Less than an hour ago
  if (diff < 60 * 60 * 1000) {
    const minutes = Math.floor(diff / (60 * 1000))
    return `${minutes} minute${minutes > 1 ? 's' : ''} ago`
  }
  
  // Less than a day ago
  if (diff < 24 * 60 * 60 * 1000) {
    const hours = Math.floor(diff / (60 * 60 * 1000))
    return `${hours} hour${hours > 1 ? 's' : ''} ago`
  }
  
  // Show full date for older updates
  return updated.toLocaleString()
}

const navigateToTwitch = (username: string) => {
  window.open(`https://twitch.tv/${username}`, '_blank')
}

const handleImageError = (event: Event) => {
  const target = event.target as HTMLImageElement
  if (target) {
    // Hide the broken image and let the placeholder show instead
    target.style.display = 'none'
    
    // Only log in development mode
    if (import.meta.env.DEV) {
      console.warn('Failed to load profile image:', target.src)
    }
  }
}

const handleDelete = async (streamerId: string) => {
  if (!confirm('Are you sure you want to delete this streamer?')) return
  
  isDeleting.value = streamerId
  try {
    if (await deleteStreamer(streamerId)) {
      emit('streamerDeleted')
      // Refresh streamers data after deletion
      await fetchStreamersStatus(false)
    }
  } finally {
    isDeleting.value = null
  }
}

const navigateToStreamerDetail = (streamerId: string, username: string) => {
  router.push({
    name: 'streamer-detail',
    params: { id: streamerId },
    query: { name: username }
  })
}

// Connection status handling
watch(() => connectionStatus.value, (status) => {
  if (status) {
    // Refresh when connection is established
    fetchStreamersStatus(false)
  }
}, { immediate: true })

onMounted(() => {
  // Initial fetch
  fetchStreamersStatus()
})
</script>

<style scoped>
.streamer-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;
  padding: 8px;
  width: 100%;
}

.streamer-card {
  background-color: var(--background-card, #1f1f23);
  border-radius: var(--border-radius, 8px);
  overflow: hidden;
  transition: all 0.3s var(--vue-ease, cubic-bezier(0.25, 0.8, 0.5, 1));
  position: relative;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color, #2d2d35);
  margin-bottom: 0;
  box-shadow: none;
}

.streamer-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  border-color: rgba(66, 184, 131, 0.5);
}

.streamer-card.live {
  border-color: rgba(239, 68, 68, 0.5);
  box-shadow: none;
}

.streamer-card.live:hover {
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.15);
}

/* Left border indicator with more subtle styling */
.streamer-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background-color: transparent;
  transition: background-color 0.3s var(--vue-ease, cubic-bezier(0.25, 0.8, 0.5, 1));
}

.streamer-card:hover::before {
  background-color: var(--primary-color, #42b883);
}

.streamer-card.live::before {
  background-color: var(--danger-color, #ef4444);
  animation: subtle-pulse 2s infinite;
}

@keyframes subtle-pulse {
  0% {
    opacity: 0.7;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.7;
  }
}

.streamer-header {
  background-color: var(--background-darker, #18181b);
  padding: 8px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color, #2d2d35);
}

.status-badges {
  display: flex;
  gap: 6px;
  align-items: center;
}

.streamer-info {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
}

.profile-image-wrapper {
  position: relative;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
}

.profile-image {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--border-color, #2d2d35);
}

.status-dot {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: var(--text-muted-color, #6d6d6d);
  border: 2px solid var(--background-darker, #18181b);
}

.status-dot.live {
  background-color: var(--danger-color, #ef4444);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(239, 68, 68, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
  }
}

.streamer-name-link {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  color: var(--text-primary, #efeff1);
  transition: color 0.2s ease;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.streamer-name-link:hover {
  color: var(--primary-color, #42b883);
  text-decoration: underline;
}

.streamer-content {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.streamer-content p {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.4;
  color: var(--text-secondary, #adadb8);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.streamer-content p strong {
  color: var(--text-primary, #efeff1);
  margin-right: 4px;
}

.streamer-footer {
  padding: 8px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px solid var(--border-color, #2d2d35);
  background-color: var(--background-darker, #18181b);
}

.status-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 12px;
  background-color: var(--background-dark, #121214);
  color: var(--text-secondary, #adadb8);
  letter-spacing: 0.5px;
}

.status-badge.live {
  background-color: var(--danger-color, #ef4444);
  color: white;
}

.status-badge.recording {
  background-color: var(--success-color, #22c55e);
  color: white;
  animation: pulse 2s infinite;
}

.status-badge.not-recording {
  background-color: var(--warning-color, #f59e0b);
  color: white;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

/* Button styling */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 16px;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  font-size: 0.875rem;
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  height: 32px;
  min-width: 80px;
  box-shadow: none;
}

.btn-primary {
  background-color: var(--primary-color, #42b883);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: var(--primary-color-hover, #3ca978);
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(66, 184, 131, 0.25);
}

.btn-danger {
  background-color: var(--danger-color, #ef4444);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background-color: var(--danger-color-hover, #dc2626);
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(239, 68, 68, 0.25);
}

.btn-primary:active:not(:disabled),
.btn-danger:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: none;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loader {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: white;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Empty state styling */
.empty-state {
  grid-column: 1 / -1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 32px 16px;
  background-color: var(--background-card, #1f1f23);
  border-radius: var(--border-radius, 8px);
  border: 1px dashed var(--border-color, #2d2d35);
  margin: 16px 0;
}

.empty-state-content {
  text-align: center;
  max-width: 400px;
}

.empty-state-icon {
  font-size: 3rem;
  margin-bottom: 16px;
}

.empty-state h3 {
  margin: 0 0 8px;
  color: var(--text-primary, #efeff1);
}

.empty-state p {
  margin: 0 0 16px;
  color: var(--text-secondary, #adadb8);
}

/* Card transition animations */
.streamer-card-enter-active,
.streamer-card-leave-active {
  transition: all 0.3s var(--vue-ease, cubic-bezier(0.25, 0.8, 0.5, 1));
}

.streamer-card-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.streamer-card-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

.streamer-card-move {
  transition: transform 0.5s var(--vue-ease, cubic-bezier(0.25, 0.8, 0.5, 1));
}

/* Responsive adjustments */
@media (max-width: 640px) {
  .streamer-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  
  .streamer-footer {
    padding: 4px;
  }
  
  .btn {
    padding: 4px 8px;
    font-size: 0.8rem;
  }
}
</style>
