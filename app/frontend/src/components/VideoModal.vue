<template>
  <div class="video-modal-overlay" @click="closeModal">
    <div class="video-modal" @click.stop>
      <!-- Modal Header -->
      <div class="modal-header">
        <h2>{{ video.title || 'Video Player' }}</h2>
        <button @click="closeModal" class="close-btn">×</button>
      </div>
      
      <!-- Modal Content -->
      <div class="modal-content">
        <!-- Video Container -->
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
            @timeupdate="updateCurrentChapter"
          >
            Your browser does not support the video tag.
          </video>
            
          <!-- Loading State -->
          <div v-if="loading" class="video-loading">
            <div class="loading-spinner"></div>
            <p>Loading video...</p>
          </div>
          
          <!-- Error State -->
          <div v-if="error" class="video-error">
            <div class="error-icon">⚠️</div>
            <h3>Could not load video</h3>
            <p>{{ errorMessage }}</p>
            <button @click="retryVideo" class="retry-btn">🔄 Retry</button>
          </div>
        </div>
        
        <!-- Video Details -->
        <div class="video-details">
          <div class="video-info">
            <h3>{{ video.streamer_name }}</h3>
            <p class="video-date">{{ formatDate(video.created_at) }}</p>
            <div class="video-stats">
              <span v-if="video.duration" class="stat">
                🕐 {{ formatDuration(video.duration) }}
              </span>
              <span v-if="video.file_size" class="stat">
                📄 {{ formatFileSize(video.file_size) }}
              </span>
            </div>
          </div>
          
          <div class="video-actions">
            <button @click="downloadVideo" class="action-btn">
              ⬇️ Download
            </button>
            <button @click="shareVideo" class="action-btn">
              🔗 Share
            </button>
            <button 
              v-if="chapters.length > 0"
              @click="toggleChapters" 
              class="action-btn"
              :class="{ 'active': showChapters }"
            >
              📋 Chapters ({{ chapters.length }})
            </button>
          </div>
        </div>
        
        <!-- Chapter Navigation -->
        <div v-if="chapters.length > 0 && showChapters" class="chapters-panel">
          <div class="chapters-header">
            <h4>📋 Chapters</h4>
            <button @click="toggleChapters" class="close-chapters-btn">×</button>
          </div>
          <div class="chapters-list">
            <div 
              v-for="(chapter, index) in chapters" 
              :key="index"
              @click="jumpToChapter(chapter)"
              class="chapter-item"
              :class="{ 'active': currentChapter === index }"
            >
              <div class="chapter-number">{{ index + 1 }}</div>
              <div class="chapter-content">
                <div class="chapter-title">{{ chapter.title || `Chapter ${index + 1}` }}</div>
                <div class="chapter-time">{{ formatChapterTime(chapter.start_time) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { streamerApi } from '@/services/api'

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
  return `/api/videos/${props.video.id}/stream`
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
  // Get session token for public URL
  const sessionToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('session='))
    ?.split('=')[1]
  
  if (!sessionToken) {
    alert('Unable to generate share link: No active session')
    return
  }
  
  // Create a direct video stream URL with token that works in VLC and other media players
  const directVideoUrl = `${window.location.origin}/api/videos/public/${props.video.id}?token=${sessionToken}`
  
  const shareData = {
    title: props.video.title,
    text: `Check out this video from ${props.video.streamer_name}! Open in VLC or any media player.`,
    url: directVideoUrl
  }
  
  if (navigator.share) {
    try {
      await navigator.share(shareData)
    } catch (err) {
      if (err.name !== 'AbortError') {
        fallbackShare(directVideoUrl)
      }
    }
  } else {
    fallbackShare(directVideoUrl)
  }
}

const fallbackShare = (url) => {
  const sessionToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('session='))
    ?.split('=')[1]
    
  const shareUrl = url || (sessionToken ? 
    `${window.location.origin}/api/videos/public/${props.video.id}?token=${sessionToken}` :
    `${window.location.origin}/api/videos/${props.video.id}/stream`)
    
  navigator.clipboard.writeText(shareUrl).then(() => {
    alert('Direct video link copied!\n\nVLC: Press Ctrl+N (or Cmd+N on Mac) and paste the link\nOther players: Use "Open Network Stream" or similar option')
  }).catch(() => {
    alert(`Direct video link: ${shareUrl}\n\nVLC: Press Ctrl+N (or Cmd+N on Mac) and paste this link\nOther players: Use "Open Network Stream" or similar option`)
  })
}

const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleDateString('de-DE', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatDuration = (seconds) => {
  if (!seconds) return 'Unknown'
  
  const totalSeconds = Math.round(seconds)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const secs = totalSeconds % 60
  
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
  } catch (error) {
    console.error('Failed to jump to chapter:', error)
  }
}

const parseTimeToSeconds = (timeString) => {
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
    const [minutes, seconds] = parts
    return parseInt(minutes) * 60 + parseFloat(seconds)
  } else if (parts.length === 3) {
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
  background: rgba(0, 0, 0, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
}

.video-modal {
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  max-width: 90vw;
  max-height: 90vh;
  width: 100%;
  max-width: 1000px;
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  background: var(--background-card);
}

.modal-header h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.2rem;
  font-weight: 600;
  flex: 1;
  margin-right: 16px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  font-size: 1.5rem;
  line-height: 1;
  transition: color 0.2s;
}

.close-btn:hover {
  color: var(--text-primary);
}

.modal-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.video-container {
  position: relative;
  flex: 1;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}

.video-player {
  width: 100%;
  height: 100%;
  max-height: 60vh;
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
  padding: 20px;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(255,255,255,0.3);
  border-top: 4px solid var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-icon {
  font-size: 48px;
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
  background: var(--primary-color);
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: var(--border-radius);
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.retry-btn:hover {
  background: var(--primary-color-hover);
}

.video-details {
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  border-bottom: 1px solid var(--border-color);
}

.video-info {
  flex: 1;
  min-width: 0;
}

.video-info h3 {
  margin: 0 0 8px 0;
  color: var(--primary-color);
  font-size: 1.1rem;
  font-weight: 600;
}

.video-date {
  margin: 0 0 12px 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.video-stats {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.stat {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.video-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border: 1px solid var(--border-color);
  background: var(--background-darker);
  color: var(--text-primary);
  border-radius: var(--border-radius);
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
  font-size: 0.9rem;
  white-space: nowrap;
}

.action-btn:hover {
  background: var(--background-dark);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.action-btn.active {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: white;
}

/* Chapter Panel */
.chapters-panel {
  background: var(--background-darker);
  border-top: 1px solid var(--border-color);
  max-height: 300px;
  overflow-y: auto;
}

.chapters-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  background: var(--background-darker);
  position: sticky;
  top: 0;
  z-index: 10;
}

.chapters-header h4 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: 600;
}

.close-chapters-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  font-size: 1.2rem;
  line-height: 1;
  transition: color 0.2s;
}

.close-chapters-btn:hover {
  color: var(--text-primary);
}

.chapters-list {
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
  background: var(--background-dark);
  border-color: var(--border-color);
}

.chapter-item.active {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: white;
}

.chapter-number {
  width: 32px;
  height: 32px;
  background: var(--background-card);
  color: var(--text-primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.9rem;
  flex-shrink: 0;
}

.chapter-item.active .chapter-number {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.chapter-content {
  flex: 1;
  min-width: 0;
}

.chapter-title {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 0.95rem;
  margin-bottom: 4px;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.chapter-item.active .chapter-title {
  color: white;
}

.chapter-time {
  font-size: 0.8rem;
  color: var(--text-secondary);
  font-family: monospace;
  font-weight: 500;
}

.chapter-item.active .chapter-time {
  color: rgba(255, 255, 255, 0.8);
}

/* Mobile Responsive */
@media (max-width: 768px) {
  .video-modal-overlay {
    padding: 8px;
  }
  
  .video-modal {
    max-width: 100vw;
    max-height: 100vh;
    width: 100%;
    height: 100%;
    border-radius: 0;
  }
  
  .modal-header {
    padding: 12px 16px;
  }
  
  .modal-header h2 {
    font-size: 1.1rem;
  }
  
  .video-container {
    min-height: 200px;
  }
  
  .video-player {
    max-height: 50vh;
  }
  
  .video-details {
    flex-direction: column;
    gap: 16px;
    padding: 16px;
  }
  
  .video-actions {
    width: 100%;
  }
  
  .action-btn {
    flex: 1;
    justify-content: center;
    padding: 12px 8px;
  }
  
  .chapters-panel {
    max-height: 200px;
  }
  
  .chapters-header {
    padding: 12px 16px;
  }
  
  .chapter-item {
    padding: 16px 12px;
  }
  
  .chapter-number {
    width: 28px;
    height: 28px;
    font-size: 0.8rem;
  }
}

/* Small mobile screens */
@media (max-width: 480px) {
  .video-modal-overlay {
    padding: 0;
  }
  
  .video-modal {
    border-radius: 0;
    height: 100vh;
    max-height: 100vh;
  }
  
  .modal-header {
    padding: 10px 12px;
  }
  
  .modal-header h2 {
    font-size: 1rem;
  }
  
  .video-details {
    padding: 12px;
  }
  
  .video-stats {
    flex-direction: column;
    gap: 8px;
  }
  
  .video-actions {
    flex-direction: column;
    gap: 8px;
  }
  
  .action-btn {
    width: 100%;
    padding: 14px;
  }
  
  .chapters-panel {
    max-height: 150px;
  }
  
  .chapter-item {
    padding: 12px;
  }
}

/* Landscape mobile */
@media (max-width: 768px) and (orientation: landscape) {
  .video-details {
    display: none;
  }
  
  .video-player {
    max-height: 80vh;
  }
  
  .chapters-panel {
    max-height: 120px;
  }
}
</style>
