<template>
  <div class="video-tabs-container">
    <!-- Tab Headers -->
    <div class="tab-headers">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id"
        :class="['tab-header', { active: activeTab === tab.id }]"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span class="tab-title">{{ tab.title }}</span>
        <span v-if="tab.count" class="tab-count">{{ tab.count }}</span>
      </button>
    </div>

    <!-- Tab Content -->
    <div class="tab-content">
      <!-- Video Player Tab -->
      <div v-if="activeTab === 'player'" class="tab-panel">
        <div class="video-section">
          <h3>{{ currentVideo?.title || 'Stream Recording' }}</h3>
          <div v-if="currentVideo" class="video-info">
            <span class="info-item">
              <i class="icon">📅</i>
              {{ formatDate(currentVideo.date) }}
            </span>
            <span class="info-item" v-if="currentVideo.duration">
              <i class="icon">⏱️</i>
              {{ formatDuration(currentVideo.duration) }}
            </span>
            <span class="info-item" v-if="currentVideo.game">
              <i class="icon">🎮</i>
              {{ currentVideo.game }}
            </span>
          </div>
          
          <VideoPlayer
            v-if="currentVideo"
            :video-src="currentVideo.src"
            :stream-id="currentVideo.streamId"
            :chapters-url="currentVideo.chaptersUrl"
            @chapter-change="onChapterChange"
            @video-ready="onVideoReady"
          />
          
          <div v-else class="no-video-selected">
            <div class="no-video-icon">📹</div>
            <h4>No Video Selected</h4>
            <p>Select a video from the list on the right side.</p>
          </div>
        </div>
      </div>

      <!-- Video List Tab -->
      <div v-if="activeTab === 'list'" class="tab-panel">
        <div class="video-list-section">
          <div class="section-header">
            <h3>Verfügbare Videos</h3>
            <div class="list-controls">
              <select v-model="sortBy" class="sort-select">
                <option value="date">By Date</option>
                <option value="title">By Title</option>
                <option value="duration">By Duration</option>
                <option value="game">By Game</option>
              </select>
              <button @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'" class="sort-order-btn">
                {{ sortOrder === 'asc' ? '↑' : '↓' }}
              </button>
            </div>
          </div>

          <div class="video-grid">
            <div
              v-for="video in sortedVideos"
              :key="video.id"
              @click="selectVideo(video)"
              :class="['video-card', { active: currentVideo?.id === video.id }]"
            >
              <div class="video-thumbnail">
                <img v-if="video.thumbnail" :src="video.thumbnail" :alt="video.title" />
                <div v-else class="default-thumbnail">
                  <span class="thumbnail-icon">🎬</span>
                </div>
                <div class="video-duration">{{ formatDuration(video.duration) }}</div>
              </div>
              
              <div class="video-details">
                <h4 class="video-title">{{ video.title }}</h4>
                <p class="video-date">{{ formatDate(video.date) }}</p>
                <p v-if="video.game" class="video-game">🎮 {{ video.game }}</p>
                <p v-if="video.fileSize" class="video-size">💾 {{ formatFileSize(video.fileSize) }}</p>
              </div>
            </div>
          </div>

          <div v-if="videos.length === 0" class="no-videos">
            <div class="no-videos-icon">📁</div>
            <h4>No Videos Found</h4>
            <p>No stream recordings are available yet.</p>
          </div>
        </div>
      </div>

      <!-- Statistics Tab -->
      <div v-if="activeTab === 'stats'" class="tab-panel">
        <div class="stats-section">
          <h3>Video-Statistiken</h3>
          
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-value">{{ videos.length }}</div>
              <div class="stat-label">Total Videos</div>
            </div>
            
            <div class="stat-card">
              <div class="stat-value">{{ formatDuration(totalDuration) }}</div>
              <div class="stat-label">Total Duration</div>
            </div>
            
            <div class="stat-card">
              <div class="stat-value">{{ formatFileSize(totalSize) }}</div>
              <div class="stat-label">Total Size</div>
            </div>
            
            <div class="stat-card">
              <div class="stat-value">{{ uniqueGames.length }}</div>
              <div class="stat-label">Verschiedene Spiele</div>
            </div>
          </div>

          <div class="games-breakdown">
            <h4>Recordings by Game</h4>
            <div class="game-list">
              <div v-for="game in gameStats" :key="game.name" class="game-item">
                <span class="game-name">{{ game.name || 'Unbekannt' }}</span>
                <span class="game-count">{{ game.count }} Videos</span>
                <span class="game-duration">{{ formatDuration(game.duration) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import VideoPlayer from './VideoPlayer.vue'

interface VideoData {
  id: string
  title: string
  src: string
  date: Date
  duration: number
  game?: string
  thumbnail?: string
  fileSize?: number
  streamId?: number
  chaptersUrl?: string
}

interface Props {
  videos: VideoData[]
  initialVideo?: VideoData
}

const props = defineProps<Props>()

const activeTab = ref('player')
const currentVideo = ref<VideoData | null>(props.initialVideo || null)
const sortBy = ref('date')
const sortOrder = ref<'asc' | 'desc'>('desc')

const tabs = computed(() => [
  {
    id: 'player',
    title: 'Player',
    icon: '▶️',
    count: null
  },
  {
    id: 'list',
    title: 'Videos',
    icon: '📋',
    count: props.videos.length
  },
  {
    id: 'stats',
    title: 'Statistics',
    icon: '📊',
    count: null
  }
])

const sortedVideos = computed(() => {
  const sorted = [...props.videos].sort((a, b) => {
    let aVal: any, bVal: any
    
    switch (sortBy.value) {
      case 'title':
        aVal = a.title.toLowerCase()
        bVal = b.title.toLowerCase()
        break
      case 'duration':
        aVal = a.duration
        bVal = b.duration
        break
      case 'game':
        aVal = (a.game || '').toLowerCase()
        bVal = (b.game || '').toLowerCase()
        break
      case 'date':
      default:
        aVal = a.date.getTime()
        bVal = b.date.getTime()
        break
    }
    
    if (sortOrder.value === 'asc') {
      return aVal < bVal ? -1 : aVal > bVal ? 1 : 0
    } else {
      return aVal > bVal ? -1 : aVal < bVal ? 1 : 0
    }
  })
  
  return sorted
})

const totalDuration = computed(() => {
  return props.videos.reduce((total, video) => total + (video.duration || 0), 0)
})

const totalSize = computed(() => {
  return props.videos.reduce((total, video) => total + (video.fileSize || 0), 0)
})

const uniqueGames = computed(() => {
  const games = new Set(props.videos.map(v => v.game).filter(Boolean))
  return Array.from(games)
})

// PERFORMANCE FIX: Memoized gameStats computation 
const gameStats = computed(() => {
  // Early return if no videos to avoid expensive operations
  if (!props.videos || props.videos.length === 0) {
    return []
  }
  
  const stats = new Map<string, { count: number, duration: number }>()
  
  // Use for loop instead of forEach for better performance
  for (let i = 0; i < props.videos.length; i++) {
    const video = props.videos[i]
    const game = video.game || 'Unbekannt'
    const current = stats.get(game)
    
    if (current) {
      current.count++
      current.duration += video.duration || 0
    } else {
      stats.set(game, { count: 1, duration: video.duration || 0 })
    }
  }
  
  // Convert and sort in one step
  const result = []
  for (const [name, data] of stats.entries()) {
    result.push({ name, ...data })
  }
  
  return result.sort((a, b) => b.count - a.count)
})

const selectVideo = (video: VideoData) => {
  currentVideo.value = video
  activeTab.value = 'player'
}

const onChapterChange = (chapter: any, index: number) => {
}

const onVideoReady = (duration: number) => {
}

const formatDate = (date: Date): string => {
  return new Intl.DateTimeFormat('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

const formatDuration = (seconds: number): string => {
  if (!seconds) return '00:00'
  
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

const formatFileSize = (bytes: number): string => {
  if (!bytes) return '0 B'
  
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

// Auto-select first video if none selected
watch(() => props.videos, (newVideos) => {
  if (!currentVideo.value && newVideos.length > 0) {
    currentVideo.value = newVideos[0]
  }
}, { immediate: true })
</script>

<style scoped>
.video-tabs-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f8f9fa;
  border-radius: 8px;
  overflow: hidden;
}

.tab-headers {
  display: flex;
  background: #fff;
  border-bottom: 1px solid #e9ecef;
}

.tab-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s;
  border-bottom: 3px solid transparent;
}

.tab-header:hover {
  background: #f8f9fa;
}

.tab-header.active {
  background: #fff;
  border-bottom-color: #007bff;
  color: #007bff;
}

.tab-count {
  background: #6c757d;
  color: white;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 16px;
  text-align: center;
}

.tab-header.active .tab-count {
  background: #007bff;
}

.tab-content {
  flex: 1;
  overflow: auto;
}

.tab-panel {
  padding: 20px;
  height: 100%;
}

/* Video Player Tab */
.video-section h3 {
  margin: 0 0 10px 0;
  color: #333;
}

.video-info {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #666;
}

.no-video-selected {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: #666;
}

.no-video-icon {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.5;
}

/* Video List Tab */
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.list-controls {
  display: flex;
  gap: 10px;
  align-items: center;
}

.sort-select {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.sort-order-btn {
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 16px;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.video-card {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
}

.video-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.video-card.active {
  border-color: #007bff;
}

.video-thumbnail {
  position: relative;
  aspect-ratio: 16/9;
  background: #000;
}

.video-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.default-thumbnail {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #333, #555);
}

.thumbnail-icon {
  font-size: 48px;
  opacity: 0.5;
}

.video-duration {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0,0,0,0.8);
  color: white;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.video-details {
  padding: 15px;
}

.video-title {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  line-height: 1.3;
}

.video-date,
.video-game,
.video-size {
  margin: 4px 0;
  font-size: 13px;
  color: #666;
}

.no-videos {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: #666;
}

.no-videos-icon {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.5;
}

/* Statistics Tab */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: white;
  padding: 25px;
  border-radius: 8px;
  text-align: center;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: #007bff;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #666;
  text-transform: uppercase;
  font-weight: 500;
}

.games-breakdown {
  background: white;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.games-breakdown h4 {
  margin: 0 0 20px 0;
  color: #333;
}

.game-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #eee;
}

.game-item:last-child {
  border-bottom: none;
}

.game-name {
  font-weight: 500;
  color: #333;
}

.game-count,
.game-duration {
  font-size: 14px;
  color: #666;
}

/* Mobile responsiveness */
@media (max-width: 768px) {
  .tab-headers {
    overflow-x: auto;
  }
  
  .tab-header {
    white-space: nowrap;
    padding: 10px 16px;
  }
  
  .video-info {
    flex-direction: column;
    gap: 10px;
  }
  
  .video-grid {
    grid-template-columns: 1fr;
  }
  
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .section-header {
    flex-direction: column;
    gap: 15px;
    align-items: stretch;
  }
}
</style>
