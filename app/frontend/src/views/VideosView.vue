<template>
  <div class="videos-view">
    <!-- Header with Actions -->
    <div class="view-header">
      <div class="header-content">
        <h1 class="page-title">
          <svg class="icon-title">
            <use href="#icon-video" />
          </svg>
          Videos
        </h1>
        <p class="page-subtitle">Browse and manage all recorded streams</p>
      </div>

      <div class="header-actions">
        <button
          v-if="selectedVideos.length > 0"
          @click="handleBatchDelete"
          class="btn-action btn-danger"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-trash" />
          </svg>
          Delete ({{ selectedVideos.length }})
        </button>
        <button
          @click="toggleSelectMode"
          class="btn-action"
          :class="selectMode ? 'btn-primary' : 'btn-secondary'"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-check-square" />
          </svg>
          {{ selectMode ? 'Cancel' : 'Select' }}
        </button>
      </div>
    </div>

    <!-- Search and Filters -->
    <div class="controls-bar">
      <!-- Search -->
      <div class="search-box">
        <svg class="icon">
          <use href="#icon-search" />
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search videos by title or streamer..."
          class="search-input"
        />
        <button
          v-if="searchQuery"
          @click="searchQuery = ''"
          class="clear-btn"
        >
          <svg class="icon">
            <use href="#icon-x" />
          </svg>
        </button>
      </div>

      <!-- View Toggle -->
      <div class="view-toggle">
        <button
          @click="viewMode = 'grid'"
          :class="{ active: viewMode === 'grid' }"
          class="toggle-btn"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-grid" />
          </svg>
        </button>
        <button
          @click="viewMode = 'list'"
          :class="{ active: viewMode === 'list' }"
          class="toggle-btn"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-list" />
          </svg>
        </button>
      </div>

      <!-- Filters Button -->
      <button @click="showFilters = !showFilters" class="filters-btn" v-ripple>
        <svg class="icon">
          <use href="#icon-filter" />
        </svg>
        Filters
        <span v-if="activeFiltersCount > 0" class="filter-badge">
          {{ activeFiltersCount }}
        </span>
      </button>

      <!-- Sort Dropdown -->
      <select v-model="sortBy" class="sort-select">
        <option value="newest">Newest First</option>
        <option value="oldest">Oldest First</option>
        <option value="duration-desc">Longest Duration</option>
        <option value="duration-asc">Shortest Duration</option>
        <option value="size-desc">Largest Size</option>
        <option value="size-asc">Smallest Size</option>
        <option value="title">Title A-Z</option>
      </select>
    </div>

    <!-- Filter Panel -->
    <Transition name="slide-down">
      <div v-if="showFilters" class="filter-panel">
        <!-- Streamer Filter -->
        <div class="filter-group">
          <label class="filter-label">Streamer</label>
          <select v-model="filterStreamer" class="filter-select">
            <option value="">All Streamers</option>
            <option v-for="streamer in availableStreamers" :key="streamer" :value="streamer">
              {{ streamer }}
            </option>
          </select>
        </div>

        <!-- Date Filter -->
        <div class="filter-group">
          <label class="filter-label">Date</label>
          <select v-model="filterDate" class="filter-select">
            <option value="all">All Time</option>
            <option value="today">Today</option>
            <option value="week">This Week</option>
            <option value="month">This Month</option>
            <option value="custom">Custom Range</option>
          </select>
        </div>

        <!-- Duration Filter -->
        <div class="filter-group">
          <label class="filter-label">Duration</label>
          <select v-model="filterDuration" class="filter-select">
            <option value="">Any Duration</option>
            <option value="short">Short (< 1h)</option>
            <option value="medium">Medium (1-3h)</option>
            <option value="long">Long (> 3h)</option>
          </select>
        </div>

        <!-- Clear Filters -->
        <button @click="clearFilters" class="clear-filters-btn" v-ripple>
          <svg class="icon">
            <use href="#icon-x" />
          </svg>
          Clear All
        </button>
      </div>
    </Transition>

    <!-- Results Count -->
    <div class="results-info">
      <span v-if="!isLoading">
        {{ filteredAndSortedVideos.length }} {{ filteredAndSortedVideos.length === 1 ? 'video' : 'videos' }}
      </span>
      <span v-if="selectedVideos.length > 0" class="selected-count">
        {{ selectedVideos.length }} selected
      </span>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="videos-container" :class="`view-${viewMode}`">
      <LoadingSkeleton
        v-for="i in 12"
        :key="i"
        :type="viewMode === 'grid' ? 'video' : 'list-item'"
      />
    </div>

    <!-- Empty State -->
    <EmptyState
      v-else-if="filteredAndSortedVideos.length === 0"
      :title="searchQuery ? 'No Results Found' : 'No Videos Yet'"
      :description="searchQuery ? `No videos match '${searchQuery}'` : 'Start recording streamers to see their VODs here.'"
      icon="video"
      action-label="Clear Search"
      v-if="searchQuery"
      @action="searchQuery = ''"
    />

    <!-- Videos Grid/List -->
    <div v-else class="videos-container" :class="`view-${viewMode}`">
      <div
        v-for="video in filteredAndSortedVideos"
        :key="video.id"
        class="video-wrapper"
        :class="{ selected: isSelected(video.id) }"
      >
        <!-- Checkbox for Select Mode -->
        <div v-if="selectMode" class="select-checkbox" @click.stop="toggleSelection(video.id)">
          <input
            type="checkbox"
            :checked="isSelected(video.id)"
            @change="toggleSelection(video.id)"
          />
        </div>

        <VideoCard
          :video="video"
          :view-mode="viewMode"
          @click="selectMode ? toggleSelection(video.id) : playVideo(video)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { videoApi } from '@/services/api'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import VideoCard from '@/components/cards/VideoCard.vue'

const router = useRouter()

// State
const isLoading = ref(true)
const videos = ref<any[]>([])
const searchQuery = ref('')
const viewMode = ref<'grid' | 'list'>('grid')
const sortBy = ref('newest')
const showFilters = ref(false)

// Filters
const filterStreamer = ref('')
const filterDate = ref('all')
const filterDuration = ref('')

// Selection
const selectMode = ref(false)
const selectedVideos = ref<number[]>([])

// Available filter options
const availableStreamers = computed(() => {
  const streamers = videos.value
    .map(v => v.streamer_name)
    .filter((name, index, arr) => name && arr.indexOf(name) === index)
    .sort()
  return streamers
})

// Active filters count
const activeFiltersCount = computed(() => {
  let count = 0
  if (filterStreamer.value) count++
  if (filterDate.value !== 'all') count++
  if (filterDuration.value) count++
  return count
})

// Filtered and sorted videos
const filteredAndSortedVideos = computed(() => {
  let filtered = [...videos.value]

  // Search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(v =>
      v.title?.toLowerCase().includes(query) ||
      v.streamer_name?.toLowerCase().includes(query)
    )
  }

  // Streamer filter
  if (filterStreamer.value) {
    filtered = filtered.filter(v => v.streamer_name === filterStreamer.value)
  }

  // Date filter
  if (filterDate.value !== 'all') {
    const now = new Date()
    const filterTime = new Date()

    switch (filterDate.value) {
      case 'today':
        filterTime.setHours(0, 0, 0, 0)
        break
      case 'week':
        filterTime.setDate(now.getDate() - 7)
        break
      case 'month':
        filterTime.setMonth(now.getMonth() - 1)
        break
    }

    filtered = filtered.filter(v => {
      const date = new Date(v.stream_date || v.created_at)
      return date >= filterTime
    })
  }

  // Duration filter
  if (filterDuration.value) {
    filtered = filtered.filter(v => {
      const duration = v.duration || 0
      switch (filterDuration.value) {
        case 'short':
          return duration < 3600
        case 'medium':
          return duration >= 3600 && duration <= 10800
        case 'long':
          return duration > 10800
        default:
          return true
      }
    })
  }

  // Sorting
  const sorted = [...filtered]
  switch (sortBy.value) {
    case 'newest':
      sorted.sort((a, b) => {
        const dateA = new Date(a.stream_date || a.created_at).getTime()
        const dateB = new Date(b.stream_date || b.created_at).getTime()
        return dateB - dateA
      })
      break
    case 'oldest':
      sorted.sort((a, b) => {
        const dateA = new Date(a.stream_date || a.created_at).getTime()
        const dateB = new Date(b.stream_date || b.created_at).getTime()
        return dateA - dateB
      })
      break
    case 'duration-desc':
      sorted.sort((a, b) => (b.duration || 0) - (a.duration || 0))
      break
    case 'duration-asc':
      sorted.sort((a, b) => (a.duration || 0) - (b.duration || 0))
      break
    case 'size-desc':
      sorted.sort((a, b) => (b.file_size || 0) - (a.file_size || 0))
      break
    case 'size-asc':
      sorted.sort((a, b) => (a.file_size || 0) - (b.file_size || 0))
      break
    case 'title':
      sorted.sort((a, b) => (a.title || '').localeCompare(b.title || ''))
      break
  }

  return sorted
})

// Fetch videos
async function fetchVideos() {
  isLoading.value = true
  try {
    console.log('[VideosView] Fetching all videos...')
    const response = await videoApi.getAll()
    console.log('[VideosView] API response:', response)
    
    // Backend returns array directly (not wrapped in { data: [] })
    videos.value = Array.isArray(response) ? response : (response.data || [])
    console.log('[VideosView] Loaded videos count:', videos.value.length)
    
    if (videos.value.length > 0) {
      console.log('[VideosView] Sample video:', videos.value[0])
    }
  } catch (error: any) {
    console.error('[VideosView] Failed to fetch videos:', error)
    console.error('[VideosView] Error details:', {
      message: error.message,
      status: error.response?.status,
      data: error.response?.data
    })
    videos.value = []
  } finally {
    isLoading.value = false
  }
}

// Actions
function playVideo(video: any) {
  // Navigate to video player with correct route parameters
  // Route expects: /streamer/:streamerId/stream/:streamId/watch
  router.push({
    name: 'VideoPlayer',
    params: {
      streamerId: video.streamer_id,
      streamId: video.id  // video.id is actually the stream_id
    },
    query: {
      title: video.title || `Stream ${video.id}`,
      streamerName: video.streamer_name
    }
  })
}

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) {
    selectedVideos.value = []
  }
}

function isSelected(id: number) {
  return selectedVideos.value.includes(id)
}

function toggleSelection(id: number) {
  const index = selectedVideos.value.indexOf(id)
  if (index > -1) {
    selectedVideos.value.splice(index, 1)
  } else {
    selectedVideos.value.push(id)
  }
}

function handleBatchDelete() {
  console.log('Batch delete:', selectedVideos.value)
  // TODO: Implement batch delete
}

function clearFilters() {
  filterStreamer.value = ''
  filterDate.value = 'all'
  filterDuration.value = ''
}

// Watch for filter changes to auto-close panel
watch([filterStreamer, filterDate, filterDuration], () => {
  if (activeFiltersCount.value > 0) {
    // Keep panel open while actively filtering
  }
})

// Initialize
onMounted(() => {
  fetchVideos()
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.videos-view {
  padding: var(--spacing-6) var(--spacing-4);
  max-width: 1600px;
  margin: 0 auto;
  min-height: 100vh;
}

// Header
.view-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--spacing-6);
  gap: var(--spacing-4);
  flex-wrap: wrap;
}

.header-content {
  flex: 1;
  min-width: 250px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  font-size: var(--text-3xl);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-2) 0;

  .icon-title {
    width: 32px;
    height: 32px;
    stroke: var(--primary-color);
    fill: none;
  }
}

.page-subtitle {
  font-size: var(--text-base);
  color: var(--text-secondary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: var(--spacing-3);
  flex-wrap: wrap;
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  border-radius: var(--radius-lg);
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  border: none;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
  }

  &.btn-primary {
    background: var(--primary-color);
    color: white;

    &:hover {
      background: var(--primary-600);
      box-shadow: var(--shadow-md);
    }
  }

  &.btn-secondary {
    background: var(--background-card);
    color: var(--text-primary);
    border: 1px solid var(--border-color);

    &:hover {
      background: rgba(var(--primary-500-rgb), 0.1);
      border-color: var(--primary-color);
      color: var(--primary-color);
      
      [data-theme="light"] & {
        background: var(--primary-50, #e0f2f1);
        color: var(--primary-700, #0f766e);
      }
    }
  }

  &.btn-danger {
    background: var(--danger-color);
    color: white;

    &:hover {
      background: var(--danger-600);
      box-shadow: var(--shadow-md);
    }
  }
}

// Controls Bar
.controls-bar {
  display: flex;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-4);
  flex-wrap: wrap;
  align-items: center;
}

.search-box {
  position: relative;
  flex: 1;
  min-width: 280px;

  .icon {
    position: absolute;
    left: var(--spacing-3);
    top: 50%;
    transform: translateY(-50%);
    width: 20px;
    height: 20px;
    pointer-events: none;
    z-index: 10;
  }

  .search-input {
    width: 100%;
    padding: var(--spacing-3) var(--spacing-10) var(--spacing-3) var(--spacing-10);
    background: var(--background-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    color: var(--text-primary);
    font-size: var(--text-sm);
    transition: all v.$duration-200 v.$ease-out;

    &:focus {
      outline: none;
      border-color: var(--primary-color);
      box-shadow: 0 0 0 3px rgba(var(--primary-500-rgb), 0.1);
    }

    &::placeholder {
      color: var(--text-tertiary);
    }
  }

  .clear-btn {
    position: absolute;
    right: var(--spacing-2);
    top: 50%;
    transform: translateY(-50%);
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all v.$duration-200 v.$ease-out;

    .icon {
      width: 16px;
      height: 16px;
      stroke: var(--text-secondary);
      fill: none;
    }

    &:hover {
      background: rgba(var(--danger-500-rgb), 0.1);

      .icon {
        stroke: var(--danger-color);
      }
    }
  }
}

.view-toggle {
  display: flex;
  gap: var(--spacing-1);
  background: var(--background-card);
  border-radius: var(--radius-lg);
  padding: var(--spacing-1);
  border: 1px solid var(--border-color);
}

.toggle-btn {
  padding: var(--spacing-2);
  background: transparent;
  border: none;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 20px;
    height: 20px;
    stroke: var(--text-secondary);
    fill: none;
  }

  &.active {
    background: var(--primary-color);

    .icon {
      stroke: white;
    }
  }

  &:hover:not(.active) {
    background: rgba(var(--primary-500-rgb), 0.1);
  }
}

.filters-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
  }

  &:hover {
    border-color: var(--primary-color);
    color: var(--primary-color);
  }

  .filter-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 20px;
    padding: 0 var(--spacing-1);
    background: var(--primary-color);
    color: white;
    font-size: var(--text-xs);
    font-weight: v.$font-bold;
    border-radius: var(--radius-full);
  }
}

.sort-select {
  padding: var(--spacing-3) var(--spacing-4);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &:hover {
    border-color: var(--primary-color);
  }

  &:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

// Filter Panel
.filter-panel {
  display: flex;
  gap: var(--spacing-4);
  padding: var(--spacing-5);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  margin-bottom: var(--spacing-5);
  flex-wrap: wrap;
}

.filter-group {
  flex: 1;
  min-width: 180px;
}

.filter-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-2);
}

.filter-select {
  width: 100%;
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &:hover {
    border-color: var(--primary-color);
  }

  &:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

.clear-filters-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  align-self: flex-end;

  .icon {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
  }

  &:hover {
    border-color: var(--danger-color);
    color: var(--danger-color);
  }
}

// Results Info
.results-info {
  display: flex;
  gap: var(--spacing-3);
  align-items: center;
  margin-bottom: var(--spacing-4);
  font-size: var(--text-sm);
  color: var(--text-secondary);

  .selected-count {
    padding: var(--spacing-1) var(--spacing-2);
    background: rgba(var(--primary-500-rgb), 0.1);
    color: var(--primary-color);
    border-radius: var(--radius-md);
    font-weight: v.$font-semibold;
  }
}

// Videos Container
.videos-container {
  &.view-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--spacing-5);
  }

  &.view-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
  }
}

.video-wrapper {
  position: relative;
  transition: all v.$duration-200 v.$ease-out;

  &.selected {
    outline: 2px solid var(--primary-color);
    outline-offset: 4px;
    border-radius: var(--radius-xl);
  }
}

.select-checkbox {
  position: absolute;
  top: var(--spacing-3);
  left: var(--spacing-3);
  z-index: 10;
  min-width: 32px;
  min-height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &:hover {
    background: rgba(0, 0, 0, 0.8);
    border-color: var(--primary-color);
    transform: scale(1.05);
  }

  input[type="checkbox"] {
    width: 20px;
    height: 20px;
    cursor: pointer;
    accent-color: var(--primary-color);
  }

  // Mobile: Larger touch target
  @include m.respond-below('md') {  // < 768px
    min-width: 44px;
    min-height: 44px;
    
    input[type="checkbox"] {
      width: 24px;
      height: 24px;
    }
  }
}

// Transitions
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all v.$duration-300 v.$ease-out;
  overflow: hidden;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
  margin-bottom: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.slide-down-enter-to,
.slide-down-leave-from {
  opacity: 1;
  max-height: 500px;
}

// Responsive - Use SCSS mixins for breakpoints
@include m.respond-below('lg') {  // < 1024px
  .controls-bar {
    flex-direction: column;
    align-items: stretch;
  }

}

@include m.respond-below('sm') {  // < 640px
  .videos-view {
    padding: var(--spacing-4) var(--spacing-3);
  }

  .page-title {
    font-size: var(--text-2xl);
  }

  .header-actions {
    width: 100%;

    .btn-action {
      flex: 1;
      justify-content: center;
      min-height: 44px;  // Touch-friendly
    }
  }
  
  // Filter and sort controls
  .filters-btn,
  .sort-select {
    min-height: 44px;  // Touch-friendly
    font-size: var(--text-base);  // Larger for readability
  }
  
  .filter-panel {
    padding: var(--spacing-4);
    gap: var(--spacing-3);
  }
  
  .filter-select {
    min-height: 44px;  // Touch-friendly
    font-size: 16px;  // Prevent iOS zoom
  }
  
  .clear-filters-btn {
    width: 100%;  // Full width on mobile
    min-height: 44px;
    justify-content: center;
  }
  
  // Search and view controls
  .search-box {
    order: -1;  // Move search to top on mobile
    width: 100%;
    margin-bottom: var(--spacing-3);
  }
  
  .view-toggle,
  .filters-btn,
  .sort-select {
    flex: 1;  // Equal width buttons
  }
  
  .filter-panel {
    flex-direction: column;  // Stack vertically on mobile
  }
  
  .filter-group {
    width: 100%;
    
    label {
      font-size: var(--text-sm);
      font-weight: 600;
    }
    
    select {
      width: 100%;
    }
  }

  .videos-container.view-grid {
    grid-template-columns: 1fr;
  }
}
</style>
