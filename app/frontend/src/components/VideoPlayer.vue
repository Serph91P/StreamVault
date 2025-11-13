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
        controls
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

// Category images composable
const { getCategoryImage } = useCategoryImages()

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

// Event handlers
const onVideoLoaded = () => {
  if (videoElement.value) {
    videoDuration.value = videoElement.value.duration
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
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeyDown)
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
