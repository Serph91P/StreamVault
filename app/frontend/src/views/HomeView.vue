<template>
  <div class="home-view">
    <!-- Live Now Section -->
    <section class="live-section">
      <div class="section-header">
        <h2 class="section-title">
          <span class="live-indicator-wrapper">
            <span class="live-indicator"></span>
            <span v-if="!isLoadingStreamers && liveStreamers.length > 0" class="live-count">
              {{ liveStreamers.length }}
            </span>
          </span>
          Live Now
        </h2>
      </div>

      <!-- Loading State -->
      <div v-if="isLoadingStreamers" class="horizontal-scroll">
        <LoadingSkeleton
          v-for="i in 4"
          :key="`skeleton-${i}`"
          type="streamer"
          class="live-card-skeleton"
        />
      </div>

      <!-- Empty State -->
      <EmptyState
        v-else-if="liveStreamers.length === 0 && totalStreamers === 0"
        variant="compact"
        title="Welcome to StreamVault"
        description="Add your first streamer to start recording streams automatically."
        icon="users"
        action-label="Add Streamer"
        action-icon="plus"
        :show-decoration="false"
        @action="navigateToAddStreamer"
      />
      
      <EmptyState
        v-else-if="liveStreamers.length === 0"
        variant="compact"
        title="No Live Streams"
        description="None of your streamers are currently live. Check out your recent recordings below."
        icon="video-off"
        :show-decoration="false"
      />

      <!-- Live Streamers -->
      <div v-else class="horizontal-scroll">
        <StreamerCard
          v-for="streamer in liveStreamers"
          :key="streamer.id"
          :streamer="streamer"
          class="live-card"
        />
      </div>
    </section>

    <!-- Recent Recordings Section -->
    <section class="recordings-section">
      <div class="section-header">
        <h2 class="section-title">
          <svg class="section-icon">
            <use href="#icon-video" />
          </svg>
          Recent Recordings
        </h2>
        <router-link to="/videos" class="view-all-link">
          View All
          <svg class="arrow-icon">
            <use href="#icon-arrow-right" />
          </svg>
        </router-link>
      </div>

      <!-- Loading State -->
      <div v-if="isLoadingVideos" class="recordings-grid">
        <LoadingSkeleton
          v-for="i in 6"
          :key="`skeleton-video-${i}`"
          type="video"
        />
      </div>

      <!-- Empty State -->
      <EmptyState
        v-else-if="recentRecordings.length === 0"
        title="No Recordings Yet"
        description="Start recording your favorite streamers to see them here."
        icon="video"
        action-label="Add Streamer"
        action-icon="plus"
        @action="navigateToAddStreamer"
      />

      <!-- Recent Videos -->
      <div v-else class="recordings-grid">
        <VideoCard
          v-for="video in recentRecordings"
          :key="video.id"
          :video="video"
          @click="playVideo(video)"
        />
      </div>
    </section>

    <!-- Quick Stats Section -->
    <section class="stats-section">
      <div class="section-header">
        <h2 class="section-title">Quick Stats</h2>
      </div>

      <div v-if="isLoadingStreamers" class="stats-grid">
        <LoadingSkeleton
          v-for="i in 4"
          :key="`skeleton-stat-${i}`"
          type="status"
        />
      </div>

      <div v-else class="stats-grid">
        <StatusCard
          :value="totalStreamers"
          label="Total Streamers"
          icon="users"
          type="primary"
        />
        <StatusCard
          :value="liveStreamers.length"
          label="Live Now"
          icon="video"
          type="danger"
        />
        <StatusCard
          :value="activeRecordings.length"
          label="Recording"
          icon="circle"
          type="warning"
        />
        <StatusCard
          :value="recentRecordings.length"
          label="Recent Videos"
          icon="film"
          type="info"
        />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { streamersApi, videoApi, recordingApi } from '@/services/api'
import { useWebSocket } from '@/composables/useWebSocket'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StreamerCard from '@/components/cards/StreamerCard.vue'
import VideoCard from '@/components/cards/VideoCard.vue'
import StatusCard from '@/components/cards/StatusCard.vue'

const router = useRouter()

// WebSocket for real-time updates
const { messages } = useWebSocket()

// Loading states
const isLoadingStreamers = ref(true)
const isLoadingVideos = ref(true)
const isLoadingRecordings = ref(true)

// Data
const streamers = ref<any[]>([])
const videos = ref<any[]>([])
const activeRecordings = ref<any[]>([])

// Computed properties
const liveStreamers = computed(() => {
  return streamers.value.filter(s => s.is_live)
})

const recentRecordings = computed(() => {
  // Sort by date (newest first) and limit to 6
  return videos.value
    .sort((a, b) => {
      const dateA = new Date(a.stream_date || a.created_at).getTime()
      const dateB = new Date(b.stream_date || b.created_at).getTime()
      return dateB - dateA
    })
    .slice(0, 6)
})

const totalStreamers = computed(() => streamers.value.length)

// Fetch data functions
async function fetchStreamers() {
  isLoadingStreamers.value = true
  try {
    const response = await streamersApi.getAll()
    // Backend returns {streamers: [...]} not raw array
    streamers.value = response?.streamers || []
  } catch (error) {
    console.error('Failed to fetch streamers:', error)
    streamers.value = []
  } finally {
    isLoadingStreamers.value = false
  }
}

async function fetchVideos() {
  isLoadingVideos.value = true
  try {
    const response = await videoApi.getAll({ limit: 12 })
    videos.value = response || []
  } catch (error) {
    console.error('Failed to fetch videos:', error)
    videos.value = []
  } finally {
    isLoadingVideos.value = false
  }
}

async function fetchActiveRecordings() {
  isLoadingRecordings.value = true
  try {
    const response = await recordingApi.getActiveRecordings()
    activeRecordings.value = response || []
  } catch (error) {
    console.error('Failed to fetch active recordings:', error)
    activeRecordings.value = []
  } finally {
    isLoadingRecordings.value = false
  }
}

// Actions
function navigateToAddStreamer() {
  router.push('/add-streamer')
}

function playVideo(video: any) {
  router.push(`/videos/${video.id}`)
}

// WebSocket: Real-time updates for streamer status
watch(messages, (newMessages) => {
  if (!newMessages || newMessages.length === 0) return
  
  // Process latest message
  const latestMessage = newMessages[newMessages.length - 1]
  
  // Handle stream status changes
  if (latestMessage.type === 'stream.online' || 
      latestMessage.type === 'stream.offline' ||
      latestMessage.type === 'channel.update' ||
      latestMessage.type === 'stream.update') {
    
    const username = latestMessage.data?.username || latestMessage.data?.streamer_name
    if (!username) return
    
    // Find streamer in list
    const streamerIndex = streamers.value.findIndex(
      s => s.username?.toLowerCase() === username.toLowerCase() ||
           s.name?.toLowerCase() === username.toLowerCase()
    )
    
    if (streamerIndex === -1) return
    
    // Update streamer data based on message type
    const streamer = { ...streamers.value[streamerIndex] }
    
    if (latestMessage.type === 'stream.online') {
      streamer.is_live = true
      streamer.title = latestMessage.data?.title
      streamer.category_name = latestMessage.data?.category_name
      console.log(`[HomeView WebSocket] ${username} went LIVE`)
    } else if (latestMessage.type === 'stream.offline') {
      streamer.is_live = false
      streamer.title = null
      streamer.category_name = null
      console.log(`[HomeView WebSocket] ${username} went OFFLINE`)
    } else if (latestMessage.type === 'channel.update' || latestMessage.type === 'stream.update') {
      // Update title and category in real-time
      if (latestMessage.data?.title) {
        streamer.title = latestMessage.data.title
      }
      if (latestMessage.data?.category_name) {
        streamer.category_name = latestMessage.data.category_name
      }
      console.log(`[HomeView WebSocket] ${username} updated`)
    }
    
    // Update the streamer in array (trigger reactivity)
    streamers.value = [
      ...streamers.value.slice(0, streamerIndex),
      streamer,
      ...streamers.value.slice(streamerIndex + 1)
    ]
  }
}, { deep: true })

// Initialize
onMounted(async () => {
  await Promise.all([
    fetchStreamers(),
    fetchVideos(),
    fetchActiveRecordings()
  ])
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.home-view {
  padding: var(--spacing-6) var(--spacing-4);
  max-width: 1400px;
  margin: 0 auto;
  min-height: 100vh;
}

// Section Styling
section {
  margin-bottom: var(--spacing-10);

  &:last-child {
    margin-bottom: 0;
  }
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-5);
  padding: 0 var(--spacing-2);
}

.section-title {
  font-size: var(--text-2xl);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  margin: 0;
}

.section-icon {
  width: 28px;
  height: 28px;
  stroke: var(--primary-color);
  fill: none;
}

// Live Indicator Wrapper (contains indicator + count)
.live-indicator-wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.live-indicator {
  display: inline-block;
  width: 20px;  // Larger to accommodate count
  height: 20px;
  background: var(--danger-color);
  border-radius: 50%;
  animation: pulse-live 2s ease-in-out infinite;
  position: relative;
}

.live-count {
  position: absolute;
  font-size: 10px;
  font-weight: v.$font-bold;
  color: white;
  line-height: 1;
  pointer-events: none;
  text-shadow: 0 0 2px rgba(0, 0, 0, 0.5);
}

@keyframes pulse-live {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.1);
  }
}

// View All Link
.view-all-link {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  color: var(--primary-color);
  text-decoration: none;
  transition: all v.$duration-200 v.$ease-out;

  &:hover {
    gap: var(--spacing-3);
    color: var(--primary-600);
  }

  .arrow-icon {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
    transition: transform v.$duration-200 v.$ease-out;
  }

  &:hover .arrow-icon {
    transform: translateX(4px);
  }
}

// Horizontal Scroll (Live Streamers)
.horizontal-scroll {
  // DESKTOP: Grid layout with wrapping (no scroll)
  @include m.respond-to('md') {  // >= 768px
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: var(--spacing-4);
    overflow: visible;  // No scroll on desktop
    padding: var(--spacing-2);
    margin: 0;
  }
  
  // MOBILE: Horizontal scroll
  @include m.respond-below('md') {  // < 768px
    display: flex;
    gap: var(--spacing-4);
    overflow-x: auto;
    overflow-y: visible;  /* CRITICAL: Allow dropdown to overflow vertically */
    padding: var(--spacing-2) var(--spacing-2) var(--spacing-6);  /* FIXED: Increased bottom padding for shadow */
    margin: 0 calc(var(--spacing-4) * -1);
    padding-left: var(--spacing-4);
    padding-right: var(--spacing-4);
    
    // Smooth scroll behavior
    scroll-behavior: smooth;
    -webkit-overflow-scrolling: touch;
    
    // FIX: Prevent weird touch behavior - only horizontal scroll
    touch-action: pan-x pan-y;  /* Allow both horizontal and vertical panning */
    overscroll-behavior-x: contain;  /* Prevent scroll chaining */
    
    // Custom scrollbar styling (visible on mobile)
    scrollbar-width: thin;
    scrollbar-color: var(--primary-color) var(--background-darker);

    &::-webkit-scrollbar {
      height: 8px;
    }

    &::-webkit-scrollbar-track {
      background: var(--background-darker);
      border-radius: var(--radius-full);
    }

    &::-webkit-scrollbar-thumb {
      background: var(--primary-color);
      border-radius: var(--radius-full);
      
      &:hover {
        background: var(--primary-600);
      }
    }
  }
}

.live-card,
.live-card-skeleton {
  // Animation FIRST (before nested rules to avoid SASS deprecation warning)
  animation: fade-in v.$duration-300 v.$ease-out;
  
  // DESKTOP: Full width in grid
  @include m.respond-to('md') {  // >= 768px
    width: 100%;  // Take full grid cell
    max-width: none;
  }
  
  // MOBILE: Fixed width for horizontal scroll
  @include m.respond-below('md') {  // < 768px
    flex: 0 0 320px;
    max-width: 320px;
  }

  @for $i from 1 through 10 {
    &:nth-child(#{$i}) {
      animation-delay: #{$i * 50}ms;
    }
  }
}

// Recordings Grid
.recordings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--spacing-5);
  padding: var(--spacing-2);

  > * {
    animation: fade-in v.$duration-300 v.$ease-out;

    @for $i from 1 through 12 {
      &:nth-child(#{$i}) {
        animation-delay: #{$i * 50}ms;
      }
    }
  }
}

// Stats Grid
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: var(--spacing-4);
  padding: var(--spacing-2);

  > * {
    animation: fade-in v.$duration-300 v.$ease-out;

    @for $i from 1 through 4 {
      &:nth-child(#{$i}) {
        animation-delay: #{$i * 75}ms;
      }
    }
  }
}

// Responsive Design - Use SCSS mixins for breakpoints
@include m.respond-below('lg') {  // < 1024px
  .home-view {
    padding: var(--spacing-4) var(--spacing-3);
  }

  .section-title {
    font-size: var(--text-xl);
  }

  .recordings-grid {
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: var(--spacing-4);
  }
}

@include m.respond-below('sm') {  // < 640px
  .home-view {
    padding: var(--spacing-3) var(--spacing-2);
  }

  .section-header {
    flex-wrap: wrap;
    gap: var(--spacing-2);
  }

  .section-title {
    font-size: var(--text-lg);
  }

  // Center live cards on mobile and reduce size
  .horizontal-scroll {
    justify-content: flex-start;  // Start from left for natural scroll
    padding-left: var(--spacing-4);  // Keep padding
    padding-right: var(--spacing-4);
  }

  .live-card,
  .live-card-skeleton {
    flex: 0 0 280px;  // Slightly smaller on mobile
    max-width: 280px;
  }

  .recordings-grid {
    grid-template-columns: 1fr;
    gap: var(--spacing-3);
  }

  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--spacing-3);
  }
}

// Animation keyframe (if not already in _animations.scss)
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
