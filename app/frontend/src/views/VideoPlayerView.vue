<template>
  <div class="video-player-view">
    <!-- Player Header -->
    <div class="player-header">
      <button @click="goBack" class="btn-back" v-ripple>
        <svg class="icon">
          <use href="#icon-arrow-left" />
        </svg>
        <span>Back</span>
      </button>

      <div class="stream-info">
        <h1 class="stream-title">{{ streamTitle }}</h1>
        <p v-if="streamerName" class="streamer-name">
          <svg class="icon">
            <use href="#icon-user" />
          </svg>
          <span>{{ streamerName }}</span>
        </p>
      </div>
    </div>

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

    <!-- Video Player -->
    <div v-else class="player-wrapper">
      <VideoPlayer
        :video-src="chapterData.video_url"
        :chapters="chapterData.chapters"
        :stream-title="chapterData.stream_title"
        :stream-id="parseInt(streamId)"
        class="video-player-container"
        @chapter-change="onChapterChange"
        @video-ready="onVideoReady"
        @time-update="onTimeUpdate"
      />
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
        start_time: chapter.start_time.toString(),
        title: chapter.title,
        type: 'chapter'
      })),
      stream_id: parseInt(streamId.value),
      stream_title: streamTitle.value,
      duration: chapters.length > 0 ? chapters[chapters.length - 1].end_time : 0,
      video_url: videoApi.getVideoStreamUrl(parseInt(streamId.value)),
      video_file: `stream_${streamId.value}.mp4`,
      metadata: {
        has_vtt: false,
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
}

const onTimeUpdate = (currentTime: number) => {
  // Update progress or other time-based features
}

onMounted(() => {
  loadChapterData()
})
</script>

<style scoped lang="scss">
.video-player-view {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--background-primary);
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

// Header
.player-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-4);
  padding: var(--spacing-4) var(--spacing-6);
  background: var(--background-card);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 100;
  backdrop-filter: blur(10px);
  background: rgba(var(--background-card-rgb), 0.95);
}

.btn-back {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--background-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;

  .icon {
    width: 16px;
    height: 16px;
    fill: currentColor;
  }

  &:hover {
    background: var(--background-tertiary);
    color: var(--text-primary);
    border-color: var(--color-primary);
    transform: translateY(-1px);
  }
}

.stream-info {
  flex: 1;
  min-width: 0;
}

.stream-title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.streamer-name {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  margin: var(--spacing-1) 0 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;

  .icon {
    width: 14px;
    height: 14px;
    fill: currentColor;
    flex-shrink: 0;
  }
}

// Content States
.content-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: var(--spacing-8);
  min-height: 400px;
  animation: fadeIn 0.4s ease-out;
}

.state-text {
  margin-top: var(--spacing-4);
  color: var(--text-secondary);
  font-size: var(--font-size-base);
}

// Player Wrapper
.player-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--background-secondary);
}

.video-player-container {
  flex: 1;
  display: flex;
  flex-direction: column;
}

// Responsive
@media (max-width: 768px) {
  .player-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-3);
    padding: var(--spacing-3) var(--spacing-4);
  }

  .btn-back {
    align-self: flex-start;
  }

  .stream-info {
    width: 100%;
  }

  .stream-title {
    font-size: var(--font-size-base);
    white-space: normal;
    overflow: visible;
    text-overflow: unset;
    line-height: 1.4;
  }

  .streamer-name {
    white-space: normal;
    overflow: visible;
    text-overflow: unset;
  }

  .content-state {
    padding: var(--spacing-6) var(--spacing-4);
    min-height: 300px;
  }
}

@media (max-width: 480px) {
  .player-header {
    padding: var(--spacing-2) var(--spacing-3);
  }

  .stream-title {
    font-size: var(--font-size-sm);
  }

  .streamer-name {
    font-size: var(--font-size-xs);
  }

  .content-state {
    padding: var(--spacing-4) var(--spacing-3);
  }
}

// Landscape mobile optimization
@media (max-width: 768px) and (orientation: landscape) {
  .player-header {
    flex-direction: row;
    align-items: center;
    padding: var(--spacing-2) var(--spacing-4);
  }

  .stream-title {
    font-size: var(--font-size-sm);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .streamer-name {
    font-size: var(--font-size-xs);
  }

  .content-state {
    min-height: 200px;
    padding: var(--spacing-4);
  }
}
</style>
