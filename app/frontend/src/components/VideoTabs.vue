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
          <div class="video-header">
            <h3>{{ currentVideo?.title || 'Stream Recording' }}</h3>
            <div v-if="currentVideo" class="video-info">
              <span class="info-item">
                📅 {{ formatDate(currentVideo.date) }}
              </span>
              <span class="info-item" v-if="currentVideo.duration">
                ⏱️ {{ formatDuration(currentVideo.duration) }}
              </span>
              <span class="info-item" v-if="currentVideo.game">
                🎮 {{ currentVideo.game }}
              </span>
            </div>
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
            <div class="no-video-icon">🎬</div>
            <h4>No Video Selected</h4>
            <p>Select a video from the Videos tab to start watching.</p>
          </div>
        </div>
      </div>

      <!-- Video List Tab -->
      <div v-if="activeTab === 'list'" class="tab-panel">
        <div class="video-list-section">
          <div class="section-header">
            <h3>Available Videos</h3>
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
          <h3>Video Statistics</h3>
          
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
              <div class="stat-label">Different Games</div>
            </div>
          </div>

          <div class="games-breakdown">
            <h4>📊 Recordings by Game</h4>
            <div class="game-list">
              <div v-for="game in gameStats" :key="game.name" class="game-item">
                <span class="game-name">{{ game.name || 'Unknown' }}</span>
                <div class="game-stats">
                  <span class="game-count">{{ game.count }} videos</span>
                  <span class="game-duration">{{ formatDuration(game.duration) }}</span>
                </div>
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
    title: 'Stats',
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

const gameStats = computed(() => {
  if (!props.videos || props.videos.length === 0) {
    return []
  }
  
  const stats = new Map<string, { count: number, duration: number }>()
  
  for (let i = 0; i < props.videos.length; i++) {
    const video = props.videos[i]
    const game = video.game || 'Unknown'
    const current = stats.get(game)
    
    if (current) {
      current.count++
      current.duration += video.duration || 0
    } else {
      stats.set(game, { count: 1, duration: video.duration || 0 })
    }
  }
  
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
  // Handle chapter changes
}

const onVideoReady = (duration: number) => {
  // Handle video ready
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

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.video-tabs-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--background-primary);
  border-radius: var(--border-radius);
  overflow: hidden;
}

.tab-headers {
  display: flex;
  background: var(--background-card);
  border-bottom: 1px solid var(--border-color);
  overflow-x: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.tab-headers::-webkit-scrollbar {
  display: none;
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
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}

.tab-header:hover {
  background: var(--background-darker);
  color: var(--text-primary);
}

.tab-header.active {
  background: var(--background-card);
  border-bottom-color: var(--primary-color);
  color: var(--primary-color);
}

.tab-icon {
  font-size: 1.1rem;
}

.tab-title {
  font-weight: 500;
}

.tab-count {
  background: var(--text-secondary);
  color: white;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: var(--radius-lg);
  min-width: 20px;
  text-align: center;
  font-weight: 600;
}

.tab-header.active .tab-count {
  background: var(--primary-color);
}

.tab-content {
  flex: 1;
  overflow: auto;
}

.tab-panel {
  padding: 20px;
  height: 100%;
  min-height: 0;
}

/* Video Player Tab */
.video-section {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.video-header {
  margin-bottom: 20px;
}

.video-header h3 {
  margin: 0 0 10px 0;
  color: var(--text-primary);
  font-size: 1.3rem;
  font-weight: 600;
}

.video-info {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.9rem;
  color: var(--text-secondary);
  padding: 4px 8px;
  background: var(--background-darker);
  border-radius: var(--border-radius);
}

.no-video-selected {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  text-align: center;
  color: var(--text-secondary);
  padding: 60px 20px;
}

.no-video-icon {
  font-size: 4rem;
  margin-bottom: 20px;
  opacity: 0.5;
}

.no-video-selected h4 {
  margin: 0 0 8px 0;
  color: var(--text-primary);
  font-size: 1.2rem;
}

.no-video-selected p {
  margin: 0;
  max-width: 300px;
  line-height: 1.5;
}

/* Video List Tab */
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.2rem;
  font-weight: 600;
}

.list-controls {
  display: flex;
  gap: 8px;
  align-items: center;
}

.sort-select {
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  background: var(--background-card);
  color: var(--text-primary);
  font-size: 0.9rem;
}

.sort-order-btn {
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  background: var(--background-card);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 1rem;
  transition: all 0.2s;
}

.sort-order-btn:hover {
  background: var(--background-darker);
  border-color: var(--primary-color);
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.video-card {
  background: var(--background-card);
  border-radius: var(--border-radius);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid var(--border-color);
}

.video-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  border-color: var(--primary-color);
}

.video-card.active {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(66, 184, 131, 0.2);
}

.video-thumbnail {
  position: relative;
  aspect-ratio: 16/9;
  background: var(--background-darker);
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
  background: var(--background-darker);
}

.thumbnail-icon {
  font-size: 2rem;
  color: var(--text-secondary);
  opacity: 0.5;
}

.video-duration {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0,0,0,0.8);
  color: white;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
  font-weight: 500;
  font-family: monospace;
}

.video-details {
  padding: 16px;
}

.video-title {
  margin: 0 0 8px 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.video-date,
.video-game,
.video-size {
  margin: 4px 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.no-videos {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: var(--text-secondary);
}

.no-videos-icon {
  font-size: 4rem;
  margin-bottom: 20px;
  opacity: 0.5;
}

.no-videos h4 {
  margin: 0 0 8px 0;
  color: var(--text-primary);
  font-size: 1.2rem;
}

.no-videos p {
  margin: 0;
  max-width: 300px;
  line-height: 1.5;
}

/* Statistics Tab */
.stats-section h3 {
  margin: 0 0 20px 0;
  color: var(--text-primary);
  font-size: 1.2rem;
  font-weight: 600;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: var(--background-card);
  padding: 24px;
  border-radius: var(--border-radius);
  text-align: center;
  border: 1px solid var(--border-color);
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--primary-color);
  margin-bottom: 8px;
  line-height: 1;
}

.stat-label {
  font-size: 0.9rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.games-breakdown {
  background: var(--background-card);
  padding: 20px;
  border-radius: var(--border-radius);
  border: 1px solid var(--border-color);
}

.games-breakdown h4 {
  margin: 0 0 16px 0;
  color: var(--text-primary);
  font-size: 1.1rem;
  font-weight: 600;
}

.game-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.game-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-radius: var(--border-radius);
  background: var(--background-darker);
  border: 1px solid var(--border-color);
}

.game-name {
  font-weight: 500;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
  margin-right: 12px;
}

.game-stats {
  display: flex;
  gap: 12px;
  align-items: center;
}

.game-count,
.game-duration {
  font-size: 0.85rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

/* Mobile Responsive */
@include m.respond-below('md') {  // < 768px
  .tab-panel {
    padding: 16px;
  }
  
  .video-info {
    flex-direction: column;
    gap: 8px;
  }
  
  .info-item {
    align-self: flex-start;
  }
  
  .section-header {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }
  
  .list-controls {
    justify-content: space-between;
  }
  
  .video-grid {
    grid-template-columns: 1fr;
  }
  
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .game-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .game-stats {
    align-self: flex-end;
  }
}

/* Small mobile screens */
@include m.respond-below('xs') {  // < 480px
  .tab-panel {
    padding: 12px;
  }
  
  .tab-header {
    padding: 10px 16px;
  }
  
  .video-header h3 {
    font-size: 1.1rem;
  }
  
  .section-header h3 {
    font-size: 1.1rem;
  }
  
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .stat-value {
    font-size: 1.5rem;
  }
  
  .no-video-selected,
  .no-videos {
    padding: 40px 16px;
  }
  
  .no-video-icon,
  .no-videos-icon {
    font-size: 3rem;
  }
}
</style>
