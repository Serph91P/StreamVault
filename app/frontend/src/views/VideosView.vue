<template>
  <div class="page-view videos-view">
    <PageHeader
      title="Videos"
      icon="video"
      subtitle="Browse and manage all recorded streams"
    >
      <template #actions>
        <BaseButton
          v-if="selectedVideos.length > 0"
          variant="danger"
          size="sm"
          @click="handleBatchDelete"
        >
          <svg class="icon"><use href="#icon-trash" /></svg>
          Delete ({{ selectedVideos.length }})
        </BaseButton>
        <BaseButton
          :variant="selectMode ? 'primary' : 'outline'"
          size="sm"
          @click="toggleSelectMode"
        >
          <svg class="icon"><use href="#icon-check-square" /></svg>
          {{ selectMode ? 'Cancel' : 'Select' }}
        </BaseButton>
      </template>
    </PageHeader>

    <!-- Library Brief -->
    <section v-if="!isLoading && !fetchError && videos.length > 0" class="videos-brief" aria-labelledby="videos-brief-title">
      <div>
        <p class="eyebrow">Video Library</p>
        <h2 id="videos-brief-title">Browse all recorded streams</h2>
        <p class="brief-copy">
          Search, filter, and sort your video collection. Use grid view for browsing thumbnails or list view for detailed information.
        </p>
      </div>
      <dl class="brief-stats" aria-label="Video library summary">
        <div class="brief-stat total">
          <dt>Recordings</dt>
          <dd>{{ videos.length }}</dd>
        </div>
        <div class="brief-stat">
          <dt>Hours</dt>
          <dd>{{ totalHoursDisplay || '0m' }}</dd>
        </div>
        <div class="brief-stat">
          <dt>Size</dt>
          <dd>{{ totalSizeDisplay || '0 B' }}</dd>
        </div>
        <div v-if="failedCount > 0" class="brief-stat failed">
          <dt>Failed</dt>
          <dd>{{ failedCount }}</dd>
        </div>
        <div v-if="processingCount > 0" class="brief-stat processing">
          <dt>Processing</dt>
          <dd>{{ processingCount }}</dd>
        </div>
      </dl>
    </section>

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
          aria-label="Clear video search"
          title="Clear video search"
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
          aria-label="Show videos as grid"
          title="Show videos as grid"
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
          aria-label="Show videos as list"
          title="Show videos as list"
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
      <label class="sort-control-wrap">
        <svg class="sort-icon" aria-hidden="true">
          <use href="#icon-list-ordered" />
        </svg>
        <span class="sort-label">Sort</span>
        <select v-model="sortBy" class="sort-select" aria-label="Sort videos">
          <option value="newest">Newest First</option>
          <option value="oldest">Oldest First</option>
          <option value="duration-desc">Longest Duration</option>
          <option value="duration-asc">Shortest Duration</option>
          <option value="size-desc">Largest Size</option>
          <option value="size-asc">Smallest Size</option>
          <option value="title">Title A-Z</option>
        </select>
      </label>
    </div>

    <!-- Filter Panel -->
    <Transition name="slide-down">
      <div v-if="showFilters" class="filter-panel">
        <!-- Streamer Filter -->
        <div class="filter-group">
          <label class="filter-label">Streamer</label>
          <select v-model="filterStreamer" class="filter-select" aria-label="Filter videos by streamer">
            <option value="">All Streamers</option>
            <option v-for="streamer in availableStreamers" :key="streamer" :value="streamer">
              {{ streamer }}
            </option>
          </select>
        </div>

        <!-- Date Filter -->
        <div class="filter-group">
          <label class="filter-label">Date</label>
          <select v-model="filterDate" class="filter-select" aria-label="Filter videos by date">
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
          <select v-model="filterDuration" class="filter-select" aria-label="Filter videos by duration">
            <option value="">Any Duration</option>
            <option value="short">Short (&lt; 1h)</option>
            <option value="medium">Medium (1-3h)</option>
            <option value="long">Long (&gt; 3h)</option>
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

    <!-- Filter Chips -->
    <div v-if="!isLoading && !fetchError && activeFiltersCount > 0" class="filter-chips">
      <span v-if="filterStreamer" class="chip" @click="filterStreamer = ''">
        {{ filterStreamer }}
        <svg class="icon"><use href="#icon-x" /></svg>
      </span>
      <span v-if="filterDate !== 'all'" class="chip" @click="filterDate = 'all'">
        {{ filterDateLabel }}
        <svg class="icon"><use href="#icon-x" /></svg>
      </span>
      <span v-if="filterDuration" class="chip" @click="filterDuration = ''">
        {{ durationLabel }}
        <svg class="icon"><use href="#icon-x" /></svg>
      </span>
    </div>

    <!-- Results Count + Summary -->
    <div v-if="!isLoading && !fetchError" class="results-info">
      <span>
        Showing {{ filteredAndSortedVideos.length }}
        {{ filteredAndSortedVideos.length === 1 ? 'video' : 'videos' }}
        <template v-if="videos.length > 0 && filteredAndSortedVideos.length < videos.length">
          of {{ videos.length }}
        </template>
        <template v-if="hasActiveSearchOrFilters">
          <template v-if="searchQuery"> matching "{{ searchQuery }}"</template>
          <template v-else> with current filters</template>
        </template>
      </span>
      <span v-if="selectedVideos.length > 0" class="selected-count">
        {{ selectedVideos.length }} selected
      </span>
    </div>

    <!-- Error State -->
    <EmptyState
      v-if="fetchError"
      title="Failed to Load Videos"
      :description="fetchError"
      icon="alert-circle"
      tone="danger"
      variant="large"
      retry-label="Retry"
      @retry="fetchVideos"
    />

    <!-- Loading State -->
    <div v-else-if="isLoading" class="videos-container" :class="[`view-${viewMode}`, viewMode === 'grid' ? 'grid-recordings' : '']">
      <LoadingSkeleton
        v-for="i in 12"
        :key="i"
        :type="viewMode === 'grid' ? 'video' : 'list-item'"
      />
    </div>

    <!-- Empty State -->
    <EmptyState
      v-else-if="filteredAndSortedVideos.length === 0"
      :title="hasActiveSearchOrFilters ? 'No Results Found' : 'No Videos Yet'"
      :description="hasActiveSearchOrFilters ? emptyResultsDescription : 'Start recording streamers to see their VODs here.'"
      icon="video"
      :action-label="hasActiveSearchOrFilters ? 'Clear Search and Filters' : undefined"
      @action="clearSearchAndFilters"
    />

    <!-- Videos Grid/List -->
    <div v-else class="videos-container" :class="[`view-${viewMode}`, viewMode === 'grid' ? 'grid-recordings' : '']">
      <div
        v-for="video in filteredAndSortedVideos"
        :key="video.id"
        class="video-wrapper"
        :class="{ selected: isSelected(video.id), selectable: selectMode }"
      >
        <!-- Checkbox for Select Mode -->
        <label v-if="selectMode" class="select-checkbox" :aria-label="`Select ${video.title || 'video'}`" @click.stop>
          <input
            type="checkbox"
            :checked="isSelected(video.id)"
            @change="handleSelectionChange(video.id, $event)"
          />
          <span class="checkbox-box" aria-hidden="true">
            <svg class="checkbox-check">
              <use href="#icon-check" />
            </svg>
          </span>
        </label>

        <VideoCard
          :video="video"
          :view-mode="viewMode"
          :disable-navigation="selectMode"
          @play="playVideo"
          @select="toggleSelection(video.id)"
        />
      </div>
    </div>

    <BaseModal
      v-model="showDeleteConfirm"
      title="Delete selected videos?"
      size="sm"
      :close-on-backdrop="!isDeleting"
      :close-on-esc="!isDeleting"
    >
      <p class="confirm-message">
        This will delete {{ selectedVideos.length }} selected {{ selectedVideos.length === 1 ? 'video' : 'videos' }} and queue cleanup of associated files. This action cannot be undone.
      </p>
      <p v-if="deleteError" class="delete-error" role="alert">{{ deleteError }}</p>

      <template #footer>
        <button type="button" class="btn-action btn-secondary" :disabled="isDeleting" @click="showDeleteConfirm = false">
          No, keep videos
        </button>
        <button type="button" class="btn-action btn-danger" :disabled="isDeleting" @click="confirmBatchDelete">
          <svg v-if="!isDeleting" class="icon">
            <use href="#icon-trash" />
          </svg>
          {{ isDeleting ? 'Deleting…' : 'Yes, delete' }}
        </button>
      </template>
    </BaseModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { videoApi } from '@/services/api'
import BaseButton from '@/components/base/BaseButton.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import VideoCard from '@/components/cards/VideoCard.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import PageHeader from '@/components/base/PageHeader.vue'

interface Video {
  id: number
  title?: string | null
  thumbnail_url?: string
  duration?: number
  file_size?: number
  view_count?: number
  viewer_count?: number
  created_at?: string
  recorded_at?: string
  stream_date?: string
  streamer_name?: string
  streamer_id?: number
  category_name?: string
  file_path?: string
  status?: 'recording' | 'processing' | 'ready' | 'failed' | string
  is_recording?: boolean
}

const router = useRouter()

// State
const isLoading = ref(true)
const fetchError = ref('')
const videos = ref<Video[]>([])
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
const showDeleteConfirm = ref(false)
const isDeleting = ref(false)
const deleteError = ref('')

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

// Summary metrics
const totalDuration = computed(() => videos.value.reduce((sum, v) => sum + (v.duration || 0), 0))
const totalHoursDisplay = computed(() => {
  const hours = totalDuration.value / 3600
  if (hours >= 1) return `${Math.round(hours * 10) / 10}h`
  const minutes = Math.round(totalDuration.value / 60)
  return `${minutes}m`
})
const totalSizeDisplay = computed(() => {
  const bytes = videos.value.reduce((sum, v) => sum + (v.file_size || 0), 0)
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes > 0) return `${(bytes / 1024).toFixed(0)} KB`
  return ''
})
const failedCount = computed(() => videos.value.filter(v => v.status === 'failed').length)
const processingCount = computed(() => videos.value.filter(v => v.is_recording || v.status === 'processing' || v.status === 'recording').length)

// Filter chip labels
const filterDateLabel = computed(() => {
  const labels: Record<string, string> = {
    today: 'Today',
    week: 'This Week',
    month: 'This Month',
    custom: 'Custom Range'
  }
  return labels[filterDate.value] || filterDate.value
})
const durationLabel = computed(() => {
  const labels: Record<string, string> = {
    short: 'Short (< 1h)',
    medium: 'Medium (1-3h)',
    long: 'Long (> 3h)'
  }
  return labels[filterDuration.value] || filterDuration.value
})
const hasActiveSearchOrFilters = computed(() => Boolean(searchQuery.value || activeFiltersCount.value > 0))
const emptyResultsDescription = computed(() => (
  searchQuery.value
    ? `No videos match '${searchQuery.value}'. Try adjusting your search or filters.`
    : 'No videos match the selected filters. Try clearing one or more filters.'
))

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
      const date = new Date(v.recorded_at || v.stream_date || v.created_at || '')
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
        const getDate = (v: Video) => new Date(v.recorded_at || v.stream_date || v.created_at || '').getTime()
        return getDate(b) - getDate(a)
      })
      break
    case 'oldest':
      sorted.sort((a, b) => {
        const getDate = (v: Video) => new Date(v.recorded_at || v.stream_date || v.created_at || '').getTime()
        return getDate(a) - getDate(b)
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
  fetchError.value = ''
  try {
    const response = await videoApi.getAll()

    // Backend returns array directly (not wrapped in { data: [] })
    videos.value = Array.isArray(response) ? response : (response.data || [])
  } catch (error: any) {
    console.error('[VideosView] Failed to fetch videos:', error)
    fetchError.value = error?.message || 'An unexpected error occurred while loading videos.'
    videos.value = []
  } finally {
    isLoading.value = false
  }
}

// Actions
function playVideo(video: Video) {
  if (!video.streamer_id || !video.id || video.status === 'failed') return

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
    showDeleteConfirm.value = false
    deleteError.value = ''
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

function handleSelectionChange(id: number, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  const isAlreadySelected = selectedVideos.value.includes(id)

  if (checked && !isAlreadySelected) {
    selectedVideos.value.push(id)
  } else if (!checked && isAlreadySelected) {
    selectedVideos.value = selectedVideos.value.filter(videoId => videoId !== id)
  }
}

function handleBatchDelete() {
  if (selectedVideos.value.length === 0) return
  deleteError.value = ''
  showDeleteConfirm.value = true
}

async function confirmBatchDelete() {
  if (selectedVideos.value.length === 0 || isDeleting.value) return

  const idsToDelete = [...selectedVideos.value]
  isDeleting.value = true
  deleteError.value = ''

  try {
    await videoApi.deleteMultiple(idsToDelete)
    videos.value = videos.value.filter(video => !idsToDelete.includes(video.id))
    selectedVideos.value = []
    selectMode.value = false
    showDeleteConfirm.value = false
  } catch (error: any) {
    console.error('[VideosView] Failed to delete selected videos:', error)
    deleteError.value = error?.message || 'Failed to delete selected videos. Please try again.'
  } finally {
    isDeleting.value = false
  }
}

function clearFilters() {
  filterStreamer.value = ''
  filterDate.value = 'all'
  filterDuration.value = ''
}

function clearSearchAndFilters() {
  searchQuery.value = ''
  clearFilters()
}

// Initialize
onMounted(() => {
  fetchVideos()
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.videos-view {
  // .page-view provides padding/sizing via global styles
  // Page-specific overrides only
}

.videos-brief {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(360px, 0.85fr);
  gap: var(--spacing-6);
  align-items: center;
  margin-bottom: var(--spacing-5);
  padding: var(--spacing-6);
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(var(--primary-500-rgb), 0.2), transparent 34%),
    linear-gradient(135deg, rgba(var(--primary-500-rgb), 0.12), rgba(var(--accent-500-rgb), 0.08));
  border: 1px solid rgba(var(--primary-500-rgb), 0.2);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-lg);

  h2 {
    margin: var(--spacing-1) 0 var(--spacing-2);
    color: var(--text-primary);
    font-size: clamp(var(--text-xl), 3vw, var(--text-3xl));
    line-height: v.$leading-tight;
  }
}

.eyebrow {
  margin: 0;
  color: var(--primary-color);
  font-size: var(--text-xs);
  font-weight: v.$font-bold;
  letter-spacing: v.$tracking-widest;
  text-transform: uppercase;
}

.brief-copy {
  max-width: 58ch;
  margin: 0;
  color: var(--text-secondary);
  line-height: v.$leading-relaxed;
}

.brief-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--spacing-3);
  margin: 0;
}

.brief-stat {
  min-width: 120px;
  padding: var(--spacing-4);
  background: rgba(var(--background-card-rgb), 0.72);
  border: 1px solid rgba(var(--border-color-rgb), 0.8);
  border-radius: var(--radius-xl);
  backdrop-filter: blur(var(--glass-blur-sm));
  -webkit-backdrop-filter: blur(var(--glass-blur-sm));

  dt {
    margin: 0;
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    font-weight: v.$font-semibold;
    text-transform: uppercase;
    letter-spacing: v.$tracking-wide;
  }

  dd {
    margin: var(--spacing-1) 0 0;
    color: var(--text-primary);
    font-size: var(--text-2xl);
    font-weight: v.$font-bold;
    line-height: 1;
  }

  &.total dd {
    color: var(--primary-color);
  }

  &.failed dd {
    color: var(--danger-color);
  }

  &.processing dd {
    color: var(--warning-color);
  }
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
    background: v.$primary-700;
    color: white;

    &:hover {
      background: v.$primary-800;
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
        background: var(--primary-50);
        color: var(--primary-700);
      }
    }
  }

  &.btn-danger {
    background: v.$danger-700;
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
  padding: var(--spacing-3);
  flex-wrap: wrap;
  align-items: center;
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
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
  min-height: 44px;
}

.toggle-btn {
  width: 40px;
  min-width: 40px;
  min-height: 36px;
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
    background: v.$primary-700;

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
    background: v.$primary-700;
    color: white;
    font-size: var(--text-xs);
    font-weight: v.$font-bold;
    border-radius: var(--radius-full);
  }
}

.sort-control-wrap {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  min-height: 44px;
  padding: 0 var(--spacing-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--background-card);
  cursor: pointer;
}

.sort-icon {
  width: 18px;
  height: 18px;
  color: var(--text-secondary);
  stroke: currentColor;
  fill: none;
}

.sort-label {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
}

.sort-select {
  min-width: 156px;
  min-height: 42px;
  margin: 0;
  padding: 0 var(--spacing-6) 0 0;
  appearance: none;
  background: transparent;
  border: 0;
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
}

.sort-select:focus {
  outline: none;
}

.sort-control-wrap:focus-within {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(var(--primary-500-rgb), 0.1);
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

// Filter Chips
.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
  margin-bottom: var(--spacing-3);

  .chip {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-1);
    padding: var(--spacing-1) var(--spacing-3);
    background: rgba(var(--primary-500-rgb), 0.12);
    border: 1px solid rgba(var(--primary-500-rgb), 0.25);
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
    font-weight: v.$font-medium;
    color: var(--text-primary);
    cursor: pointer;
    transition: all v.$duration-200 v.$ease-out;

    .icon {
      width: 14px;
      height: 14px;
      stroke: currentColor;
      fill: none;
    }

    &:hover {
      background: rgba(var(--danger-500-rgb), 0.12);
      border-color: rgba(var(--danger-500-rgb), 0.35);
      color: var(--danger-color);
    }
  }
}

// Results Info
.results-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-3);
  width: fit-content;
  max-width: 100%;
  margin: 0 0 var(--spacing-4) auto;
  padding: var(--spacing-2) var(--spacing-3);
  background: rgba(var(--background-card-rgb, 20, 22, 29), 0.72);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  color: var(--text-secondary);

  .selected-count {
    padding: var(--spacing-1) var(--spacing-2);
    background: rgba(var(--primary-700-rgb), 0.16);
    color: var(--text-primary);
    border-radius: var(--radius-md);
    font-weight: v.$font-semibold;
    white-space: nowrap;
  }
}

// Videos Container
.videos-container {
  &.view-grid {
    align-items: stretch;
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

  &.selectable {
    cursor: pointer;
  }

  &.selected {
    outline: 2px solid rgba(var(--primary-500-rgb), 0.75);
    outline-offset: 3px;
    border-radius: var(--radius-xl);

    :deep(.video-card) {
      box-shadow: 0 0 0 1px rgba(var(--primary-500-rgb), 0.3), 0 12px 32px rgba(var(--primary-500-rgb), 0.18);
    }
  }
}

.select-checkbox {
  position: absolute;
  top: var(--spacing-2);
  left: var(--spacing-2);
  z-index: 10;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(var(--glass-blur-md));
  -webkit-backdrop-filter: blur(var(--glass-blur-md));
  border: none;
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22);

  &:hover {
    background: rgba(15, 23, 42, 0.78);
    transform: scale(1.05);
  }

  input[type="checkbox"] {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    opacity: 0;
    cursor: pointer;
    margin: 0;
  }

  .checkbox-box {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid rgba(255, 255, 255, 0.85);
    border-radius: var(--radius-md);
    background: rgba(255, 255, 255, 0.1);
    color: white;
    transition: all v.$duration-200 v.$ease-out;
  }

  .checkbox-check {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
    opacity: 0;
    transform: scale(0.75);
    transition: all v.$duration-150 v.$ease-out;
  }

  input[type="checkbox"]:checked + .checkbox-box {
    border-color: var(--primary-color);
    background: var(--primary-color);
  }

  input[type="checkbox"]:checked + .checkbox-box .checkbox-check {
    opacity: 1;
    transform: scale(1);
  }

  input[type="checkbox"]:focus-visible + .checkbox-box {
    outline: 2px solid white;
    outline-offset: 3px;
  }

  // Mobile: Larger touch target
  @include m.respond-below('md') {  // < 768px
    width: 52px;
    height: 52px;
  }
}

.confirm-message {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.delete-error {
  margin: var(--spacing-4) 0 0;
  padding: var(--spacing-3);
  border-radius: var(--radius-md);
  background: rgba(var(--danger-500-rgb), 0.1);
  color: var(--danger-color);
  font-size: var(--text-sm);
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
  .videos-brief {
    grid-template-columns: 1fr;
  }

  .brief-stats {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .controls-bar {
    flex-wrap: wrap;
    align-items: center;
  }

  .search-box {
    order: -1;
    width: 100%;
    flex-basis: 100%;
    min-width: unset;
  }
}

@include m.respond-below('sm') {  // < 640px
  .videos-view {
    padding: var(--spacing-4) var(--spacing-3);
  }

  .videos-brief {
    padding: var(--spacing-4);
    margin-bottom: var(--spacing-4);
  }

  .brief-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .brief-stat {
    min-width: 0;
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

  .results-info {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
