<template>
  <div class="video-player-container">
    <div class="video-wrapper" ref="videoWrapper">
      <video 
        ref="videoElement"
        :src="decodedVideoSrc"
        @loadedmetadata="onVideoLoaded"
        @timeupdate="onTimeUpdate"
        @loadstart="onLoadStart"
        @canplay="onCanPlay"
        @error="onVideoError"
        @abort="onVideoError"
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
      
      <!-- Custom Chapter Navigation Overlay -->
      <div v-if="chapters.length > 0 && showChapterUI" class="chapter-overlay">
        <div class="chapter-navigation">
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
              <div class="chapter-info">
                <div class="chapter-title">{{ chapter.title }}</div>
                <div class="chapter-time">{{ formatTime(chapter.startTime) }}</div>
                <div class="chapter-duration" v-if="chapter.duration">
                  {{ formatDuration(chapter.duration) }}
                </div>
              </div>
              <div class="chapter-game-icon" v-if="chapter.gameIcon">
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
            </div>
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
    </div>

    <!-- Video Controls Extension -->
    <div class="video-controls-extension">
      <div class="chapter-controls">
        <button 
          @click="toggleChapterUI" 
          class="chapter-toggle-btn"
          :class="{ 'active': showChapterUI }"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3 4h18v2H3V4zm0 7h18v2H3v-2zm0 7h18v2H3v-2z"/>
          </svg>
          Chapters ({{ chapters.length }})
        </button>
        
        <button @click="previousChapter" :disabled="currentChapterIndex <= 0">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/>
          </svg>
          Previous
        </button>
        
        <button @click="nextChapter" :disabled="currentChapterIndex >= chapters.length - 1">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M6 18l8.5-6L6 6v12zm8.5-6l8.5 6V6z"/>
          </svg>
          Next
        </button>
      </div>

      <div class="current-chapter-info" v-if="currentChapter">
        <div class="current-chapter-title">{{ currentChapter.title }}</div>
        <div class="current-chapter-progress">
          {{ formatTime(currentTime - currentChapter.startTime) }} / {{ formatDuration(currentChapter.duration) }}
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="loading-overlay">
      <div class="spinner"></div>
      <div>Loading video...</div>
    </div>

    <!-- Error State -->
    <div v-if="error" class="error-overlay">
      <div class="error-icon">⚠️</div>
      <div class="error-message">{{ error }}</div>
      <button @click="retryLoad" class="retry-btn">Retry</button>
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
    // For now, just return 0 as we'd need the stream start time to calculate offset
    return 0
  }
  
  // Handle HH:MM:SS.mmm or MM:SS format
  const parts = timeString.split(':')
  if (parts.length === 2) {
    // MM:SS format
    const [minutes, seconds] = parts
    return parseInt(minutes) * 60 + parseFloat(seconds)
  } else if (parts.length === 3) {
    // HH:MM:SS.mmm format
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
    
    // Look for timestamp line (e.g., "00:00:00.000 --> 00:05:30.000")
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

const decodedVideoSrc = computed(() => {
  if (!props.videoSrc) return ''
  
  try {
    // URL decode the video source to handle special characters
    const decoded = decodeURIComponent(props.videoSrc)

    return decoded
  } catch (error) {
    console.error('Error decoding video src:', error)
    return props.videoSrc
  }
})
</script>

<style scoped>
.video-player-container {
  position: relative;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  width: 100%;
  max-width: 100%;
}

.video-wrapper {
  position: relative;
  width: 100%;
}

.video-element {
  width: 100%;
  height: auto;
  max-height: 70vh;
  display: block;
}

/* Chapter Overlay */
.chapter-overlay {
  position: absolute;
  top: 0;
  right: 0;
  width: 300px;
  height: 100%;
  background: linear-gradient(to left, rgba(0, 0, 0, 0.9), transparent);
  padding: 20px 20px 20px 40px;
  overflow-y: auto;
  z-index: 10;
  transition: transform 0.3s ease;
}

.chapter-navigation {
  height: 100%;
}

.chapter-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chapter-item {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 2px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.chapter-item:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: translateX(-4px);
  border-color: rgba(255, 255, 255, 0.3);
  box-shadow: 0 4px 8px rgba(0,0,0,0.3);
}

.chapter-item.active {
  border-color: #9146ff;
  background: rgba(145, 70, 255, 0.2);
  box-shadow: 0 4px 12px rgba(145, 70, 255, 0.3);
}

.chapter-thumbnail {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
}

.chapter-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chapter-info {
  flex: 1;
  min-width: 0;
}

.chapter-title {
  font-weight: 600;
  color: white;
  font-size: 14px;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chapter-time {
  font-size: 12px;
  color: #ccc;
  font-family: monospace;
}

.chapter-duration {
  font-size: 11px;
  color: #999;
}

.chapter-game-icon {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
}

.chapter-game-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chapter-game-icon .category-icon {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: #9146ff;
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
  opacity: 0.7;
}

.chapter-segment:hover {
  height: 8px;
  opacity: 1;
}

/* Video Controls Extension */
.video-controls-extension {
  background: linear-gradient(to bottom, #1a1a1a, #2d2d2d);
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 2px solid #444;
  box-shadow: 0 -4px 8px rgba(0,0,0,0.3);
}

.chapter-controls {
  display: flex;
  gap: 8px;
  align-items: center;
}

.chapter-toggle-btn {
  background: #333;
  border: none;
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: background 0.2s ease;
}

.chapter-toggle-btn:hover {
  background: #555;
}

.chapter-toggle-btn.active {
  background: #9146ff;
}

.chapter-controls button {
  background: #333;
  border: none;
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  transition: background 0.2s ease;
}

.chapter-controls button:hover:not(:disabled) {
  background: #555;
}

.chapter-controls button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.current-chapter-info {
  text-align: right;
  color: white;
}

.current-chapter-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 2px;
}

.current-chapter-progress {
  font-size: 12px;
  color: #ccc;
  font-family: monospace;
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
  border-top-color: #9146ff;
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
  background: #9146ff;
  border: none;
  color: white;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
}

.retry-btn:hover {
  background: #7c3aed;
}

/* Mobile Responsive */
@media (max-width: 768px) {
  .chapter-overlay {
    width: 100%;
    height: auto;
    position: static;
    background: rgba(0, 0, 0, 0.9);
    padding: 16px;
  }

  .video-controls-extension {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }

  .chapter-controls {
    justify-content: center;
  }

  .current-chapter-info {
    text-align: center;
  }

  .chapter-item {
    flex-direction: column;
    text-align: center;
  }

  .chapter-progress-bar {
    height: 6px;
  }
}

/* Hide chapter overlay by default on mobile */
@media (max-width: 768px) {
  .chapter-overlay {
    transform: translateY(100%);
  }
  
  .chapter-overlay.show {
    transform: translateY(0);
  }
}
</style>
