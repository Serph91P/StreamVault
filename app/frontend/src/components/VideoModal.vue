<template>
  <div class="video-modal-overlay" @click="closeModal">
    <div class="video-modal" @click.stop>
      <div class="modal-header">
        <h2>{{ video.title }}</h2>
        <button @click="closeModal" class="close-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      
      <div class="modal-content">
        <div class="video-container">
          <video 
            ref="videoPlayer"
            :src="videoUrl" 
            controls 
            preload="metadata"
            class="video-player"
            @loadstart="onLoadStart"
            @canplay="onCanPlay"
            @error="onError"
          >
            Your browser does not support the video tag.
          </video>
            <div v-if="loading" class="video-loading">
            <div class="loading-spinner"></div>
            <p>Loading video...</p>
          </div>
          
          <div v-if="error" class="video-error">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="15" y1="9" x2="9" y2="15"></line>
              <line x1="9" y1="9" x2="15" y2="15"></line>
            </svg>
            <h3>Could not load video</h3>
            <p>{{ errorMessage }}</p>
            <button @click="retryVideo" class="retry-btn">Retry</button>
          </div>

          <!-- Chapter Navigation -->
          <div v-if="chapters.length > 0 && !loading && !error" class="chapter-navigation">
            <button 
              @click="toggleChapters" 
              class="chapters-toggle-btn"
              :class="{ active: showChapters }"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="9" y1="9" x2="15" y2="9"></line>
                <line x1="9" y1="12" x2="15" y2="12"></line>
                <line x1="9" y1="15" x2="15" y2="15"></line>
              </svg>
              Chapters ({{ chapters.length }})
            </button>
            <div v-if="showChapters" class="chapters-list">
              <div 
                v-for="(chapter, index) in chapters" 
                :key="index"
                @click="jumpToChapter(chapter)"
                class="chapter-item"
                :class="{ active: currentChapter === index }"
              >
                <div class="chapter-time">{{ formatChapterTime(chapter.start_time) }}</div>
                <div class="chapter-title">{{ chapter.title || `Chapter ${index + 1}` }}</div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="video-details">
          <div class="video-info">
            <h3>{{ video.streamer_name }}</h3>
            <p class="video-date">{{ formatDate(video.created_at) }}</p>
            <div class="video-stats">
              <span v-if="video.duration" class="stat">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <polyline points="12,6 12,12 16,14"></polyline>
                </svg>
                {{ formatDuration(video.duration) }}
              </span>
              <span v-if="video.file_size" class="stat">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14,2 14,8 20,8"></polyline>
                </svg>
                {{ formatFileSize(video.file_size) }}
              </span>
            </div>
          </div>
          
          <div class="video-actions">
            <button @click="downloadVideo" class="action-btn download-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              Download
            </button>
              <button @click="shareVideo" class="action-btn share-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
              </svg>
              Share
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { streamerApi } from '../services/api.js'

const props = defineProps({
  video: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['close'])

const videoPlayer = ref(null)
const loading = ref(true)
const error = ref(false)
const errorMessage = ref('')
const chapters = ref([])
const showChapters = ref(false)
const currentChapter = ref(-1)

const videoUrl = computed(() => {
  // Use the stream ID based endpoint
  return `/api/videos/stream/${props.video.id}`
})

const closeModal = () => {
  if (videoPlayer.value) {
    videoPlayer.value.pause()
    videoPlayer.value.removeEventListener('timeupdate', updateCurrentChapter)
  }
  emit('close')
}

const onLoadStart = () => {
  loading.value = true
  error.value = false
}

const onCanPlay = () => {
  loading.value = false
  error.value = false
  
  // Add event listener for time updates to track current chapter
  if (videoPlayer.value) {
    videoPlayer.value.addEventListener('timeupdate', updateCurrentChapter)
  }
}

const onError = (event) => {
  loading.value = false
  error.value = true
  
  const videoEl = event.target
  if (videoEl.error) {
    switch (videoEl.error.code) {
      case videoEl.error.MEDIA_ERR_ABORTED:
        errorMessage.value = 'Video playback was aborted.'
        break
      case videoEl.error.MEDIA_ERR_NETWORK:
        errorMessage.value = 'Network error while loading video.'
        break
      case videoEl.error.MEDIA_ERR_DECODE:
        errorMessage.value = 'Video could not be decoded.'
        break
      case videoEl.error.MEDIA_ERR_SRC_NOT_SUPPORTED:
        errorMessage.value = 'Video format is not supported.'
        break
      default:
        errorMessage.value = 'Unknown error while loading video.'
    }
  } else {
    errorMessage.value = 'Video could not be found. Please check the path and try again.'
  }
  
  console.error('Video error:', event.target.error, 'URL:', videoUrl.value)
}

const retryVideo = () => {
  if (videoPlayer.value) {
    error.value = false
    loading.value = true
    videoPlayer.value.load()
  }
}

const downloadVideo = () => {
  const link = document.createElement('a')
  link.href = videoUrl.value
  link.download = props.video.title || 'video.mp4'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

const shareVideo = async () => {
  const shareData = {
    title: props.video.title,
    text: `Check out this video from ${props.video.streamer_name}!`,
    url: window.location.href
  }
  
  if (navigator.share) {
    try {
      await navigator.share(shareData)
    } catch (err) {
      if (err.name !== 'AbortError') {
        fallbackShare()
      }
    }
  } else {
    fallbackShare()
  }
}

const fallbackShare = () => {
  const url = window.location.href
  navigator.clipboard.writeText(url).then(() => {
    alert('Link copied to clipboard!')
  }).catch(() => {
    alert(`Share link: ${url}`)
  })
}

const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatDuration = (seconds) => {
  if (!seconds) return 'Unknown'
  
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  } else {
    return `${minutes}:${secs.toString().padStart(2, '0')}`
  }
}

const formatFileSize = (bytes) => {
  if (!bytes) return 'Unknown'
  
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`
}

// Chapter navigation functions
const loadChapters = async () => {
  try {
    if (!props.video.streamer_id || !props.video.id) {
      console.warn('Missing streamer_id or stream id for loading chapters')
      return
    }
    
    const response = await streamerApi.getStreamChapters(props.video.streamer_id, props.video.id)
    chapters.value = response.chapters || []
    console.log(`Loaded ${chapters.value.length} chapters for stream ${props.video.id}`)
  } catch (error) {
    console.error('Failed to load chapters:', error)
    chapters.value = []
  }
}

const toggleChapters = () => {
  showChapters.value = !showChapters.value
}

const jumpToChapter = (chapter) => {
  if (!videoPlayer.value) return
  
  try {
    const timeInSeconds = parseTimeToSeconds(chapter.start_time)
    videoPlayer.value.currentTime = timeInSeconds
    
    // Update current chapter
    const chapterIndex = chapters.value.indexOf(chapter)
    currentChapter.value = chapterIndex
    
    console.log(`Jumped to chapter: ${chapter.title} at ${chapter.start_time} (${timeInSeconds}s)`)
  } catch (error) {
    console.error('Failed to jump to chapter:', error)
  }
}

const parseTimeToSeconds = (timeString) => {
  // Handle different time formats: "HH:MM:SS.mmm", "MM:SS", ISO datetime
  if (!timeString) return 0
  
  // If it looks like an ISO datetime, convert to seconds from start
  if (timeString.includes('T')) {
    const chapterTime = new Date(timeString)
    const streamStart = new Date(props.video.created_at || props.video.started_at)
    return Math.max(0, (chapterTime - streamStart) / 1000)
  }
  
  // Handle "HH:MM:SS.mmm" or "MM:SS" format
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

const formatChapterTime = (timeString) => {
  try {
    const seconds = parseTimeToSeconds(timeString)
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    } else {
      return `${minutes}:${secs.toString().padStart(2, '0')}`
    }
  } catch (error) {
    return timeString
  }
}

const updateCurrentChapter = () => {
  if (!videoPlayer.value || chapters.value.length === 0) return
  
  const currentTime = videoPlayer.value.currentTime
  let newCurrentChapter = -1
  
  for (let i = chapters.value.length - 1; i >= 0; i--) {
    const chapterTime = parseTimeToSeconds(chapters.value[i].start_time)
    if (currentTime >= chapterTime) {
      newCurrentChapter = i
      break
    }
  }
  
  if (newCurrentChapter !== currentChapter.value) {
    currentChapter.value = newCurrentChapter
  }
}

// Handle ESC key
const handleKeydown = (event) => {
  if (event.key === 'Escape') {
    closeModal()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  document.body.style.overflow = 'hidden'
  
  // Load chapters for this stream
  loadChapters()
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.video-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.video-modal {
  background: var(--bg-secondary, #2d2d2d);
  border-radius: 12px;
  max-width: 90vw;
  max-height: 90vh;
  width: 1000px;
  overflow: hidden;
  position: relative;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--border-color, #404040);
}

.modal-header h2 {
  margin: 0;
  color: var(--text-primary, #ffffff);
  font-size: 1.3rem;
  flex: 1;
  margin-right: 20px;
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary, #b0b0b0);
  cursor: pointer;
  padding: 5px;
  border-radius: 6px;
  transition: all 0.3s;
}

.close-btn:hover {
  background: var(--bg-tertiary, #404040);
  color: var(--text-primary, #ffffff);
}

.modal-content {
  display: flex;
  flex-direction: column;
  height: calc(90vh - 100px);
  max-height: 800px;
}

.video-container {
  position: relative;
  flex: 1;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-player {
  width: 100%;
  height: 100%;
  max-height: 500px;
  object-fit: contain;
}

.video-loading,
.video-error {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: white;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(255,255,255,0.3);
  border-top: 4px solid white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 20px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.video-error svg {
  margin-bottom: 16px;
}

.video-error h3 {
  margin: 0 0 8px 0;
  font-size: 1.2rem;
}

.video-error p {
  margin: 0 0 16px 0;
  opacity: 0.8;
}

.retry-btn {
  background: var(--primary-color, #6f42c1);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: background-color 0.3s;
}

.retry-btn:hover {
  background: var(--primary-hover, #5a359a);
}

.video-details {
  padding: 20px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
}

.video-info h3 {
  margin: 0 0 8px 0;
  color: var(--primary-color, #6f42c1);
  font-size: 1.2rem;
}

.video-date {
  margin: 0 0 12px 0;
  color: var(--text-secondary, #b0b0b0);
  font-size: 0.9rem;
}

.video-stats {
  display: flex;
  gap: 16px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary, #b0b0b0);
  font-size: 0.9rem;
}

.video-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border: 2px solid var(--border-color, #404040);
  background: transparent;
  color: var(--text-primary, #ffffff);
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s;
}

.action-btn:hover {
  background: var(--primary-color, #6f42c1);
  border-color: var(--primary-color, #6f42c1);
}

/* Chapter Navigation */
.chapter-navigation {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 10;
}

.chapters-toggle-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.3s;
  backdrop-filter: blur(5px);
}

.chapters-toggle-btn:hover,
.chapters-toggle-btn.active {
  background: rgba(111, 66, 193, 0.8);
  border-color: var(--primary-color, #6f42c1);
}

.chapters-list {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: rgba(0, 0, 0, 0.9);
  border-radius: 8px;
  padding: 8px 0;
  min-width: 250px;
  max-width: 350px;
  max-height: 300px;
  overflow-y: auto;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.chapter-item {
  padding: 10px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
  border-left: 3px solid transparent;
}

.chapter-item:hover {
  background: rgba(255, 255, 255, 0.1);
}

.chapter-item.active {
  background: rgba(111, 66, 193, 0.3);
  border-left-color: var(--primary-color, #6f42c1);
}

.chapter-time {
  font-size: 0.8rem;
  color: var(--primary-color, #6f42c1);
  font-weight: 600;
  margin-bottom: 2px;
}

.chapter-title {
  font-size: 0.9rem;
  color: white;
  line-height: 1.3;
  word-wrap: break-word;
}

.chapter-item.active .chapter-title {
  font-weight: 500;
}

/* Mobile Responsive */
@media (max-width: 768px) {
  .video-modal-overlay {
    padding: 10px;
  }
  
  .video-modal {
    width: 100%;
    max-width: 100vw;
    max-height: 100vh;
    border-radius: 0;
  }
  
  .modal-header {
    padding: 15px;
  }
  
  .modal-header h2 {
    font-size: 1.1rem;
  }
  
  .modal-content {
    height: calc(100vh - 80px);
  }
  
  .video-details {
    flex-direction: column;
    gap: 16px;
  }
  
  .video-actions {
    align-self: stretch;
  }
  
  .action-btn {
    flex: 1;
    justify-content: center;
  }

  /* Chapter Navigation Mobile */
  .chapter-navigation {
    top: 10px;
    right: 10px;
  }

  .chapters-toggle-btn {
    padding: 6px 10px;
    font-size: 0.8rem;
  }

  .chapters-list {
    min-width: 200px;
    max-width: 280px;
    max-height: 250px;
    right: -10px;
  }

  .chapter-item {
    padding: 8px 12px;
  }

  .chapter-time {
    font-size: 0.75rem;
  }

  .chapter-title {
    font-size: 0.85rem;
  }
}

/* Landscape mobile */
@media (max-width: 768px) and (orientation: landscape) {
  .video-details {
    display: none;
  }
  
  .modal-content {
    height: calc(100vh - 60px);
  }
  
  .modal-header {
    padding: 10px 15px;
  }

  .chapter-navigation {
    top: 60px;
    right: 10px;
  }

  .chapters-list {
    max-height: 200px;
  }
}
</style>
