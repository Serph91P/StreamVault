<template>
  <div class="page-view video-player-view fade-in">
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
    <div v-else class="player-layout">
      <!-- Main Content: Video + Sidebar -->
      <div class="player-main">
        <!-- Video Player with Header -->
        <GlassCard variant="strong" :padding="false" class="player-card">
          <!-- Header inside the card -->
          <div class="player-header">
            <button @click="goBack" class="back-button" v-ripple>
              <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M19 12H5M12 19l-7-7 7-7" />
              </svg>
              Back
            </button>
            
            <h1 class="video-title">{{ streamTitle }}</h1>
            
            <div v-if="streamerName" class="streamer-badge">
              <svg class="icon-streamer">
                <use href="#icon-user" />
              </svg>
              <span>{{ streamerName }}</span>
            </div>
          </div>

          <!-- Video Player - directly in card, no wrapper -->
          <VideoPlayer
            :video-src="chapterData.video_url"
            :chapters="chapterData.chapters"
            :stream-title="chapterData.stream_title"
            :stream-id="parseInt(streamId)"
            @chapter-change="onChapterChange"
            @video-ready="onVideoReady"
            @time-update="onTimeUpdate"
          />
        </GlassCard>

        <!-- Info Sidebar -->
        <aside class="info-sidebar">
          <!-- Stream Details -->
          <GlassCard variant="subtle" class="info-card">
            <h3 class="info-title">
              <svg class="info-icon">
                <use href="#icon-info" />
              </svg>
              Stream Details
            </h3>
            <div class="info-list">
              <div class="info-row">
                <span class="info-label">Duration</span>
                <span class="info-value highlight">{{ formatDuration(chapterData.duration ?? 0) }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Stream ID</span>
                <span class="info-value">#{{ streamId }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Recorded</span>
                <span class="info-value">{{ formattedDate }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Format</span>
                <span class="info-value">{{ chapterData.metadata?.has_vtt ? 'VTT Chapters' : 'Standard' }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Quality</span>
                <span class="info-value">1080p60</span>
              </div>
            </div>
          </GlassCard>

          <!-- Chapters List -->
          <GlassCard v-if="chapterData.chapters?.length > 0" variant="subtle" class="info-card chapters-card">
            <h3 class="info-title">
              <svg class="info-icon">
                <use href="#icon-list" />
              </svg>
              Chapters ({{ chapterData.chapters.length }})
            </h3>
            <div class="chapters-list">
              <div
                v-for="(chapter, index) in chapterData.chapters"
                :key="index"
                class="chapter-item"
                :class="{ 'active': currentChapterIndex === index }"
                @click="seekToChapter(chapter)"
              >
                <span class="chapter-time">{{ chapter.start_time }}</span>
                <span class="chapter-title">{{ chapter.title }}</span>
              </div>
            </div>
          </GlassCard>

          <!-- Quick Actions -->
          <GlassCard variant="subtle" class="info-card">
            <h3 class="info-title">
              <svg class="info-icon">
                <use href="#icon-settings" />
              </svg>
              Actions
            </h3>
            <div class="action-buttons">
              <button class="action-btn" v-ripple>
                <svg class="action-icon"><use href="#icon-download" /></svg>
                Download
              </button>
              <button class="action-btn" v-ripple>
                <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="18" cy="5" r="3"/>
                  <circle cx="6" cy="12" r="3"/>
                  <circle cx="18" cy="19" r="3"/>
                  <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
                  <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
                </svg>
                Share
              </button>
              <button class="action-btn danger" v-ripple>
                <svg class="action-icon"><use href="#icon-trash-2" /></svg>
                Delete
              </button>
            </div>
          </GlassCard>
        </aside>
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

const _streamerId = computed(() => route.params.streamerId as string)
// Support both route patterns: /videos/:id and /streamer/:streamerId/stream/:streamId/watch
const streamId = computed(() => {
  // Check for 'id' parameter first (from /videos/:id route)
  if (route.params.id) {
    return route.params.id as string
  }
  // Fallback to 'streamId' parameter (from legacy route)
  return route.params.streamId as string
})
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
    let chapters: any[] = []
    let videoUrl = `/api/videos/${streamId.value}/stream`
    
    try {
      chapters = await videoApi.getChapters(parseInt(streamId.value))
    } catch {
      // If no chapters available, use mock data for development
      chapters = [
        { start_time: '0:00', title: 'Stream Start', type: 'chapter' },
        { start_time: '0:05', title: 'Intro & Welcome', type: 'chapter' },
        { start_time: '0:10', title: 'Main Gameplay', type: 'chapter' },
        { start_time: '0:15', title: 'Epic Moment', type: 'chapter' },
        { start_time: '0:20', title: 'Chat Interaction', type: 'chapter' },
        { start_time: '0:25', title: 'Outro', type: 'chapter' },
      ]
      // Use a public sample video for demo purposes
      videoUrl = 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4'
    }

    // Create chapter data structure compatible with the video player
    chapterData.value = {
      chapters: chapters.map((chapter: any) => ({
        start_time: chapter.start_time,
        title: chapter.title,
        type: 'chapter'
      })),
      stream_id: parseInt(streamId.value),
      stream_title: streamTitle.value,
      duration: 596, // Big Buck Bunny duration
      video_url: videoUrl,
      video_file: '',
      metadata: {
        has_vtt: true,
        has_srt: false,
        has_ffmpeg: true
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

const onTimeUpdate = (_currentTime: number) => {
  // Update progress or other time-based features
}

// Helper functions
const formatDuration = (seconds: number): string => {
  if (!seconds) return '0:00'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

const formattedDate = computed(() => {
  // Mock date for now
  return new Date().toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
})

// Chapter navigation
const currentChapterIndex = ref(0)

const seekToChapter = (chapter: any) => {
  console.log('Seeking to chapter:', chapter.title)
  // The VideoPlayer component handles actual seeking
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
  // Override page-view padding for more immersive video experience on mobile
  @include m.respond-below('sm') {
    padding: var(--spacing-2) var(--spacing-2);
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
  min-height: 50vh;
  padding: var(--spacing-8);
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
// PLAYER LAYOUT
// ============================================================================

.player-layout {
  display: flex;
  flex-direction: column;
}

// ============================================================================
// MAIN CONTENT: Video + Sidebar side by side
// ============================================================================

.player-main {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: var(--spacing-4);
  align-items: start;
  
  @include m.respond-below('xl') {
    grid-template-columns: 1fr 280px;
  }
  
  @include m.respond-below('lg') {
    grid-template-columns: 1fr;
  }
}

// ============================================================================
// VIDEO PLAYER CARD (includes header)
// ============================================================================

.player-card {
  overflow: hidden;
  
  :deep(.glass-card-content) {
    padding: 0;
    display: flex;
    flex-direction: column;
  }
}

.player-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);
  
  @include m.respond-below('sm') {
    flex-wrap: wrap;
    padding: var(--spacing-2) var(--spacing-3);
  }
}

.back-button {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--background-darker);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-weight: v.$font-medium;
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  flex-shrink: 0;

  .icon {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
  }

  &:hover {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: white;
  }
}

.video-title {
  flex: 1;
  margin: 0;
  font-size: var(--text-lg);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  
  @include m.respond-below('sm') {
    font-size: var(--text-base);
    order: 3;
    flex-basis: 100%;
    margin-top: var(--spacing-2);
  }
}

.streamer-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  background: rgba(var(--primary-500-rgb), 0.15);
  border: 1px solid rgba(var(--primary-500-rgb), 0.3);
  border-radius: var(--radius-pill);
  padding: var(--spacing-1) var(--spacing-3);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  color: var(--primary-color);
  flex-shrink: 0;
  
  .icon-streamer {
    width: 14px;
    height: 14px;
    stroke: currentColor;
    fill: none;
  }
}

// ============================================================================
// INFO SIDEBAR
// ============================================================================

.info-sidebar {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
  
  @include m.respond-below('lg') {
    flex-direction: row;
    flex-wrap: wrap;
    
    .info-card {
      flex: 1;
      min-width: 280px;
    }
  }
}

.info-card {
  flex-shrink: 0;
}

.info-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  margin: 0 0 var(--spacing-3) 0;
  font-size: var(--text-base);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  
  .info-icon {
    width: 18px;
    height: 18px;
    stroke: var(--primary-color);
    fill: none;
  }
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-2) 0;
  border-bottom: 1px solid var(--border-color);
  
  &:last-child {
    border-bottom: none;
  }
}

.info-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.info-value {
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  color: var(--text-primary);
  
  &.highlight {
    color: var(--primary-color);
    font-weight: v.$font-bold;
  }
}

// ============================================================================
// CHAPTERS LIST
// ============================================================================

.chapters-card {
  max-height: 250px;
  display: flex;
  flex-direction: column;
  
  :deep(.glass-card-content) {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
}

.chapters-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
  overflow-y: auto;
  flex: 1;
  
  &::-webkit-scrollbar {
    width: 4px;
  }
  
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  
  &::-webkit-scrollbar-thumb {
    background: var(--primary-color);
    border-radius: var(--radius-full);
  }
}

.chapter-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2);
  background: var(--background-darker);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all v.$duration-150 v.$ease-out;
  
  &:hover {
    background: rgba(var(--primary-500-rgb), 0.15);
    padding-left: var(--spacing-3);
  }
  
  &.active {
    background: rgba(var(--primary-500-rgb), 0.2);
    border-left: 2px solid var(--primary-color);
  }
}

.chapter-time {
  flex-shrink: 0;
  font-family: v.$font-mono;
  font-size: 11px;
  color: var(--primary-color);
  background: rgba(var(--primary-500-rgb), 0.1);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.chapter-title {
  font-size: var(--text-xs);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

// ============================================================================
// ACTION BUTTONS
// ============================================================================

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  
  .action-icon {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
  }
  
  &:hover {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: white;
  }
  
  &.danger:hover {
    background: var(--danger-color);
    border-color: var(--danger-color);
  }
}

// ============================================================================
// MOBILE LAYOUT
// ============================================================================

@include m.respond-below('md') {
  .player-main {
    gap: var(--spacing-3);
  }
}

// ============================================================================
// LANDSCAPE MOBILE - Immersive
// ============================================================================

@media (max-width: 767px) and (orientation: landscape) {
  .player-header,
  .info-sidebar {
    display: none;
  }
  
  .player-container {
    height: 100vh;
    aspect-ratio: auto;
  }
}
</style>
