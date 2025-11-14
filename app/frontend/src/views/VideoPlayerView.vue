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
      <!-- Header: Title + Streamer + Back Button -->
      <div class="player-header">
        <button @click="goBack" class="btn btn-secondary btn-icon-text" v-ripple>
          <svg class="icon">
            <use href="#icon-arrow-left" />
          </svg>
          <span>Back</span>
        </button>

        <div class="title-section">
          <h1 class="video-title">{{ streamTitle }}</h1>
          <div v-if="streamerName" class="streamer-badge">
            <svg class="icon-streamer">
              <use href="#icon-user" />
            </svg>
            <span class="streamer-name">{{ streamerName }}</span>
          </div>
        </div>
      </div>

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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VideoPlayer from '@/components/VideoPlayer.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
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
  padding: var(--spacing-6) var(--spacing-4);
  
  @include m.respond-below('md') {
    padding: var(--spacing-4) 0;
  }
}

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
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
}

// ============================================================================
// HEADER - Title, Streamer, Back Button
// ============================================================================

.player-header {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-4);
  padding: 0 var(--spacing-2);
  
  @include m.respond-below('md') {
    flex-direction: column;
    gap: var(--spacing-3);
    padding: 0 var(--spacing-4);
  }
}

.btn-icon-text {
  flex-shrink: 0;
  
  .icon {
    width: 18px;
    height: 18px;
  }
}

.title-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  min-width: 0;
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
  
  background: rgba(var(--primary-500-rgb), 0.1);
  border: 1px solid rgba(var(--primary-500-rgb), 0.3);
  border-radius: var(--radius-pill);
  padding: var(--spacing-2) var(--spacing-3);
  
  width: fit-content;
  
  .icon-streamer {
    width: 14px;
    height: 14px;
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
// VIDEO PLAYER CONTAINER
// ============================================================================

.player-container {
  width: 100%;
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: v.$shadow-2xl;
  
  @include m.respond-below('md') {
    border-radius: 0;
    box-shadow: none;
  }
}

// ============================================================================
// MOBILE OPTIMIZATIONS
// ============================================================================

@include m.respond-below('sm') {
  .video-player-view {
    padding: var(--spacing-3) 0;
  }
  
  .player-content {
    gap: var(--spacing-3);
  }
  
  .player-header {
    padding: 0 var(--spacing-3);
  }
}

// ============================================================================
// LANDSCAPE MOBILE - Immersive video mode
// ============================================================================

@media (max-width: 767px) and (orientation: landscape) {
  .player-header {
    display: none;  // Hide header in landscape for immersive playback
  }
  
  .player-content {
    gap: 0;
  }
}
</style>
