<template>
  <div class="video-player-container">
    <!-- Video Element -->
    <div class="video-wrapper" ref="videoWrapper" @mouseenter="revealControls" @mouseleave="onVideoLeave" @mousemove="revealControls" @touchstart="revealControls">
      <video
        ref="videoElement"
        :src="decodedVideoSrc"
        @loadedmetadata="onVideoLoaded"
        @timeupdate="onTimeUpdate"
        @loadstart="onLoadStart"
        @canplay="onCanPlay"
        @error="onVideoError"
        @play="onPlay"
        @pause="onPause"
        @click="togglePlayPause"
        @keydown.space.prevent="togglePlayPause"
        preload="metadata"
        class="video-element"
        tabindex="0"
        role="application"
        aria-label="Video player"
      >
        <!-- WebVTT chapters track -->
        <track
          v-if="chaptersUrl"
          kind="chapters"
          :src="chaptersUrl"
          srclang="en"
          label="Chapters"
          default
        />
        Your browser does not support the video tag.
      </video>

      <!-- Custom Video Controls Overlay -->
      <div
        v-show="showControls || !isPlaying"
        class="video-controls-overlay"
        @click.stop
        @touchstart="revealControls"
      >
        <!-- Progress Bar with Chapter Markers -->
        <div
          class="progress-container"
          role="slider"
          tabindex="0"
          aria-label="Video progress"
          aria-valuemin="0"
          :aria-valuemax="Math.round(videoDuration)"
          :aria-valuenow="Math.round(currentTime)"
          @click="seekVideo"
          @keydown.left.prevent="seekByKeyboard(-5)"
          @keydown.right.prevent="seekByKeyboard(5)"
          @keydown.home.prevent="seekToTime(0)"
          @keydown.end.prevent="seekToTime(videoDuration)"
        >
          <div class="progress-bar-track">
            <!-- Chapter markers background -->
            <div class="chapter-markers" v-if="parsedChapters.length > 0">
              <div
                v-for="(chapter, index) in parsedChapters"
                :key="index"
                class="chapter-marker"
                :style="{
                  left: `${(chapter.startTime / videoDuration) * 100}%`,
                  width: `${(chapter.duration / videoDuration) * 100}%`,
                  backgroundColor: getChapterColor(chapter.title)
                }"
                :title="`${chapter.title} - ${formatTime(chapter.startTime)} (${formatDuration(chapter.duration)})`"
                @click.stop="seekToChapter(chapter.startTime)"
              ></div>
            </div>
            <div class="progress-bar-fill" :style="{ width: progressPercentage + '%' }"></div>
            <div class="progress-bar-thumb" :style="{ left: progressPercentage + '%' }"></div>
          </div>
        </div>

        <!-- Control Buttons -->
        <div class="controls-bottom">
          <div class="controls-left">
            <!-- Play/Pause Button (Primary) -->
            <button
              @click="togglePlayPause"
              class="control-button play-pause-button"
              :aria-label="isPlaying ? 'Pause' : 'Play'"
            >
              <svg v-if="!isPlaying" viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                <path d="M8 5v14l11-7z"/>
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
              </svg>
            </button>

            <!-- Volume Control -->
            <button
              @click="toggleMute"
              class="control-button volume-button"
              :aria-label="isMuted ? 'Unmute' : 'Mute'"
            >
              <svg v-if="!isMuted && volume > 0.5" viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
              </svg>
              <svg v-else-if="!isMuted && volume > 0" viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                <path d="M7 9v6h4l5 5V4l-5 5H7z"/>
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
              </svg>
            </button>

            <!-- Time Display -->
            <div class="time-display">
              <span>{{ formatTime(currentTime) }}</span>
              <span class="time-separator">/</span>
              <span>{{ formatTime(videoDuration) }}</span>
            </div>
          </div>

          <div class="controls-right">
            <!-- Chapter Navigation (when chapters exist) -->
            <template v-if="parsedChapters.length > 0">
              <!-- Previous Chapter Button -->
              <button
                @click="seekChapterBy(-1)"
                :disabled="currentChapterIndex <= 0"
                class="control-button chapter-nav-button"
                :aria-label="'Previous Chapter'"
                :title="`Previous: ${parsedChapters[currentChapterIndex - 1]?.title || 'None'}`"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                  <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/>
                </svg>
              </button>

              <!-- Current Chapter Info inline -->
              <div v-if="currentChapter" class="current-chapter-inline">
                <span class="chapter-inline-title">{{ currentChapter.title }}</span>
                <span class="chapter-inline-time">{{ formatTime(currentTime - currentChapter.startTime) }} / {{ formatDuration(currentChapter.duration) }}</span>
              </div>

              <!-- Chapters Button (Toggle List) -->
              <button
                @click="toggleChapterUI"
                class="control-button chapters-button"
                :class="{ 'active': showChapterUI }"
                :aria-label="'Chapters'"
                :title="`${parsedChapters.length} Chapters${currentChapter ? ': ' + currentChapter.title : ''}`"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                  <path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z"/>
                </svg>
                <span class="chapter-count">{{ parsedChapters.length }}</span>
              </button>

              <!-- Next Chapter Button -->
              <button
                @click="seekChapterBy(1)"
                :disabled="currentChapterIndex >= parsedChapters.length - 1"
                class="control-button chapter-nav-button"
                :aria-label="'Next Chapter'"
                :title="`Next: ${parsedChapters[currentChapterIndex + 1]?.title || 'None'}`"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                  <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/>
                </svg>
              </button>
            </template>

            <button
              @click="emit('toggle-theater')"
              class="control-button theater-button"
              :class="{ active: theaterMode }"
              :aria-label="theaterMode ? 'Show details' : 'Theater mode'"
              :aria-pressed="theaterMode"
            >
              <svg viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                <path d="M3 5h18v12H3V5zm2 2v8h14V7H5zm4 12h6v2H9v-2z"/>
              </svg>
            </button>

            <!-- Fullscreen Button -->
            <button
              @click="toggleFullscreen"
              class="control-button fullscreen-button"
              :aria-label="isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'"
            >
              <svg v-if="!isFullscreen" viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                <path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="isLoading && !error" class="loading-overlay">
        <PlayerStatus state="loading" message="Preparing video for playback..." />
      </div>

      <!-- Error State -->
      <div v-if="error" class="error-overlay">
        <PlayerError
          title="Playback Error"
          :message="error"
          action-label="Retry"
          @action="retryLoad"
        />
      </div>

      <!-- Chapter List Panel (Overlay inside video) -->
      <transition name="slide-panel">
        <dialog
            v-if="showChapterUI && parsedChapters.length > 0"
            class="chapter-list-panel"
            ref="chapterListPanel"
            aria-label="Chapters"
            @cancel.prevent="closeChapterUI"
            @keydown="containFocus($event, $event.currentTarget as HTMLDialogElement)"
            @click.self="dismissChapterBackdrop"
            @scroll="handleChapterListScroll"
          >
        <div class="chapter-list-header">
          <h3>Chapters</h3>
          <button @click="closeChapterUI" class="close-btn" aria-label="Close chapters">x</button>
        </div>
        <div class="chapter-list">
          <button
            v-for="(chapter, index) in parsedChapters"
            :key="index"
            type="button"
            class="chapter-item"
            :class="{ 'active': currentChapterIndex === index }"
            :ref="el => { if (el) chapterItemRefs[index] = el as HTMLElement }"
            @click="seekToChapter(chapter.startTime)"
          >
            <div class="chapter-thumbnail" v-if="chapter.thumbnail">
              <img :src="chapter.thumbnail" :alt="chapter.title" />
            </div>
            <div class="chapter-icon" v-else-if="chapter.gameIcon">
              <img
                v-if="!chapter.gameIcon.startsWith('icon:')"
                :src="chapter.gameIcon"
                :alt="chapter.title"
              />
              <i
                v-else
                :class="chapter.gameIcon.replace('icon:', '')"
                class="category-icon"
              ></i>
            </div>
            <div class="chapter-placeholder" v-else>
              <svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24"><path d="M8 5v14l11-7z"/></svg>
            </div>

            <ChapterDetails
              :title="chapter.title" :category-name="chapter.categoryName"
              :start="chapter.startTime" :end="chapter.endTime ?? chapter.startTime + chapter.duration" truncate
            />
          </button>
        </div>
        </dialog>
      </transition>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useCategoryImages } from '@/composables/useCategoryImages'
import PlayerStatus from '@/components/player/PlayerStatus.vue'
import PlayerError from '@/components/player/PlayerError.vue'
import ChapterDetails from '@/components/player/ChapterDetails.vue'
import { videoApi } from '@/services/api'
import { containFocus } from '@/utils/focus'
import { formatTime } from '@/utils/playerClock'

interface Chapter {
  title: string
  startTime: number // in seconds
  duration: number // in seconds
  endTime?: number
  categoryName?: string | null
  thumbnail?: string
  gameIcon?: string
}

interface ApiChapter {
  id?: number
  title?: string
  start?: number
  end?: number
  start_time?: string
  category_name?: string | null
  type?: string
}

interface Props {
  videoSrc: string
  streamId?: number
  chaptersUrl?: string // URL to WebVTT chapter file
  autoChapters?: boolean // Auto-generate chapters from category changes
  chapters?: ApiChapter[] // Pre-loaded chapters from API
  theaterMode?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  autoChapters: true,
  theaterMode: false
})

const emit = defineEmits<{
  'chapter-change': [chapter: Chapter, index: number]
  'video-ready': [duration: number]
  'toggle-theater': []
}>()

const videoElement = ref<HTMLVideoElement>()
const videoWrapper = ref<HTMLDivElement>()
const chapterListPanel = ref<HTMLDialogElement>()

const chapterItemRefs = ref<Record<number, HTMLElement>>({})
const isLoading = ref(true)
const error = ref<string>('')
const currentTime = ref(0)
const videoDuration = ref(0)
const showChapterUI = ref(false)
const parsedChapters = ref<Chapter[]>([])

// Custom controls state
const isPlaying = ref(false)
const isMuted = ref(false)
const volume = ref(1)
const showControls = ref(true)
const controlsTimeout = ref<number | null>(null)
const isFullscreen = ref(false)

// Category images composable
const { getCategoryImage } = useCategoryImages()

// Progress percentage for progress bar
const progressPercentage = computed(() => {
  if (videoDuration.value === 0) return 0
  return (currentTime.value / videoDuration.value) * 100
})

// Current chapter detection
const currentChapterIndex = computed(() => {
  for (let i = parsedChapters.value.length - 1; i >= 0; i--) {
    if (currentTime.value >= parsedChapters.value[i].startTime) {
      return i
    }
  }
  return 0
})

const currentChapter = computed(() => {
  return parsedChapters.value[currentChapterIndex.value] || null
})

// Video URL decoding
const decodedVideoSrc = computed(() => {
  if (!props.videoSrc) return ''

  try {
    return decodeURIComponent(props.videoSrc)
  } catch (error) {
    console.error('Error decoding video src:', error)
    return props.videoSrc
  }
})

// Custom Controls Functions
const togglePlayPause = () => {
  if (!videoElement.value) return

  if (isPlaying.value) {
    videoElement.value.pause()
  } else {
    videoElement.value.play()
  }
}

const toggleMute = () => {
  if (!videoElement.value) return

  videoElement.value.muted = !videoElement.value.muted
  isMuted.value = videoElement.value.muted

  if (!isMuted.value && volume.value === 0) {
    videoElement.value.volume = 0.5
    volume.value = 0.5
  }
}

const seekVideo = (event: MouseEvent) => {
  if (!videoElement.value) return

  const progressBar = event.currentTarget as HTMLElement
  const rect = progressBar.getBoundingClientRect()
  const clickX = event.clientX - rect.left
  const percentage = clickX / rect.width
  const seekTime = percentage * videoDuration.value

  videoElement.value.currentTime = seekTime
}

const seekToTime = (time: number) => {
  if (!videoElement.value) return

  videoElement.value.currentTime = Math.min(Math.max(time, 0), videoDuration.value)
}

const seekByKeyboard = (deltaSeconds: number) => {
  seekToTime(currentTime.value + deltaSeconds)
}

const toggleFullscreen = async () => {
  if (!videoWrapper.value) return

  try {
    if (!document.fullscreenElement) {
      await videoWrapper.value.requestFullscreen()
      isFullscreen.value = true
    } else {
      await document.exitFullscreen()
      isFullscreen.value = false
    }
  } catch (err) {
    console.error('Fullscreen error:', err)
  }
}

const revealControls = () => {
  showControls.value = true
  resetControlsTimeout()
}

const onVideoLeave = () => {
  if (isPlaying.value) {
    resetControlsTimeout()
  }
}


const resetControlsTimeout = () => {
  if (controlsTimeout.value) {
    clearTimeout(controlsTimeout.value)
  }

  // Hide controls after 5 seconds on mobile, 3 seconds on desktop
  const hideDelay = window.innerWidth < 768 ? 5000 : 3000

  if (isPlaying.value) {
    controlsTimeout.value = window.setTimeout(() => {
      showControls.value = false
    }, hideDelay)
  }
}

const onPlay = () => {
  isPlaying.value = true
  resetControlsTimeout()
}

const onPause = () => {
  isPlaying.value = false
  showControls.value = true

  if (controlsTimeout.value) {
    clearTimeout(controlsTimeout.value)
  }
}

// Event handlers
const onVideoLoaded = () => {
  const video = videoElement.value
  if (!video) return
  videoDuration.value = video.duration
  volume.value = video.volume
  isMuted.value = video.muted
  emit('video-ready', videoDuration.value)
  if (parsedChapters.value.length) parsedChapters.value = calculateChapterDurations([...parsedChapters.value])
}

const onTimeUpdate = () => {
  currentTime.value = videoElement.value?.currentTime ?? 0
}

const onLoadStart = () => {
  isLoading.value = true
  error.value = ''
}

const onCanPlay = () => {
  isLoading.value = false
}

const onVideoError = () => {
  isLoading.value = false
  error.value = 'Failed to load video. Please check the video file and try again.'
}

const retryLoad = () => videoElement.value?.load()

// Chapter navigation
const seekToChapter = (startTime: number) => {
  if (videoElement.value) videoElement.value.currentTime = startTime
}

const seekChapterBy = (offset: number) => {
  const chapter = parsedChapters.value[currentChapterIndex.value + offset]
  if (chapter) seekToChapter(chapter.startTime)
}

const closeChapterUI = () => {
  // End modal inertness (and restore the opener) before Vue starts leaving.
  chapterListPanel.value?.close()
  showChapterUI.value = false
}

const toggleChapterUI = () => {
  if (showChapterUI.value) return closeChapterUI()
  showChapterUI.value = true
  void nextTick(() => {
    // The browser top layer escapes ancestor clipping/stacking and also works
    // inside fullscreen. A larger page z-index cannot guarantee either.
    chapterListPanel.value?.showModal()
    chapterListPanel.value?.focus()
  })
}

const dismissChapterBackdrop = (event: MouseEvent) => {
  const { left, right, top, bottom } = chapterListPanel.value!.getBoundingClientRect()
  if (event.clientX < left || event.clientX > right || event.clientY < top || event.clientY > bottom) closeChapterUI()
}

// Chapter loading
const loadChapters = async () => {
  // First, check if we have pre-loaded chapters from props
  if (props.chapters) return // The immediate props watcher owns conversion.

  if (props.streamId && props.autoChapters) {
    try {
      const chaptersData = await videoApi.getChapters(props.streamId)
      parsedChapters.value = convertApiChaptersToInternal(chaptersData)
    } catch (e) {
      console.warn('Failed to load auto-generated chapters:', e)
    }
  }

  // If we have a chapters URL, try to parse WebVTT chapters
  if (props.chaptersUrl) {
    try {
      const response = await fetch(props.chaptersUrl, {
        credentials: 'include' // CRITICAL: Required to send session cookie
      })
      if (response.ok) {
        const vttText = await response.text()
        parseWebVTTChapters(vttText)
      }
    } catch (e) {
      console.warn('Failed to load WebVTT chapters:', e)
    }
  }
}

// Convert API chapters to internal format
const convertApiChaptersToInternal = (apiChapters: ApiChapter[]): Chapter[] => {
  const converted = apiChapters.map((chapter, index) => {
    const startTime = typeof chapter.start === 'number'
      ? chapter.start
      : parseTimeStringToSeconds(chapter.start_time || '')
    const hasEnd = typeof chapter.end === 'number' && chapter.end >= startTime

    return {
      title: chapter.title || chapter.category_name || `Chapter ${index + 1}`,
      categoryName: chapter.category_name,
      startTime,
      endTime: hasEnd ? chapter.end : undefined,
      duration: hasEnd ? chapter.end! - startTime : undefined,
      gameIcon: chapter.category_name ? getCategoryImage(chapter.category_name) : undefined,
    }
  })

  const unique = [...new Map(converted.map(chapter => [
    `${chapter.startTime}:${chapter.title}`, chapter
  ])).values()]

  return calculateChapterDurations(unique)
}

// Calculate chapter durations based on video metadata
const calculateChapterDurations = (
  chapterList: Array<Omit<Chapter, 'duration'> & { duration?: number }>
): Chapter[] => {
  const videoDur = videoElement.value?.duration || videoDuration.value
  return chapterList.map((chapter, index) => {
    chapter.duration = chapter.endTime !== undefined
      ? chapter.endTime - chapter.startTime
      : index < chapterList.length - 1
        ? chapterList[index + 1].startTime - chapter.startTime
        : videoDur > 0 ? videoDur - chapter.startTime : 60
    return chapter as Chapter
  })
}

// Parse time string to seconds
const parseTimeStringToSeconds = (timeString: string): number => {
  if (!timeString) return 0

  // Handle ISO datetime format
  if (timeString.includes('T')) {
    return 0
  }

  // Handle HH:MM:SS.mmm or MM:SS format
  const parts = timeString.split(':').map(Number)
  if (parts.length === 2) return parts[0] * 60 + parts[1]
  return parts.length === 3 ? parts[0] * 3600 + parts[1] * 60 + parts[2] : 0
}

const parseWebVTTChapters = (vttText: string) => {
  const cue = /(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})[^\n]*\n([^\n]*)/g
  const chapters = Array.from(vttText.matchAll(cue), match => {
    const startTime = parseTimeStringToSeconds(match[1])
    return {
      title: match[3].trim() || 'Chapter',
      startTime,
      endTime: parseTimeStringToSeconds(match[2]),
      duration: parseTimeStringToSeconds(match[2]) - startTime
    }
  })
  if (chapters.length) parsedChapters.value = chapters
}


// Utility functions
const formatDuration = (seconds: number): string => {
  const minutes = Math.floor(seconds / 60)
  return minutes > 60
    ? `${Math.floor(minutes / 60)}h ${minutes % 60}m`
    : `${minutes}m ${Math.floor(seconds % 60)}s`
}

const getChapterColor = (title: string) => `hsl(${title.length * 47 % 360}, 70%, 60%)`

// Scroll indicator management for chapter list
const handleChapterListScroll = (event: Event) => {
  const element = event.target as HTMLElement
  if (!element) return

  element.classList.toggle('scrolled-top', element.scrollTop > 10)
  element.classList.toggle(
    'scrolled-bottom',
    element.scrollTop < element.scrollHeight - element.clientHeight - 10
  )
}

// Auto-scroll to keep active chapter centered
const scrollToActiveChapter = (index: number) => {
  const panel = chapterListPanel.value
  const item = chapterItemRefs.value[index]
  if (!panel || !item) return
  panel.scrollTo({
    top: item.offsetTop - panel.clientHeight / 2 + item.offsetHeight / 2,
    behavior: 'smooth'
  })
}

// Watch for chapter changes and emit events + auto-scroll
watch(currentChapterIndex, (newIndex, oldIndex) => {
  if (newIndex !== oldIndex && parsedChapters.value[newIndex]) {
    emit('chapter-change', parsedChapters.value[newIndex], newIndex)

    // Auto-scroll to active chapter if chapter UI is visible
    if (showChapterUI.value) {
      setTimeout(() => {
        scrollToActiveChapter(newIndex)
      }, 100)
    }
  }
})

// Keyboard shortcuts
const onKeyDown = (event: KeyboardEvent) => {
  if (!videoElement.value) return

  const modified = event.ctrlKey || event.metaKey
  if (modified && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
    event.preventDefault()
    seekChapterBy(event.key === 'ArrowLeft' ? -1 : 1)
  } else if (!modified && event.key.toLowerCase() === 'c') {
    event.preventDefault()
    toggleChapterUI()
  }
}

onMounted(() => {
  loadChapters()
  document.addEventListener('keydown', onKeyDown)

  // Add fullscreen change listener
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

const onFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement
}

onUnmounted(() => {
  document.removeEventListener('keydown', onKeyDown)

  // Clean up controls timeout
  if (controlsTimeout.value) {
    clearTimeout(controlsTimeout.value)
  }

  // Clean up fullscreen listener
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})

// Watch for changes in chapters prop
watch(() => props.chapters, (newChapters) => {
  if (newChapters) {
    parsedChapters.value = convertApiChaptersToInternal(newChapters)
    if (!newChapters.length) closeChapterUI()
  }
}, { immediate: true })

defineExpose({ seekToChapter })
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* ============================================================================
   VIDEO PLAYER - Modern Design (PWA Mobile-First)
   Note: Container styling handled by parent GlassCard in VideoPlayerView
   ============================================================================ */

.video-player-container {
  container: player / inline-size;
  position: relative;
  width: 100%;
  max-width: 100%;
  overflow: hidden;

  // Mobile: Allow controls to overflow
  @include m.respond-below('md') {  // < 768px
    overflow: visible;  // CRITICAL: Allow chapter menu and controls to overflow
  }
}

// Progress plus two possible control rows must retain their 44px targets.
$min-stage-height: calc(132px + var(--spacing-8));

.video-wrapper {
  container: video-stage / inline-size;
  position: relative;
  width: 100%;
  min-height: $min-stage-height;
  background: var(--background-darker);
  overflow: hidden;

  // Desktop: 16:9, but never taller than the height budget the embedding
  // view provides via --player-max-h (YouTube-style sizing: the page should
  // not scroll just to reveal the bottom of the player).
  @include m.respond-to('md') {  // >= 768px
    aspect-ratio: 16/9;
    max-height: var(--player-max-h, none);
    width: min(100%, calc(max(var(--player-max-h, 9999px), #{$min-stage-height}) * 16 / 9));
    margin-inline: auto;
  }

  // Mobile Portrait: Full viewport width, no constraints
  @include m.respond-below('md') {  // < 768px
    width: 100%;
    max-width: 100%;
    margin: 0;
    aspect-ratio: 16/9;
  }
}

.video-element {
  width: 100%;
  height: 100%;
  display: block;
  background: var(--background-darker);
  object-fit: contain;

  // Desktop: Fill the player shell without leaving an empty lower band
  @include m.respond-to('md') {  // >= 768px
    max-height: none;
  }

  // Mobile Portrait: Full width with 16:9 ratio
  @include m.respond-below('md') {  // < 768px
    max-height: none;
  }
}

// Normal landscape reserves room for app chrome and route navigation.
@media (max-width: 767px) and (orientation: landscape) {
  .video-wrapper {
    height: var(--player-max-h);
    width: 100%;
    aspect-ratio: auto;
    margin: 0;
  }

  .video-element {
    height: 100%;
    width: 100%;
    max-height: 100vh;
  }
}

/* Loading and Error States */
.loading-overlay,
.error-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: white;
  z-index: 20;
  gap: var(--spacing-4);  /* 16px */
}

.error-overlay {
  z-index: 30;
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(255, 255, 255, 0.2);
  border-top-color: var(--primary-color);
  border-radius: var(--radius-full);
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-icon {
  font-size: var(--text-5xl);  /* 48px */

  @include m.respond-below('md') {
    display: none;
  }
}

.error-message {
  text-align: center;
  max-width: 300px;
  font-size: var(--text-base);  /* 16px */
  line-height: var(--leading-relaxed);
  color: rgba(255, 255, 255, 0.9);
}

.retry-btn {
  background: var(--primary-color);
  border: none;
  color: white;
  padding: var(--spacing-3) var(--spacing-6);  /* 12px 24px */
  border-radius: var(--radius-md);  /* 10px */
  cursor: pointer;
  font-weight: var(--font-semibold);  /* 600 */
  font-size: var(--text-sm);  /* 14px */
  transition: var(--transition-all);
  box-shadow: var(--shadow-md);
}

.retry-btn:hover {
  background: var(--primary-color-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-lg);
}

/* Current Chapter Info inline in controls */
.current-chapter-inline {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  min-width: 0;
  max-width: 200px;
}

.chapter-inline-title {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
  line-height: 1.2;
}

.chapter-inline-time {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.6);
  font-family: var(--font-mono);
  white-space: nowrap;
}

/* Chapter List Panel - bounded, opaque overlay above the player. */
.chapter-list-panel::backdrop {
  background: rgba(0, 0, 0, 0.32);
}

.chapter-list-panel {
  margin: 0;
  padding: 0;
  color: inherit;
  top: auto;
  left: auto;
  background: var(--background-card);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: var(--radius-lg);  /* 12px */
  box-shadow: var(--shadow-2xl), 0 0 40px rgba(0, 0, 0, 0.5);
  max-height: calc(100dvh - 80px - var(--spacing-4) - env(safe-area-inset-top, 0px) - env(safe-area-inset-bottom, 0px));
  overflow-y: auto;
  overscroll-behavior-y: contain;
  position: fixed;
  bottom: 80px;  /* Above video controls */
  right: max(var(--spacing-4), env(safe-area-inset-right, 0px));
  width: 44rem;
  max-width: calc(100% - max(var(--spacing-4), env(safe-area-inset-left, 0px)) - max(var(--spacing-4), env(safe-area-inset-right, 0px)));
  /* Animation now handled by Vue transition (see .slide-panel-* classes) */

  @include m.respond-below('md') {  // < 768px (mobile)
    top: max(var(--spacing-2), env(safe-area-inset-top, 0px));
    bottom: max(var(--spacing-2), env(safe-area-inset-bottom, 0px));
    right: max(var(--spacing-2), env(safe-area-inset-right, 0px));
    left: max(var(--spacing-2), env(safe-area-inset-left, 0px));
    width: auto;
    height: fit-content;
    max-height: calc(100dvh - max(var(--spacing-2), env(safe-area-inset-top, 0px)) - max(var(--spacing-2), env(safe-area-inset-bottom, 0px)));
    max-width: none;  /* Override desktop constraint */
  }
}

/* Vue Transition for Chapter Panel */
.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: all var(--duration-300) var(--ease-out);
}

@media (prefers-reduced-motion: reduce) {
  .slide-panel-enter-active,
  .slide-panel-leave-active {
    transition: none;
  }
}

.slide-panel-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.slide-panel-enter-to {
  opacity: 1;
  transform: translateX(0);
}

.slide-panel-leave-from {
  opacity: 1;
  transform: translateX(0);
}

.slide-panel-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

/* Custom scrollbar for chapter list with glass effect */
.chapter-list-panel::-webkit-scrollbar {
  width: 8px;
}

.chapter-list-panel::-webkit-scrollbar-track {
  background: rgba(var(--background-darker-rgb), 0.3);
  border-radius: var(--radius-full);
}

.chapter-list-panel::-webkit-scrollbar-thumb {
  background: rgba(var(--primary-color-rgb), 0.5);
  border-radius: var(--radius-full);
  transition: var(--transition-all);
}

.chapter-list-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(var(--primary-color-rgb), 0.7);
}

.chapter-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-4);  /* 16px */
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  position: sticky;
  top: 0;
  /* Glassmorphism sticky header */
  background: rgba(var(--background-card-rgb), 0.95);
  z-index: 10;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.chapter-list-header h3 {
  margin: 0;
  font-size: var(--text-lg);  /* 18px */
  font-weight: var(--font-semibold);  /* 600 */
  color: var(--text-primary);
  line-height: var(--leading-tight);

  @include m.respond-below('sm') {
    font-size: var(--text-base);
  }
}

.close-btn {
  background: none;
  border: none;
  font-size: var(--text-2xl);  /* 24px */
  color: var(--text-secondary);
  cursor: pointer;
  padding: var(--spacing-1);  /* 4px */
  line-height: 1;
  transition: var(--transition-colors);
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
}

.close-btn:hover {
  color: var(--text-primary);
  background: var(--background-hover);
}

.close-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.chapter-list {
  padding: var(--spacing-2);  /* 8px */
}

.chapter-item {
  // Use reusable list-item-interactive mixin from design system
  @include m.list-item-interactive;

  & {  // ✅ Wrap declaration to avoid mixed-decls warning
    width: 100%;
    appearance: none;
    border: 0;
    border-left: 3px solid transparent;  /* Default border for active state */
    color: inherit;
    font: inherit;
    text-align: left;
  }
}

.chapter-item.active {
  // Use reusable list-item-active mixin with play icon indicator
  @include m.list-item-active(3px, 4px);
  @include m.list-item-active-indicator('▶', 20px, 25px);

  & {  // ✅ Wrap declaration to avoid mixed-decls warning
    color: white;
  }
}


.chapter-thumbnail,
.chapter-icon,
.chapter-placeholder {
  // Use reusable list-item-thumbnail mixin from design system
  @include m.list-item-thumbnail(80px, 96px);

  @include m.respond-below('sm') {
    width: 50px;
    min-width: 50px;
    height: 50px;
    border-radius: var(--radius-sm);
  }
}

.chapter-placeholder {
  font-size: var(--text-2xl);  /* 24px */
  color: var(--text-secondary);

  @include m.respond-below('sm') {
    font-size: var(--text-lg);
  }
}


/* Scroll Indicators - Top and Bottom Fade Gradients */
.chapter-list-panel::before,
.chapter-list-panel::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  height: 20px;
  pointer-events: none;
  z-index: 5;
  opacity: 0;
  transition: var(--transition-opacity);
}

.chapter-list-panel::before {
  top: 0;
  background: linear-gradient(to bottom, rgba(var(--background-card-rgb), 0.95), transparent);
}

.chapter-list-panel::after {
  bottom: 0;
  background: linear-gradient(to top, rgba(var(--background-card-rgb), 0.95), transparent);
}

/* Show scroll indicators when scrolled */
.chapter-list-panel.scrolled-top::before {
  opacity: 1;
}

.chapter-list-panel.scrolled-bottom::after {
  opacity: 1;
}

/* ============================================================================
   CUSTOM VIDEO CONTROLS - Touch-Optimized (Mobile-First)
   Apple HIG + Material Design Touch Target Standards
   ============================================================================ */

.video-controls-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.9) 0%, rgba(0, 0, 0, 0.7) 60%, transparent 100%);
  padding: var(--spacing-4);  /* 16px */
  transition: opacity var(--duration-300) var(--ease-out);
  z-index: 10;
}

/* Progress Bar Container */
.progress-container {
  margin-bottom: var(--spacing-3);  /* 12px */
  padding: var(--spacing-2) 0;  /* Extended tap area */
  cursor: pointer;
  min-height: 44px;
  display: flex;
  align-items: center;
}

.progress-bar-track {
  position: relative;
  height: 8px;  /* Desktop height */
  background: rgba(255, 255, 255, 0.3);
  border-radius: var(--radius-full);
  overflow: visible;
  transition: height var(--duration-200) var(--ease-out);

  @include m.respond-below('md') {  // < 768px (mobile)
    height: 12px;  /* Thicker on mobile */
  }
}

.progress-container:hover .progress-bar-track {
  height: 12px;  /* Thicker on hover */
}

.progress-container:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 3px;
}

/* Chapter Markers - Integrated into Progress Bar */
.chapter-markers {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  border-radius: var(--radius-full);
  overflow: hidden;
  z-index: 1;
}

.chapter-marker {
  position: absolute;
  top: 0;
  height: 100%;
  opacity: 0.5;
  cursor: pointer;
  transition: all var(--duration-200) var(--ease-out);
  border-right: 2px solid rgba(0, 0, 0, 0.4);

  &:hover {
    opacity: 0.8;
    transform: scaleY(1.3);
    z-index: 2;
    box-shadow: 0 0 8px currentColor;
  }

  &:active {
    opacity: 1;
    transform: scaleY(1.5);
  }
}

.progress-bar-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: var(--primary-color);
  border-radius: var(--radius-full);
  transition: width var(--duration-150) var(--ease-out);
  z-index: 3; /* Above chapter markers */
}

.progress-bar-thumb {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 16px;
  height: 16px;
  background: white;
  border-radius: var(--radius-full);
  box-shadow: var(--shadow-md);
  opacity: 0;
  transition: all var(--duration-200) var(--ease-out);
  z-index: 4; /* Above fill and markers */

  @include m.respond-below('md') {  // < 768px (mobile)
    width: 24px;  /* Larger thumb for touch */
    height: 24px;
    border: 2px solid white;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
  }
}

.progress-container:hover .progress-bar-thumb,
.progress-bar-thumb:active {
  opacity: 1;
}

/* Control Buttons Layout */
.controls-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--spacing-3);  /* 12px */

  @include m.respond-below('md') {  // < 768px (mobile)
    gap: var(--spacing-2);  /* Reduce gap on mobile to prevent overflow */
  }
}

.controls-left,
.controls-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);  /* 8px */

  @include m.respond-below('md') {  // < 768px (mobile)
    gap: var(--spacing-2);  /* Keep consistent spacing */
  }
}

/* Control Buttons - Base Styles */
.control-button {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-full);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: all var(--duration-200) var(--ease-out);

  width: 44px;
  height: 44px;
}

.control-button:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.4);
  transform: scale(1.05);
}

.control-button:active {
  transform: scale(0.95);
}

.control-button:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* Play/Pause Button - Primary Control (Larger) */
.play-pause-button {
  background: linear-gradient(135deg, var(--primary-color), var(--primary-color-dark));
  border-color: var(--primary-color);
  box-shadow: var(--shadow-md);

  /* Desktop: 48px (primary control) */
  width: 48px;
  height: 48px;
}

.play-pause-button:hover {
  background: linear-gradient(135deg, var(--primary-color-light), var(--primary-color));
  box-shadow: var(--shadow-lg), 0 0 20px rgba(var(--primary-color-rgb), 0.4);
}

/* Chapter Navigation Buttons */
.chapter-nav-button {
  /* Same size as standard controls */
  opacity: 0.9;

  // Hide prev/next on portrait mobile - chapters list below video is used instead
  @media (max-width: 767px) and (orientation: portrait) {
    display: none;
  }
}

.chapter-nav-button:hover:not(:disabled) {
  opacity: 1;
  background: rgba(255, 255, 255, 0.25);
}

.chapter-nav-button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  pointer-events: none;
}

/* Chapters List Toggle Button */
.chapters-button {
  position: relative;
  gap: var(--spacing-1);  /* 4px between icon and count */
  padding: 0 var(--spacing-2);  /* Horizontal padding for count */
  width: auto;  /* Auto width to fit content */
  min-width: 48px;  /* Minimum touch target */
}

.chapters-button.active {
  background: linear-gradient(135deg, var(--primary-color), var(--primary-color-dark));
  border-color: var(--primary-color);
  box-shadow: var(--shadow-md), 0 0 16px rgba(var(--primary-color-rgb), 0.3);
}

.theater-button.active {
  background: linear-gradient(135deg, var(--primary-color), var(--primary-color-dark));
  border-color: var(--primary-color);
  box-shadow: var(--shadow-md), 0 0 16px rgba(var(--primary-color-rgb), 0.3);
}

.theater-button {
  @include m.respond-below('md') {
    display: none;
  }
}

.chapters-button .chapter-count {
  font-size: var(--text-xs);  /* 12px */
  font-weight: var(--font-bold);  /* 700 */
  margin-left: 2px;

  @include m.respond-below('md') {  // < 768px (mobile)
    font-size: var(--text-sm);  /* 14px on mobile */
  }
}

/* Control Icons */
.control-icon {
  width: 24px;
  height: 24px;

}

.play-pause-button .control-icon {
  width: 28px;
  height: 28px;

}

/* Time Display */
.time-display {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);  /* 4px */
  font-size: var(--text-sm);  /* 14px */
  color: white;
  font-family: var(--font-mono);
  font-weight: var(--font-medium);  /* 500 */
  white-space: nowrap;

  @include m.respond-below('sm') {  // < 640px (small mobile)
    font-size: var(--text-xs);  /* 12px - Smaller on very small screens */
  }
}

.time-separator {
  opacity: 0.7;
}

/* Adapt to the actual stage width, including height-capped landscape players. */
@mixin compact-controls {
  .control-icon { width: 20px; height: 20px; }
  .play-pause-button .control-icon { width: 24px; height: 24px; }
  .current-chapter-inline { display: none; }
  .video-controls-overlay {
    padding: var(--spacing-2);  /* Reduce all padding to prevent overflow */
    padding-bottom: env(safe-area-inset-bottom, var(--spacing-2));  /* Account for safe area */
  }

  .progress-container {
    /* Extended vertical tap area for easier scrubbing */
    padding: var(--spacing-2) 0;  /* Reduce vertical padding */
    margin-bottom: var(--spacing-2);  /* Reduce spacing */
  }

  // Never hide an action to make an overfull row appear to fit.
  .controls-bottom {
    flex-wrap: wrap;
    gap: var(--spacing-1);
  }

  .controls-left,
  .controls-right {
    gap: var(--spacing-1);
    flex-shrink: 0;
  }

  // A long recording needs two compact clock lines, not an overflowing label.
  .time-display {
    flex-direction: column;
    align-items: flex-start;
    gap: 0;
    line-height: var(--leading-tight);
  }

  .time-separator {
    display: none;
  }

  // Keep all capabilities at 320px while retaining 44px targets.
  .control-button,
  .chapters-button,
  .play-pause-button {
    width: 44px;
    min-width: 44px;
    height: 44px;
    flex-shrink: 0;
  }

  .chapters-button { padding: 0; }
}

@container video-stage (max-width: 767px) {
  @include compact-controls;
}

// Short landscape needs the available width, not a miniature stage derived
// from the depleted height budget. Only use a one-row minimum when it fits;
// the rem threshold preserves room at enlarged text sizes.
@media (max-height: 480px) and (orientation: landscape) {
  .video-wrapper { width: 100%; }
  @include compact-controls;

  @container player (min-width: 30rem) {
    .video-wrapper {
      min-height: calc(44px + max(44px, 2 * var(--text-sm) * var(--leading-tight)) + var(--spacing-4) + env(safe-area-inset-bottom, 0px));
    }
  }
}

/* Very Small Screens */
@include m.respond-below('xs') {  // < 375px (iPhone SE)
  .controls-bottom {
    gap: var(--spacing-2);  /* 8px - Tighter spacing */
  }

  .controls-left,
  .controls-right {
    gap: var(--spacing-1);
  }

  .control-button {
    width: 44px;  /* Minimum touch target */
    height: 44px;
  }
}

/* ============================================================================
   MOBILE RESPONSIVE - Chapter Controls (Existing)
   ============================================================================ */

/* Mobile Responsive - Use SCSS mixins for breakpoints */
@include m.respond-below('md') {  // < 768px
  .current-chapter-inline {
    display: none;
  }

  .chapter-item {
    text-align: left;
  }

  .chapter-info {
    width: auto;
    flex: 1;
  }

  .chapter-title {
    text-align: left;
  }

}

/* Very small screens */
@include m.respond-below('xs') {  // < 375px
  .video-controls-extension {
    padding: var(--spacing-2);  /* 8px */
  }

  .chapter-controls {
    flex-direction: column;
    gap: var(--spacing-2);  /* 8px */
  }

  .control-btn {
    width: 100%;
    padding: var(--spacing-3);  /* 12px */
  }

  .chapter-list-header {
    padding: var(--spacing-3);  /* 12px */
  }

  .chapter-item {
    padding: var(--spacing-3);  /* 12px */
  }

  .chapter-thumbnail,
  .chapter-icon,
  .chapter-placeholder {
    width: 60px;
    height: 60px;
  }
}
</style>
