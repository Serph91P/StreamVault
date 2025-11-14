<template>
  <div class="video-player-view fade-in">
    <!-- Loading State -->
    <div v-if="isLoading" class="content-state">
      <LoadingSkeleton type="video" />
      <p class="state-text">Loading video player...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="content-state">
      <EmptyState
        icon="alert-circle"
        title="Failed to Load Video"
        :description="error"
        action-label="Retry"
        action-icon="refresh-cw"
        @action="retryLoad"
      />
    </div>

    <!-- No Video State -->
    <div v-else-if="!chapterData?.video_url" class="content-state">
      <EmptyState
        icon="video-off"
        title="No Video Available"
        description="This stream doesn't have a video file or it's still being processed."
        action-label="Refresh"
        action-icon="refresh-cw"
        @action="retryLoad"
      />
    </div>

    <!-- Video Player - Main Content -->
    <div v-else class="player-content">
      <!-- Back Button - Floating overlay for mobile -->
      <button @click="goBack" class="btn-back-floating" v-ripple>
        <svg class="icon">
          <use href="#icon-arrow-left" />
        </svg>
        <span class="back-text">Back</span>
      </button>

      <!-- Video Player Container -->
      <div class="player-container">
        <VideoPlayer
          :video-src="chapterData.video_url"
          :chapters="chapterData.chapters"
          :stream-title="chapterData.stream_title"
          :stream-id="parseInt(streamId)"
          @chapter-change="onChapterChange"
          @video-ready="onVideoReady"
          @time-update="onTimeUpdate"
        />
      </div>

      <!-- Video Metadata - Glassmorphism Card below player -->
      <div class="metadata-container">
        <GlassCard :padding="true">
          <div class="metadata-content">
            <!-- Title & Streamer Info -->
            <div class="title-section">
              <h1 class="video-title">{{ streamTitle }}</h1>
              <div v-if="streamerName" class="streamer-badge">
                <svg class="icon-streamer">
                  <use href="#icon-user" />
                </svg>
                <span class="streamer-name">{{ streamerName }}</span>
              </div>
            </div>

            <!-- Video Stats Grid -->
            <div v-if="chapterData" class="stats-grid">
              <div class="stat-card">
                <svg class="stat-icon">
                  <use href="#icon-clock" />
                </svg>
                <div class="stat-info">
                  <span class="stat-label">Duration</span>
                  <span class="stat-value">{{ formatDuration(chapterData.duration) }}</span>
                </div>
              </div>

              <div class="stat-card">
                <svg class="stat-icon">
                  <use href="#icon-list" />
                </svg>
                <div class="stat-info">
                  <span class="stat-label">Chapters</span>
                  <span class="stat-value">{{ chapterData.chapters?.length || 0 }}</span>
                </div>
              </div>

              <div class="stat-card">
                <svg class="stat-icon">
                  <use href="#icon-film" />
                </svg>
                <div class="stat-info">
                  <span class="stat-label">Stream ID</span>
                  <span class="stat-value">#{{ streamId }}</span>
                </div>
              </div>
            </div>
          </div>
        </GlassCard>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VideoPlayer from '@/components/VideoPlayer.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import GlassCard from '@/components/cards/GlassCard.vue'
import { videoApi } from '@/services/api'

interface ChapterData {
  chapters: Array<{
    start_time: string
    title: string
    type: string
  }>
  stream_id: number
  stream_title: string
  duration?: number
  video_url: string
  video_file: string
  metadata: {
    has_vtt: boolean
    has_srt: boolean
    has_ffmpeg: boolean
  }
}

const route = useRoute()
const router = useRouter()

const streamerId = computed(() => route.params.streamerId as string)
const streamId = computed(() => route.params.streamId as string)
const streamTitle = computed(() => (route.query.title as string) || `Stream ${streamId.value}`)
const streamerName = computed(() => route.query.streamerName as string)

const chapterData = ref<ChapterData | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)

const loadChapterData = async () => {
  try {
    isLoading.value = true
    error.value = null

    // Load video chapters using the new API
    const chapters: any[] = await videoApi.getChapters(parseInt(streamId.value))

    // Create chapter data structure compatible with the video player
    chapterData.value = {
      chapters: chapters.map((chapter: any) => ({
        start_time: chapter.start_time,
        title: chapter.title,
        type: 'chapter'
      })),
      stream_id: parseInt(streamId.value),
      stream_title: streamTitle.value,
      duration: 0, // Will be set by video player
      video_url: `/api/videos/${streamId.value}/stream`,
      video_file: '',
      metadata: {
        has_vtt: false,
        has_srt: false,
        has_ffmpeg: false
      }
    }
  } catch (err: any) {
    console.error('Error loading chapter data:', err)
    error.value = err instanceof Error ? err.message : 'Failed to load video data. Please try again.'
  } finally {
    isLoading.value = false
  }
}

const retryLoad = () => {
  loadChapterData()
}

const goBack = () => {
  router.back()
}

// Video player event handlers
const onChapterChange = (chapter: any, index: number) => {
  console.log('Chapter changed:', chapter.title, 'at index:', index)
}

const onVideoReady = (duration: number) => {
  console.log('Video ready, duration:', duration)
  if (chapterData.value) {
    chapterData.value.duration = duration
  }
}

const onTimeUpdate = (currentTime: number) => {
  // Update progress or other time-based features
}

const formatDuration = (seconds: number | undefined): string => {
  if (!seconds) return 'Unknown'
  
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  
  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`
  }
  return `${minutes}m ${secs}s`
}

onMounted(() => {
  loadChapterData()
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

// ============================================================================
// BASE LAYOUT
// ============================================================================

.video-player-view {
  min-height: 100vh;
  background: var(--background-primary);
  padding: var(--spacing-4);
  
  @include m.respond-below('md') {  // < 768px - Mobile/Tablet
    padding: 0;  // Full-width player on mobile
  }
}

// Fade-in animation (existing from old version)
.fade-in {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

// ============================================================================
// LOADING & ERROR STATES
// ============================================================================

.content-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  padding: var(--spacing-8);
  
  @include m.respond-below('md') {
    padding: var(--spacing-6) var(--spacing-4);
    min-height: 50vh;
  }
}

.state-text {
  margin-top: var(--spacing-4);
  color: var(--text-secondary);
  font-size: var(--text-base);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

// ============================================================================
// PLAYER CONTENT LAYOUT
// ============================================================================

.player-content {
  position: relative;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-6);
  
  @include m.respond-below('md') {
    gap: var(--spacing-4);
  }
}

// ============================================================================
// FLOATING BACK BUTTON - Modern glassmorphism overlay
// ============================================================================

.btn-back-floating {
  position: fixed;
  top: var(--spacing-4);
  left: var(--spacing-4);
  z-index: 100;
  
  // Glassmorphism effect
  background: rgba(var(--background-card-rgb), 0.8);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(var(--border-color-rgb), 0.3);
  border-radius: var(--radius-lg);
  
  // Layout
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  
  // Typography
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  
  // Animation
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  
  .icon {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
  }
  
  .back-text {
    @include m.respond-below('sm') {  // < 640px - Hide text on small mobile
      display: none;
    }
  }
  
  &:hover {
    background: rgba(var(--background-card-rgb), 0.95);
    border-color: var(--primary-color);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(var(--primary-500-rgb), 0.3);
  }
  
  &:active {
    transform: translateY(0);
  }
  
  // Mobile: Larger touch target
  @include m.respond-below('md') {
    min-height: 44px;
    min-width: 44px;
    padding: var(--spacing-3);
  }
}

// ============================================================================
// VIDEO PLAYER CONTAINER
// ============================================================================

.player-container {
  width: 100%;
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: v.$shadow-2xl;
  
  // Remove border-radius on mobile for full-width
  @include m.respond-below('md') {
    border-radius: 0;
    box-shadow: none;
  }
}

// ============================================================================
// METADATA SECTION - Glassmorphism Card
// ============================================================================

.metadata-container {
  padding: 0 var(--spacing-2);
  
  @include m.respond-below('md') {
    padding: 0 var(--spacing-4);
  }
}

.metadata-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-6);
  
  @include m.respond-below('md') {
    gap: var(--spacing-4);
  }
}

// ============================================================================
// TITLE SECTION
// ============================================================================

.title-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.video-title {
  margin: 0;
  font-size: var(--text-2xl);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  line-height: v.$leading-tight;
  
  @include m.respond-below('md') {
    font-size: var(--text-xl);
  }
  
  @include m.respond-below('sm') {
    font-size: var(--text-lg);
  }
}

.streamer-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  
  // Glassmorphism badge
  background: rgba(var(--primary-500-rgb), 0.1);
  border: 1px solid rgba(var(--primary-500-rgb), 0.3);
  border-radius: var(--radius-pill);
  padding: var(--spacing-2) var(--spacing-3);
  
  width: fit-content;
  
  .icon-streamer {
    width: 16px;
    height: 16px;
    stroke: var(--primary-color);
    fill: none;
  }
  
  .streamer-name {
    font-size: var(--text-sm);
    font-weight: v.$font-medium;
    color: var(--primary-color);
  }
}

// ============================================================================
// STATS GRID - Modern card layout
// ============================================================================

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--spacing-4);
  
  @include m.respond-below('sm') {
    grid-template-columns: 1fr;
    gap: var(--spacing-3);
  }
}

.stat-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  
  // Subtle inner glassmorphism
  background: rgba(var(--background-darker-rgb), 0.3);
  border: 1px solid rgba(var(--border-color-rgb), 0.2);
  border-radius: var(--radius-md);
  padding: var(--spacing-3);
  
  transition: all v.$duration-200 v.$ease-out;
  
  &:hover {
    background: rgba(var(--background-darker-rgb), 0.5);
    border-color: rgba(var(--primary-500-rgb), 0.3);
    transform: translateY(-2px);
  }
  
  .stat-icon {
    width: 24px;
    height: 24px;
    stroke: var(--primary-color);
    fill: none;
    flex-shrink: 0;
  }
  
  .stat-info {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }
  
  .stat-label {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: v.$font-medium;
  }
  
  .stat-value {
    font-size: var(--text-base);
    color: var(--text-primary);
    font-weight: v.$font-semibold;
  }
}

// ============================================================================
// MOBILE OPTIMIZATIONS
// ============================================================================

@include m.respond-below('sm') {
  .video-player-view {
    padding: 0;
  }
  
  .player-content {
    gap: var(--spacing-4);
  }
  
  .metadata-container {
    padding: 0 var(--spacing-3);
  }
  
  .btn-back-floating {
    top: var(--spacing-2);
    left: var(--spacing-2);
    
    // Only show icon on very small screens
    .back-text {
      display: none;
    }
  }
}

// ============================================================================
// LANDSCAPE MOBILE - Immersive video mode
// ============================================================================

@media (max-width: 767px) and (orientation: landscape) {
  .btn-back-floating {
    top: var(--spacing-2);
    left: var(--spacing-2);
    padding: var(--spacing-2);
    min-height: 40px;
    min-width: 40px;
    
    .back-text {
      display: none;
    }
  }
  
  .metadata-container {
    display: none;  // Hide metadata in landscape for immersive playback
  }
}
</style>
