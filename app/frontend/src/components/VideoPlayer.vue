<template>
  <div class="video-player-container">
    <!-- Video Element -->
    <div class="video-wrapper" ref="videoWrapper" @mouseenter="onVideoHover" @mouseleave="onVideoLeave" @mousemove="onVideoMove">
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
        <!-- Progress Bar with Chapter Markers -->
        <div class="progress-container" @click="seekVideo">
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
                @click="previousChapter" 
                :disabled="currentChapterIndex <= 0"
                class="control-button chapter-nav-button"
                :aria-label="'Previous Chapter'"
                :title="`Previous: ${parsedChapters[currentChapterIndex - 1]?.title || 'None'}`"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" class="control-icon">
                  <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/>
                </svg>
              </button>
              
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
                @click="nextChapter" 
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
      
      <!-- Chapter List Panel (Overlay inside video) -->
      <transition name="slide-panel">
        <div 
          v-if="showChapterUI && parsedChapters.length > 0" 
          class="chapter-list-panel"
          ref="chapterListPanel"
          @scroll="handleChapterListScroll"
        >
        <div class="chapter-list-header">
          <h3>📋 Chapters</h3>
          <button @click="toggleChapterUI" class="close-btn">×</button>
        </div>
        <div class="chapter-list" ref="chapterList">
          <div 
            v-for="(chapter, index) in parsedChapters" 
            :key="index"
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
      </transition>
    </div>

    <!-- Video Controls Extension (below video) -->
    <div class="video-controls-extension" v-if="currentChapter">
      <!-- Current Chapter Info -->
      <div class="current-chapter-info">
        <div class="current-chapter-title">{{ currentChapter.title }}</div>
        <div class="current-chapter-progress">
          {{ formatTime(currentTime - currentChapter.startTime) }} / {{ formatDuration(currentChapter.duration) }}
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
const chapterListPanel = ref<HTMLDivElement>()
const chapterList = ref<HTMLDivElement>()
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

const _toggleControls = () => {
  showControls.value = !showControls.value
  resetControlsTimeout()
}

const onControlsTouch = () => {
  showControls.value = true
  resetControlsTimeout()
}

const onVideoHover = () => {
  showControls.value = true
  resetControlsTimeout()
}

const onVideoLeave = () => {
  if (isPlaying.value) {
    resetControlsTimeout()
  }
}

const onVideoMove = () => {
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
    
    // Recalculate chapter durations now that we have video duration
    if (parsedChapters.value.length > 0) {
      parsedChapters.value = calculateChapterDurations([...parsedChapters.value])
    }
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
    seekToChapter(parsedChapters.value[currentChapterIndex.value - 1].startTime)
  }
}

const nextChapter = () => {
  if (currentChapterIndex.value < parsedChapters.value.length - 1) {
    seekToChapter(parsedChapters.value[currentChapterIndex.value + 1].startTime)
  }
}

const toggleChapterUI = () => {
  showChapterUI.value = !showChapterUI.value
}

// Chapter loading
const loadChapters = async () => {
  // First, check if we have pre-loaded chapters from props
  if (props.chapters && props.chapters.length > 0) {
    parsedChapters.value = convertApiChaptersToInternal(props.chapters)
    return
  }

  if (props.streamId && props.autoChapters) {
    try {
      // Fetch chapters from StreamVault API
      const response = await fetch(`/api/streams/${props.streamId}/chapters`, {
        credentials: 'include' // CRITICAL: Required to send session cookie
      })
      if (response.ok) {
        const chaptersData = await response.json()
        const converted = chaptersData.map((ch: any, index: number, arr: any[]) => {
          // Calculate duration from API data or compute from next chapter
          let duration = ch.duration || 60
          if (!ch.duration && index < arr.length - 1) {
            // Calculate from next chapter's start time
            const nextStartTime = arr[index + 1].start_time || (ch.start_time + 60)
            duration = nextStartTime - ch.start_time
          }
          
          return {
            title: ch.category_name || ch.title || 'Stream Segment',
            startTime: ch.start_time || 0,
            duration: duration,
            gameIcon: getCategoryImage(ch.category_name)
          }
        })
        
        // Deduplicate by startTime and title
        parsedChapters.value = converted.filter((chapter: any, index: number, self: any[]) => 
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
const convertApiChaptersToInternal = (apiChapters: Array<{start_time: string, title: string, type: string}>) => {
  // Convert chapters first
  const converted = apiChapters.map((chapter, index) => ({
    title: chapter.title || `Chapter ${index + 1}`,
    startTime: parseTimeStringToSeconds(chapter.start_time),
    duration: 60, // Temporary, will be calculated below
    gameIcon: undefined
  }))
  
  // Deduplicate by startTime and title
  const unique = converted.filter((chapter, index, self) => 
    index === self.findIndex(c => 
      c.startTime === chapter.startTime && c.title === chapter.title
    )
  )
  
  // Calculate actual duration between chapters
  return calculateChapterDurations(unique)
}

// Calculate chapter durations based on video metadata
const calculateChapterDurations = (chapterList: Chapter[]): Chapter[] => {
  const videoDur = videoElement.value?.duration || videoDuration.value
  
  return chapterList.map((chapter, index) => {
    if (index < chapterList.length - 1) {
      // Duration = next chapter start time - current chapter start time
      chapter.duration = chapterList[index + 1].startTime - chapter.startTime
    } else {
      // Last chapter: calculate to end of video
      if (videoDur && !isNaN(videoDur) && videoDur > 0) {
        chapter.duration = videoDur - chapter.startTime
      } else {
        // Video not loaded yet, use placeholder
        chapter.duration = 60
      }
    }
    return chapter
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
  const localChapters: Chapter[] = []
  
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
      
      localChapters.push({
        title,
        startTime,
        duration
      })
    }
    i++
  }
  
  if (localChapters.length > 0) {
    parsedChapters.value = localChapters
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

// Scroll indicator management for chapter list
const handleChapterListScroll = (event: Event) => {
  const element = event.target as HTMLElement
  if (!element) return
  
  const scrollTop = element.scrollTop
  const scrollHeight = element.scrollHeight
  const clientHeight = element.clientHeight
  
  // Add/remove classes for scroll indicators
  if (scrollTop > 10) {
    element.classList.add('scrolled-top')
  } else {
    element.classList.remove('scrolled-top')
  }
  
  if (scrollTop < scrollHeight - clientHeight - 10) {
    element.classList.add('scrolled-bottom')
  } else {
    element.classList.remove('scrolled-bottom')
  }
}

// Auto-scroll to keep active chapter centered
const scrollToActiveChapter = (index: number) => {
  if (!chapterListPanel.value || !chapterItemRefs.value[index]) return
  
  const panel = chapterListPanel.value
  const item = chapterItemRefs.value[index] as HTMLElement
  
  // Calculate position to center the active item
  const itemTop = item.offsetTop
  const itemHeight = item.offsetHeight
  const panelHeight = panel.clientHeight
  const scrollPosition = itemTop - (panelHeight / 2) + (itemHeight / 2)
  
  // Smooth scroll to position
  panel.scrollTo({
    top: scrollPosition,
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
    parsedChapters.value = convertApiChaptersToInternal(newChapters)
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
    border-radius: 0;  // Eckig auf mobile
    box-shadow: none;
    overflow: visible;  // CRITICAL: Allow chapter menu and controls to overflow
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

/* Video Controls Extension - Current Chapter Info Display */
.video-controls-extension {
  background: rgba(var(--background-card-rgb), 0.95);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  padding: var(--spacing-3) var(--spacing-4);  /* 12px 16px */
  display: flex;
  justify-content: flex-end;  /* Right-aligned */
  align-items: center;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
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
  
  @include m.respond-below('md') {  // < 768px (mobile)
    font-size: var(--text-base);  /* 16px on mobile */
  }
}

.current-chapter-progress {
  font-size: var(--text-xs);  /* 12px */
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-weight: var(--font-medium);  /* 500 */
  
  @include m.respond-below('md') {  // < 768px (mobile)
    font-size: var(--text-sm);  /* 14px on mobile */
  }
}

/* Chapter List Panel - Overlay positioned inside video */
.chapter-list-panel {
  /* Glassmorphism panel design */
  background: rgba(var(--background-card-rgb), 0.97);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: var(--radius-lg);  /* 12px */
  box-shadow: var(--shadow-2xl), 0 0 40px rgba(0, 0, 0, 0.5);
  max-height: 500px;
  overflow-y: auto;
  position: absolute;  /* Position inside video wrapper */
  bottom: 80px;  /* Above video controls */
  right: var(--spacing-4);  /* 16px from right edge */
  width: 400px;  /* Fixed width for desktop */
  max-width: calc(100% - 32px);  /* Responsive on mobile */
  z-index: 20;  /* Above controls overlay */
  /* Animation now handled by Vue transition (see .slide-panel-* classes) */
  
  @include m.respond-below('md') {  // < 768px (mobile)
    width: calc(100% - 32px);  /* Full width on mobile with padding */
    bottom: 120px;  /* More space above controls */
    right: var(--spacing-4);
    left: var(--spacing-4);  /* Center horizontally */
    max-height: 60vh;  /* Responsive height - prevent cut-off */
    max-width: none;  /* Override desktop constraint */
  }
}

/* Vue Transition for Chapter Panel */
.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: all var(--duration-300) var(--ease-out);
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

/* Legacy animation (kept for backwards compatibility) */
@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
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
  // Use reusable list-item-interactive mixin from design system
  @include m.list-item-interactive;
  
  & {  // ✅ Wrap declaration to avoid mixed-decls warning
    border-left: 3px solid transparent;  /* Default border for active state */
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

.chapter-item.active .chapter-time,
.chapter-item.active .chapter-duration {
  color: rgba(255, 255, 255, 0.9);
}

.chapter-thumbnail,
.chapter-icon,
.chapter-placeholder {
  // Use reusable list-item-thumbnail mixin from design system
  @include m.list-item-thumbnail(80px, 96px);
}

.chapter-placeholder {
  font-size: var(--text-2xl);  /* 24px */
  color: var(--text-secondary);
}

.chapter-info {
  flex: 1;
  min-width: 0;
  padding-right: 40px;  /* Space for play icon on active items */
}

.chapter-title {
  font-weight: var(--font-semibold);  /* 600 */
  color: var(--text-primary);
  font-size: 15px;  /* Desktop: 15px */
  margin-bottom: var(--spacing-1);  /* 4px */
  line-height: var(--leading-snug);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  
  @include m.respond-below('md') {  // < 768px
    font-size: 16px;  /* Mobile: Larger, more readable */
    font-weight: var(--font-bold);  /* Bolder on mobile */
    -webkit-line-clamp: 2;  /* Allow 2 lines on mobile */
  }
}

.chapter-time {
  font-size: 14px;  /* Desktop: 14px */
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-weight: var(--font-medium);  /* 500 */
  margin-bottom: var(--spacing-0-5);  /* 2px */
  
  @include m.respond-below('md') {  // < 768px
    font-size: 16px;  /* Mobile: Larger timestamps */
    font-weight: var(--font-semibold);  /* Bolder for contrast */
  }
}

.chapter-duration {
  font-size: var(--text-xs);  /* 12px */
  color: var(--text-secondary);
  
  @include m.respond-below('md') {  // < 768px
    font-size: 14px;  /* Mobile: Larger subtitle text */
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
  transition: opacity 0.3s ease;
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

/* Chapter Navigation Buttons */
.chapter-nav-button {
  /* Same size as standard controls */
  opacity: 0.9;
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
  
  @include m.respond-below('md') {  // < 768px (mobile)
    min-width: 56px;
  }
}

.chapters-button.active {
  background: linear-gradient(135deg, var(--primary-color), var(--primary-color-dark));
  border-color: var(--primary-color);
  box-shadow: var(--shadow-md), 0 0 16px rgba(var(--primary-color-rgb), 0.3);
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
    padding: var(--spacing-2);  /* Reduce all padding to prevent overflow */
    padding-bottom: env(safe-area-inset-bottom, var(--spacing-2));  /* Account for safe area */
  }
  
  .progress-container {
    /* Extended vertical tap area for easier scrubbing */
    padding: var(--spacing-2) 0;  /* Reduce vertical padding */
    margin-bottom: var(--spacing-2);  /* Reduce spacing */
  }
  
  /* Ensure controls don't overflow */
  .controls-bottom {
    flex-wrap: nowrap;  /* Prevent wrapping */
    overflow-x: visible;  /* Allow horizontal visibility */
    min-width: 0;  /* Allow flex items to shrink */
  }
  
  .controls-left,
  .controls-right {
    min-width: 0;  /* Allow flex items to shrink */
    flex-shrink: 1;  /* Allow shrinking when needed */
  }
  
  /* Time display can shrink if needed */
  .time-display {
    flex-shrink: 2;  /* Can shrink more than buttons */
    min-width: 0;
  }
  
  /* Hide chapter toggle button on very small screens to save space */
  @media (max-width: 400px) {
    .chapters-button {
      display: none;  /* Hide on tiny screens - users can see chapters in extension */
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

  /* Chapter item mobile layout - keep horizontal layout */
  .chapter-item {
    /* Don't override flex-direction, keep horizontal */
    text-align: left;
    /* Padding and gap already set in base styles */
  }

  /* Thumbnails already sized in base styles */

  .chapter-info {
    width: auto;
    flex: 1;
  }

  .chapter-title {
    text-align: left;
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
