<template>
  <div class="video-player-view">
    <div class="player-header">
      <button @click="goBack" class="back-btn">
        ← Back to Streams
      </button>
      <div class="stream-info">
        <h1>{{ streamTitle }}</h1>
        <p v-if="streamerName">{{ streamerName }}</p>
      </div>
    </div>
    
    <div v-if="isLoading" class="loading-container">
      <div class="spinner"></div>
      <p>Loading video player...</p>
    </div>
    
    <div v-else-if="error" class="error-container">
      <p class="error-message">{{ error }}</p>
      <button @click="retryLoad" class="btn btn-primary">Retry</button>
    </div>
    
    <div v-else-if="!chapterData?.video_url" class="no-video-container">
      <p>No video file available for this stream.</p>
      <button @click="retryLoad" class="btn btn-secondary">Refresh</button>
    </div>
    
    <VideoPlayer 
      v-else
      :video-src="chapterData.video_url"
      :chapters="chapterData.chapters"
      :stream-title="chapterData.stream_title"
      class="video-player-container"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VideoPlayer from '@/components/VideoPlayer.vue'

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
const streamTitle = computed(() => route.query.title as string || `Stream ${streamId.value}`)
const streamerName = computed(() => route.query.streamerName as string)

const chapterData = ref<ChapterData | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)

const loadChapterData = async () => {
  try {
    isLoading.value = true
    error.value = null
    
    const response = await fetch(`/api/streamers/${streamerId.value}/streams/${streamId.value}/chapters`)
    
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Stream not found')
      }
      throw new Error(`Failed to load video data: ${response.statusText}`)
    }
    
    chapterData.value = await response.json()
  } catch (err) {
    console.error('Error loading chapter data:', err)
    error.value = err instanceof Error ? err.message : 'Failed to load video data'
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

onMounted(() => {
  loadChapterData()
})
</script>

<style scoped>
.video-player-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #000;
}

.player-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.9), rgba(0, 0, 0, 0.7));
  color: white;
  border-bottom: 2px solid #444;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.back-btn {
  background: rgba(255, 255, 255, 0.1);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.4);
  transform: translateY(-1px);
}

.stream-info h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
}

.stream-info p {
  margin: 0.25rem 0 0 0;
  color: #ccc;
  font-size: 0.9rem;
}

.loading-container,
.error-container,
.no-video-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: white;
  text-align: center;
  padding: 2rem;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top: 3px solid #fff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-message {
  color: #ff6b6b;
  margin-bottom: 1rem;
  font-size: 1.1rem;
}

.btn {
  background: #6f42c1;
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  transition: background-color 0.2s;
}

.btn:hover {
  background: #5a2d91;
}

.btn.btn-primary {
  background: #007bff;
}

.btn.btn-primary:hover {
  background: #0056b3;
}

.video-player-container {
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .player-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }
  
  .stream-info h1 {
    font-size: 1.25rem;
  }
  
  .loading-container,
  .error-container,
  .no-video-container {
    padding: 1rem;
  }
}
</style>
