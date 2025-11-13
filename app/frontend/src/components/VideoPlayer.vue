<template>
  <div class="video-player-container">
    <!-- Video Element -->
    <div class="video-wrapper" ref="videoWrapper">
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
        @click="toggleControls"
        preload="metadata"
        class="video-element"
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
        @touchstart="onControlsTouch"
      >
        <!-- Progress Bar -->
        <div class="progress-container" @click="seekVideo">
          <div class="progress-bar-track">
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
      
      <!-- Chapter Progress Bar -->
      <div v-if="chapters.length > 0" class="chapter-progress-bar">
        <div 
          v-for="(chapter, index) in chapters" 
          :key="index"
          class="chapter-segment"
          :style="{ 
            width: `${(chapter.duration / videoDuration) * 100}%`,
            backgroundColor: getChapterColor(chapter.title)
          }"
          :title="`${chapter.title} - ${formatTime(chapter.startTime)}`"
          @click="seekToChapter(chapter.startTime)"
        ></div>
      </div>
      
      <!-- Loading State -->
      <div v-if="isLoading" class="loading-overlay">
        <div class="spinner"></div>
        <p>Loading video...</p>
      </div>

      <!-- Error State -->
      <div v-if="error" class="error-overlay">
        <div class="error-icon">⚠️</div>
        <div class="error-message">{{ error }}</div>
        <button @click="retryLoad" class="retry-btn">🔄 Retry</button>
      </div>
    </div>

    <!-- Video Controls Extension -->
    <div class="video-controls-extension">
      <!-- Chapter Controls -->
      <div class="chapter-controls">
        <button 
          v-if="chapters.length > 0"
          @click="toggleChapterUI" 
          class="control-btn"
          :class="{ 'active': showChapterUI }"
        >
          📋 Chapters ({{ chapters.length }})
        </button>
        
        <button 
          v-if="chapters.length > 0"
          @click="previousChapter" 
          :disabled="currentChapterIndex <= 0"
          class="control-btn"
        >
          ⏮️ Previous
        </button>
        
        <button 
          v-if="chapters.length > 0"
          @click="nextChapter" 
          :disabled="currentChapterIndex >= chapters.length - 1"
          class="control-btn"
        >
          ⏭️ Next
        </button>
      </div>

      <!-- Current Chapter Info -->
      <div class="current-chapter-info" v-if="currentChapter">
        <div class="current-chapter-title">{{ currentChapter.title }}</div>
        <div class="current-chapter-progress">
          {{ formatTime(currentTime - currentChapter.startTime) }} / {{ formatDuration(currentChapter.duration) }}
        </div>
      </div>
    </div>

    <!-- Chapter List (Mobile-friendly) -->
    <div v-if="showChapterUI && chapters.length > 0" class="chapter-list-panel">
      <div class="chapter-list-header">
        <h3>📋 Chapters</h3>
        <button @click="toggleChapterUI" class="close-btn">×</button>
      </div>
      <div class="chapter-list">
        <div 
          v-for="(chapter, index) in chapters" 
          :key="index"
          class="chapter-item"
          :class="{ 'active': currentChapterIndex === index }"
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
            🎬
          </div>
          
          <div class="chapter-info">
            <div class="chapter-title">{{ chapter.title }}</div>
            <div class="chapter-time">{{ formatTime(chapter.startTime) }}</div>
            <div class="chapter-duration" v-if="chapter.duration">
              {{ formatDuration(chapter.duration) }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useCategoryImages } from '@/composables/useCategoryImages'

interface Chapter {
  title: string
  startTime: number // in seconds
  duration: number // in seconds
  thumbnail?: string
  gameIcon?: string
}

interface Props {
  videoSrc: string
  streamId?: number
  chaptersUrl?: string // URL to WebVTT chapter file
  autoChapters?: boolean // Auto-generate chapters from category changes
  chapters?: Array<{
    start_time: string
    title: string
    type: string
  }> // Pre-loaded chapters from API
  streamTitle?: string
}

const props = withDefaults(defineProps<Props>(), {
  autoChapters: true
})

const emit = defineEmits<{
  'chapter-change': [chapter: Chapter, index: number]
  'video-ready': [duration: number]
  'time-update': [currentTime: number]
}>()

const videoElement = ref<HTMLVideoElement>()
const videoWrapper = ref<HTMLDivElement>()
const isLoading = ref(true)
const error = ref<string>('')
const currentTime = ref(0)
const videoDuration = ref(0)
const showChapterUI = ref(false)
const chapters = ref<Chapter[]>([])

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
  for (let i = chapters.value.length - 1; i >= 0; i--) {
    if (currentTime.value >= chapters.value[i].startTime) {
      return i
    }
  }
  return 0
})

const currentChapter = computed(() => {
  return chapters.value[currentChapterIndex.value] || null
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

const toggleControls = () => {
  showControls.value = !showControls.value
  resetControlsTimeout()
}

const onControlsTouch = () => {
  showControls.value = true
  resetControlsTimeout()
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
  if (videoElement.value) {
    videoDuration.value = videoElement.value.duration
    volume.value = videoElement.value.volume
    isMuted.value = videoElement.value.muted
    emit('video-ready', videoDuration.value)
  }
}

const onTimeUpdate = () => {
  if (videoElement.value) {
    currentTime.value = videoElement.value.currentTime
    emit('time-update', currentTime.value)
  }
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

const retryLoad = () => {
  if (videoElement.value) {
    videoElement.value.load()
  }
}

// Chapter navigation
const seekToChapter = (startTime: number) => {
  if (videoElement.value) {
    videoElement.value.currentTime = startTime
  }
}

const previousChapter = () => {
  if (currentChapterIndex.value > 0) {
    seekToChapter(chapters.value[currentChapterIndex.value - 1].startTime)
  }
}

const nextChapter = () => {
  if (currentChapterIndex.value < chapters.value.length - 1) {
    seekToChapter(chapters.value[currentChapterIndex.value + 1].startTime)
  }
}

const toggleChapterUI = () => {
  showChapterUI.value = !showChapterUI.value
}

// Chapter loading
const loadChapters = async () => {
  // First, check if we have pre-loaded chapters from props
  if (props.chapters && props.chapters.length > 0) {
    chapters.value = convertApiChaptersToInternal(props.chapters)
    return
  }

  if (props.streamId && props.autoChapters) {
    try {
      // Fetch chapters from StreamVault API
      const response = await fetch(`/api/streams/${props.streamId}/chapters`)
      if (response.ok) {
        const chaptersData = await response.json()
        const converted = chaptersData.map((ch: any) => ({
          title: ch.category_name || ch.title || 'Stream Segment',
          startTime: ch.start_time || 0,
          duration: ch.duration || 60,
          gameIcon: getCategoryImage(ch.category_name)
        }))
        
        // Deduplicate by startTime and title
        chapters.value = converted.filter((chapter: any, index: number, self: any[]) => 
          index === self.findIndex((c: any) => 
            c.startTime === chapter.startTime && c.title === chapter.title
          )
        )
      }
    } catch (e) {
      console.warn('Failed to load auto-generated chapters:', e)
    }
  }

  // If we have a chapters URL, try to parse WebVTT chapters
  if (props.chaptersUrl) {
    try {
      const response = await fetch(props.chaptersUrl)
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
const convertApiChaptersToInternal = (apiChapters: Array<{start_time: string, title: string, type: string}>) => {
  // Convert chapters first
  const converted = apiChapters.map((chapter, index) => ({
    title: chapter.title || `Chapter ${index + 1}`,
    startTime: parseTimeStringToSeconds(chapter.start_time),
    duration: 60, // Default duration, can be calculated between chapters
    gameIcon: undefined
  }))
  
  // Deduplicate by startTime and title
  const unique = converted.filter((chapter, index, self) => 
    index === self.findIndex(c => 
      c.startTime === chapter.startTime && c.title === chapter.title
    )
  )
  
  return unique
}

// Parse time string to seconds
const parseTimeStringToSeconds = (timeString: string): number => {
  if (!timeString) return 0
  
  // Handle ISO datetime format
  if (timeString.includes('T')) {
    return 0
  }
  
  // Handle HH:MM:SS.mmm or MM:SS format
  const parts = timeString.split(':')
  if (parts.length === 2) {
    const [minutes, seconds] = parts
    return parseInt(minutes) * 60 + parseFloat(seconds)
  } else if (parts.length === 3) {
    const [hours, minutes, seconds] = parts
    return parseInt(hours) * 3600 + parseInt(minutes) * 60 + parseFloat(seconds)
  }
  
  return 0
}

const parseWebVTTChapters = (vttText: string) => {
  const lines = vttText.split('\n')
  const parsedChapters: Chapter[] = []
  
  let i = 0
  while (i < lines.length) {
    const line = lines[i].trim()
    
    // Look for timestamp line
    const timeMatch = line.match(/(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})/)
    if (timeMatch) {
      const startTime = parseVTTTime(timeMatch[1])
      const endTime = parseVTTTime(timeMatch[2])
      const duration = endTime - startTime
      
      // Next line should be the title
      i++
      const title = lines[i]?.trim() || 'Chapter'
      
      parsedChapters.push({
        title,
        startTime,
        duration
      })
    }
    i++
  }
  
  if (parsedChapters.length > 0) {
    chapters.value = parsedChapters
  }
}

const parseVTTTime = (timeStr: string): number => {
  const [hours, minutes, seconds] = timeStr.split(':')
  return parseInt(hours) * 3600 + parseInt(minutes) * 60 + parseFloat(seconds)
}

// Utility functions
const formatTime = (seconds: number): string => {
  const hrs = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  
  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

const formatDuration = (seconds: number): string => {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  
  if (mins > 60) {
    const hrs = Math.floor(mins / 60)
    const remainingMins = mins % 60
    return `${hrs}h ${remainingMins}m`
  }
  return `${mins}m ${secs}s`
}

const getChapterColor = (title: string): string => {
  // Generate consistent colors for different game categories
  let hash = 0
  for (let i = 0; i < title.length; i++) {
    hash = title.charCodeAt(i) + ((hash << 5) - hash)
  }
  
  const hue = Math.abs(hash % 360)
  return `hsl(${hue}, 70%, 60%)`
}

// Watch for chapter changes and emit events
watch(currentChapterIndex, (newIndex, oldIndex) => {
  if (newIndex !== oldIndex && chapters.value[newIndex]) {
    emit('chapter-change', chapters.value[newIndex], newIndex)
  }
})

// Keyboard shortcuts
const onKeyDown = (event: KeyboardEvent) => {
  if (!videoElement.value) return
  
  switch (event.key) {
    case 'ArrowLeft':
      if (event.ctrlKey || event.metaKey) {
        event.preventDefault()
        previousChapter()
      }
      break
    case 'ArrowRight':
      if (event.ctrlKey || event.metaKey) {
        event.preventDefault()
        nextChapter()
      }
      break
    case 'c':
    case 'C':
      if (!event.ctrlKey && !event.metaKey) {
        event.preventDefault()
        toggleChapterUI()
      }
      break
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
  if (newChapters && newChapters.length > 0) {
    chapters.value = convertApiChaptersToInternal(newChapters)
  }
}, { immediate: true })
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* ============================================================================
   VIDEO PLAYER - Modern Glassmorphism Design (PWA Mobile-First)
   Follows Complete Design Overhaul patterns
   ============================================================================ */

.video-player-container {
  position: relative;
  /* Glassmorphism card effect */
  background: rgba(var(--background-card-rgb), 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-xl);  /* 16px */
  overflow: hidden;
  width: 100%;
  max-width: 100%;
  box-shadow: var(--shadow-lg), 0 0 40px rgba(0, 0, 0, 0.1);
  transition: var(--transition-all);
  
  // Mobile: Remove glassmorphism effects for full-width video
  @include m.respond-below('md') {  // < 768px
    background: transparent;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    border: none;
    border-radius: 0;
    box-shadow: none;
  }
}

.video-player-container:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-xl), 0 0 60px rgba(var(--primary-color-rgb), 0.15);
  border-color: rgba(var(--primary-color-rgb), 0.2);
  
  // Mobile: No hover effects
  @include m.respond-below('md') {  // < 768px
    transform: none;
    box-shadow: none;
    border-color: transparent;
  }
}

.video-wrapper {
  position: relative;
  width: 100%;
  background: var(--background-darker);
  
  // Desktop: Constrained width with 16:9 aspect ratio
  @include m.respond-to('md') {  // >= 768px
    max-width: 1280px;
    margin: 0 auto;
    aspect-ratio: 16/9;
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
  height: auto;
  display: block;
  background: #000;
  object-fit: contain;
  
  // Desktop: Limit height
  @include m.respond-to('md') {  // >= 768px
    max-height: 70vh;
  }
  
  // Mobile Portrait: Full width with 16:9 ratio
  @include m.respond-below('md') {  // < 768px
    max-height: none;
  }
}

// Mobile Landscape: Immersive fullscreen mode
@media (max-width: 767px) and (orientation: landscape) {
  .video-wrapper {
    height: 100vh;
    width: auto;
    aspect-ratio: auto;
    margin: 0;
  }
  
  .video-element {
    height: 100%;
    width: 100%;
    max-height: 100vh;
  }
}

/* Chapter Progress Bar */
.chapter-progress-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 4px;
  display: flex;
  z-index: 5;
  /* Subtle glass effect for progress bar background */
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
}

.chapter-segment {
  height: 100%;
  cursor: pointer;
  transition: height var(--duration-200) var(--ease-out), opacity var(--duration-200);
  opacity: 0.8;
  /* Glass effect for chapter segments */
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
  border-right: 1px solid rgba(0, 0, 0, 0.3);
}

.chapter-segment:hover {
  height: 8px;
  opacity: 1;
  box-shadow: 0 0 8px currentColor;
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
  backdrop-filter: blur(4px);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: white;
  z-index: 20;
  gap: var(--spacing-4);  /* 16px */
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

/* Video Controls Extension - Glassmorphism Style */
.video-controls-extension {
  background: rgba(var(--background-card-rgb), 0.95);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  padding: var(--spacing-4);  /* 16px */
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  gap: var(--spacing-4);  /* 16px */
}

.chapter-controls {
  display: flex;
  gap: var(--spacing-2);  /* 8px */
  align-items: center;
  flex-wrap: wrap;
}

.control-btn {
  /* Glassmorphism button design */
  background: rgba(var(--background-darker-rgb), 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  padding: var(--spacing-2) var(--spacing-4);  /* 8px 16px */
  border-radius: var(--radius-lg);  /* 12px */
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--spacing-2);  /* 8px */
  transition: var(--transition-all);
  font-size: var(--text-sm);  /* 14px */
  font-weight: var(--font-medium);  /* 500 */
  white-space: nowrap;
  line-height: var(--leading-normal);
  min-height: 44px;  /* Touch target - PWA requirement */
  box-shadow: var(--shadow-sm);
}

.control-btn:hover:not(:disabled) {
  background: rgba(var(--background-darker-rgb), 0.9);
  border-color: rgba(var(--primary-color-rgb), 0.5);
  color: var(--primary-color);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md), 0 0 20px rgba(var(--primary-color-rgb), 0.2);
}

.control-btn:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
  box-shadow: var(--shadow-focus-primary);
}

.control-btn.active {
  background: linear-gradient(135deg, var(--primary-color), var(--primary-color-dark));
  border-color: var(--primary-color);
  color: white;
  box-shadow: var(--shadow-primary), 0 0 20px rgba(var(--primary-color-rgb), 0.4);
}

.control-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.current-chapter-info {
  text-align: right;
  color: var(--text-primary);
  min-width: 0;
}

.current-chapter-title {
  font-weight: var(--font-semibold);  /* 600 */
  font-size: var(--text-sm);  /* 14px */
  margin-bottom: var(--spacing-1);  /* 4px */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: var(--leading-tight);
}

.current-chapter-progress {
  font-size: var(--text-xs);  /* 12px */
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-weight: var(--font-medium);  /* 500 */
}

/* Chapter List Panel */
.chapter-list-panel {
  /* Glassmorphism panel design */
  background: rgba(var(--background-card-rgb), 0.95);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-top: 1px solid rgba(255, 255, 255, 0.15);
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.3);
  max-height: 400px;
  overflow-y: auto;
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
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  z-index: 10;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.chapter-list-header h3 {
  margin: 0;
  font-size: var(--text-lg);  /* 18px */
  font-weight: var(--font-semibold);  /* 600 */
  color: var(--text-primary);
  line-height: var(--leading-tight);
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
  display: flex;
  align-items: center;
  gap: var(--spacing-3);  /* 12px */
  padding: var(--spacing-3);  /* 12px */
  cursor: pointer;
  transition: var(--transition-all);
  border-radius: var(--radius-md);  /* 10px */
  border: 1px solid transparent;
  min-height: 44px;  /* Touch target - PWA requirement */
  /* Glassmorphism item design */
  background: rgba(var(--background-darker-rgb), 0.3);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.chapter-item:hover {
  background: rgba(var(--background-darker-rgb), 0.6);
  border-color: rgba(255, 255, 255, 0.15);
  transform: translateX(4px);
  box-shadow: var(--shadow-sm);
}

.chapter-item.active {
  background: linear-gradient(135deg, rgba(var(--primary-color-rgb), 0.9), rgba(var(--primary-color-rgb), 0.7));
  border-color: rgba(var(--primary-color-rgb), 0.8);
  color: white;
  box-shadow: var(--shadow-primary), 0 0 16px rgba(var(--primary-color-rgb), 0.3);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.chapter-item.active .chapter-time,
.chapter-item.active .chapter-duration {
  color: rgba(255, 255, 255, 0.9);
}

.chapter-thumbnail,
.chapter-icon,
.chapter-placeholder {
  width: 60px;
  height: 60px;
  border-radius: var(--radius-md);  /* 10px */
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--background-darker);
  box-shadow: var(--shadow-sm);
}

.chapter-thumbnail img,
.chapter-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chapter-placeholder {
  font-size: var(--text-2xl);  /* 24px */
  color: var(--text-secondary);
}

.chapter-info {
  flex: 1;
  min-width: 0;
}

.chapter-title {
  font-weight: var(--font-semibold);  /* 600 */
  color: var(--text-primary);
  font-size: var(--text-base);  /* 16px */
  margin-bottom: var(--spacing-1);  /* 4px */
  line-height: var(--leading-snug);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.chapter-time {
  font-size: var(--text-sm);  /* 14px */
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-weight: var(--font-medium);  /* 500 */
  margin-bottom: var(--spacing-0-5);  /* 2px */
}

.chapter-duration {
  font-size: var(--text-xs);  /* 12px */
  color: var(--text-secondary);
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
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  padding: var(--spacing-4);  /* 16px */
  transition: opacity var(--duration-300) var(--ease-out);
  z-index: 10;
}

/* Progress Bar Container */
.progress-container {
  margin-bottom: var(--spacing-3);  /* 12px */
  padding: var(--spacing-2) 0;  /* Extended tap area */
  cursor: pointer;
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

.progress-bar-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: var(--primary-color);
  border-radius: var(--radius-full);
  transition: width var(--duration-150) var(--ease-out);
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
    gap: var(--spacing-4);  /* 16px - More spacing on mobile */
  }
}

.controls-left,
.controls-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);  /* 8px */
  
  @include m.respond-below('md') {  // < 768px (mobile)
    gap: var(--spacing-3);  /* 12px */
  }
}

/* Control Buttons - Base Styles */
.control-button {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-full);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: all var(--duration-200) var(--ease-out);
  
  /* Desktop: 40px (standard size) */
  width: 40px;
  height: 40px;
  
  @include m.respond-below('md') {  // < 768px (mobile)
    /* Mobile: 48px (touch-friendly) */
    width: 48px;
    height: 48px;
    border-width: 2px;
  }
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
  
  @include m.respond-below('md') {  // < 768px (mobile)
    /* Mobile: 56px (extra large for primary action) */
    width: 56px;
    height: 56px;
  }
}

.play-pause-button:hover {
  background: linear-gradient(135deg, var(--primary-color-light), var(--primary-color));
  box-shadow: var(--shadow-lg), 0 0 20px rgba(var(--primary-color-rgb), 0.4);
}

/* Control Icons */
.control-icon {
  width: 24px;
  height: 24px;
  
  @include m.respond-below('md') {  // < 768px (mobile)
    width: 28px;  /* Larger icons on mobile */
    height: 28px;
  }
}

.play-pause-button .control-icon {
  width: 28px;
  height: 28px;
  
  @include m.respond-below('md') {  // < 768px (mobile)
    width: 32px;  /* Even larger for primary button */
    height: 32px;
  }
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

/* Mobile Optimizations */
@include m.respond-below('md') {  // < 768px
  .video-controls-overlay {
    padding: var(--spacing-3);  /* 12px */
  }
  
  .progress-container {
    /* Extended vertical tap area for easier scrubbing */
    padding: var(--spacing-4) 0;  /* 16px vertical */
  }
}

/* Very Small Screens */
@include m.respond-below('xs') {  // < 375px (iPhone SE)
  .controls-bottom {
    gap: var(--spacing-2);  /* 8px - Tighter spacing */
  }
  
  .controls-left,
  .controls-right {
    gap: var(--spacing-2);  /* 8px */
  }
  
  .control-button {
    width: 44px;  /* Minimum touch target */
    height: 44px;
  }
  
  .play-pause-button {
    width: 52px;  /* Slightly smaller but still prominent */
    height: 52px;
  }
}

/* ============================================================================
   MOBILE RESPONSIVE - Chapter Controls (Existing)
   ============================================================================ */

/* Mobile Responsive - Use SCSS mixins for breakpoints */
@include m.respond-below('md') {  // < 768px
  .video-controls-extension {
    flex-direction: column;
    gap: var(--spacing-3);  /* 12px */
    padding: var(--spacing-3);  /* 12px */
  }

  .chapter-controls {
    justify-content: center;
    width: 100%;
  }

  .control-btn {
    flex: 1;
    justify-content: center;
    padding: var(--spacing-2-5) var(--spacing-2);  /* 10px 8px */
    font-size: var(--text-xs);  /* 12px */
  }

  .current-chapter-info {
    text-align: center;
    width: 100%;
  }

  .current-chapter-title {
    white-space: normal;
    overflow: visible;
    text-overflow: unset;
  }

  .chapter-item {
    flex-direction: column;
    text-align: center;
    padding: var(--spacing-4);  /* 16px */
  }

  .chapter-thumbnail,
  .chapter-icon,
  .chapter-placeholder {
    width: 80px;
    height: 80px;
  }

  .chapter-info {
    width: 100%;
  }

  .chapter-title {
    text-align: center;
  }

  .chapter-list-panel {
    max-height: 300px;
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
