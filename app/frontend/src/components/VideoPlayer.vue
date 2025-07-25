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
        :class="{ 'fullscreen': isFullscreen }"
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
        
        <button 
          @click="toggleFullscreen"
          class="control-btn"
        >
          {{ isFullscreen ? '🪟' : '⛶' }} {{ isFullscreen ? 'Exit' : 'Fullscreen' }}
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
const isFullscreen = ref(false)

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

// Fullscreen handling
const toggleFullscreen = () => {
  if (!videoWrapper.value) return
  
  if (!document.fullscreenElement) {
    videoWrapper.value.requestFullscreen()
    isFullscreen.value = true
  } else {
    document.exitFullscreen()
    isFullscreen.value = false
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
        chapters.value = chaptersData.map((ch: any) => ({
          title: ch.category_name || ch.title || 'Stream Segment',
          startTime: ch.start_time || 0,
          duration: ch.duration || 60,
          gameIcon: getCategoryImage(ch.category_name)
        }))
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
  return apiChapters.map((chapter, index) => ({
    title: chapter.title || `Chapter ${index + 1}`,
    startTime: parseTimeStringToSeconds(chapter.start_time),
    duration: 60, // Default duration, can be calculated between chapters
    gameIcon: undefined
  }))
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
    case 'f':
    case 'F':
      if (!event.ctrlKey && !event.metaKey) {
        event.preventDefault()
        toggleFullscreen()
      }
      break
  }
}

// Fullscreen change handler
const onFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement
}

onMounted(() => {
  loadChapters()
  document.addEventListener('keydown', onKeyDown)
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeyDown)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})

// Watch for changes in chapters prop
watch(() => props.chapters, (newChapters) => {
  if (newChapters && newChapters.length > 0) {
    chapters.value = convertApiChaptersToInternal(newChapters)
  }
}, { immediate: true })
</script>

<style scoped>
.video-player-container {
  position: relative;
  background: var(--background-darker);
  border-radius: var(--border-radius);
  overflow: hidden;
  width: 100%;
  max-width: 100%;
}

.video-wrapper {
  position: relative;
  width: 100%;
  background: #000;
}

.video-element {
  width: 100%;
  height: auto;
  max-height: 70vh;
  display: block;
}

.video-element.fullscreen {
  max-height: 100vh;
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
}

.chapter-segment {
  height: 100%;
  cursor: pointer;
  transition: height 0.2s ease;
  opacity: 0.8;
}

.chapter-segment:hover {
  height: 8px;
  opacity: 1;
}

/* Loading and Error States */
.loading-overlay,
.error-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: white;
  z-index: 20;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(255, 255, 255, 0.3);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-message {
  margin-bottom: 16px;
  text-align: center;
  max-width: 300px;
}

.retry-btn {
  background: var(--primary-color);
  border: none;
  color: white;
  padding: 12px 24px;
  border-radius: var(--border-radius);
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.retry-btn:hover {
  background: var(--primary-color-hover);
  transform: translateY(-1px);
}

/* Video Controls Extension */
.video-controls-extension {
  background: var(--background-card);
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid var(--border-color);
  gap: 16px;
}

.chapter-controls {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.control-btn {
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 8px 16px;
  border-radius: var(--border-radius);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
  font-size: 0.9rem;
  white-space: nowrap;
}

.control-btn:hover:not(:disabled) {
  background: var(--background-dark);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.control-btn.active {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: white;
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
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.current-chapter-progress {
  font-size: 0.8rem;
  color: var(--text-secondary);
  font-family: monospace;
}

/* Chapter List Panel */
.chapter-list-panel {
  background: var(--background-card);
  border-top: 1px solid var(--border-color);
  max-height: 400px;
  overflow-y: auto;
}

.chapter-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  background: var(--background-card);
  z-index: 10;
}

.chapter-list-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text-primary);
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  line-height: 1;
}

.close-btn:hover {
  color: var(--text-primary);
}

.chapter-list {
  padding: 8px;
}

.chapter-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s;
  border-radius: var(--border-radius);
  border: 1px solid transparent;
}

.chapter-item:hover {
  background: var(--background-darker);
  border-color: var(--border-color);
}

.chapter-item.active {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: white;
}

.chapter-item.active .chapter-time,
.chapter-item.active .chapter-duration {
  color: rgba(255, 255, 255, 0.8);
}

.chapter-thumbnail,
.chapter-icon,
.chapter-placeholder {
  width: 60px;
  height: 60px;
  border-radius: var(--border-radius);
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--background-darker);
}

.chapter-thumbnail img,
.chapter-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chapter-placeholder {
  font-size: 1.5rem;
  color: var(--text-secondary);
}

.chapter-info {
  flex: 1;
  min-width: 0;
}

.chapter-title {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 1rem;
  margin-bottom: 4px;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.chapter-time {
  font-size: 0.9rem;
  color: var(--text-secondary);
  font-family: monospace;
  font-weight: 500;
  margin-bottom: 2px;
}

.chapter-duration {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

/* Mobile Responsive */
@media (max-width: 768px) {
  .video-controls-extension {
    flex-direction: column;
    gap: 12px;
    padding: 12px;
  }

  .chapter-controls {
    justify-content: center;
    width: 100%;
  }

  .control-btn {
    flex: 1;
    justify-content: center;
    padding: 10px 8px;
    font-size: 0.8rem;
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
    padding: 16px;
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
@media (max-width: 480px) {
  .video-controls-extension {
    padding: 8px;
  }

  .chapter-controls {
    flex-direction: column;
    gap: 6px;
  }

  .control-btn {
    width: 100%;
    padding: 12px;
  }

  .chapter-list-header {
    padding: 12px;
  }

  .chapter-item {
    padding: 12px;
  }

  .chapter-thumbnail,
  .chapter-icon,
  .chapter-placeholder {
    width: 60px;
    height: 60px;
  }
}
</style>
