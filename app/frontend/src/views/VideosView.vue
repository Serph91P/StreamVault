<template>
  <div class="page-view videos-view">
    <PageHeader
      title="Aufzeichnungen"
      icon="video"
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
          aria-label="Search videos"
        />
        <BaseIconButton
          v-if="searchQuery"
          @click="searchQuery = ''"
          class="clear-btn"
          label="Clear video search"
          title="Clear video search"
        >
          <svg class="icon">
            <use href="#icon-x" />
          </svg>
        </BaseIconButton>
      </div>

      <!-- View Toggle -->
      <div class="view-toggle">
        <BaseIconButton
          @click="viewMode = 'grid'"
          :class="{ active: viewMode === 'grid' }"
          class="toggle-btn"
          label="Show videos as grid"
          :aria-pressed="viewMode === 'grid'"
          title="Show videos as grid"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-grid" />
          </svg>
        </BaseIconButton>
        <BaseIconButton
          @click="viewMode = 'list'"
          :class="{ active: viewMode === 'list' }"
          class="toggle-btn"
          label="Show videos as list"
          :aria-pressed="viewMode === 'list'"
          title="Show videos as list"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-list" />
          </svg>
        </BaseIconButton>
      </div>

      <!-- Filters Button -->
      <button @click="showFilters = !showFilters" class="filters-btn" :aria-expanded="showFilters" aria-controls="video-filters" v-ripple>
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
        <span class="sort-value">{{ currentSortLabel }}</span>
        <select v-model="sortBy" class="sort-select" aria-label="Sort videos">
          <option v-for="option in sortOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
    </div>

    <!-- Filter Panel (grid-rows collapse: animating max-height re-layouts
         every frame and stutters; 0fr->1fr interpolates smoothly) -->
    <div class="filter-collapse" :class="{ open: showFilters }" :inert="!showFilters">
      <div id="video-filters" class="filter-panel">
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

        <div class="filter-group">
          <label class="filter-label">Category</label>
          <select v-model="filterCategory" class="filter-select" aria-label="Filter videos by category">
            <option value="">All Categories</option>
            <option v-for="category in summary.categories" :key="category" :value="category">{{ category }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label class="filter-label">Recording status</label>
          <select v-model="filterRecording" class="filter-select" aria-label="Filter videos by recording status">
            <option value="">All Recordings</option>
            <option value="true">Active</option>
            <option value="false">Finished</option>
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
    </div>

    <!-- Filter Chips -->
    <div v-if="!isLoading && !fetchError && activeFiltersCount > 0" class="filter-chips">
      <button
        v-if="filterStreamer"
        type="button"
        class="chip"
        :aria-label="`Remove ${filterStreamer} filter`"
        @click="filterStreamer = ''"
      >
        {{ filterStreamer }}
        <svg class="icon"><use href="#icon-x" /></svg>
      </button>
      <button
        v-if="filterDate !== 'all'"
        type="button"
        class="chip"
        :aria-label="`Remove ${filterDateLabel} filter`"
        @click="filterDate = 'all'"
      >
        {{ filterDateLabel }}
        <svg class="icon"><use href="#icon-x" /></svg>
      </button>
      <button
        v-if="filterDuration"
        type="button"
        class="chip"
        :aria-label="`Remove ${durationLabel} filter`"
        @click="filterDuration = ''"
      >
        {{ durationLabel }}
        <svg class="icon"><use href="#icon-x" /></svg>
      </button>
    </div>

    <!-- Results Count + Summary -->
    <div v-if="!isLoading && !fetchError" class="results-info">
      <span>
        Showing {{ filteredAndSortedVideos.length }}
        {{ filteredAndSortedVideos.length === 1 ? 'video' : 'videos' }}
        <template v-if="total > 0 && filteredAndSortedVideos.length < total">
          of {{ total }}
        </template>
        <template v-if="hasActiveSearchOrFilters">
          <template v-if="searchQuery"> matching "{{ searchQuery }}"</template>
          <template v-else> with current filters</template>
        </template>
      </span>
      <span v-if="selectedVideos.length > 0" class="selected-count">
        {{ selectedVideos.length }} selected
      </span>
      <span v-if="selectMode">Selection is limited to this page.</span>
    </div>

    <p v-if="!isLoading && catalogIndex && (catalogIndex.pending || catalogIndex.error || catalogIndex.missing)" role="status">
      Library snapshot: {{ catalogIndex.pending }} pending, {{ catalogIndex.error }} indexing errors,
      {{ catalogIndex.missing }} missing files. Counts describe indexed media.
      <BaseButton size="sm" :disabled="isDeleting" @click="fetchVideos">Refresh library</BaseButton>
    </p>

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
      :title="catalogIndex?.pending ? 'Indexing Library' : hasActiveSearchOrFilters ? 'No Results Found' : 'No Videos Yet'"
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
          :origin="getVideoOrigin()"
          :disable-navigation="selectMode"
          @play="playVideo"
          @select="toggleSelection(video.id)"
        />
      </div>
    </div>

    <nav v-if="!fetchError && (page > 1 || hasMore)" aria-label="Video library pages" class="results-info">
      <BaseButton aria-label="Previous video page" :disabled="isLoading || isDeleting || page <= 1" @click="setPage(page - 1)">Previous</BaseButton>
      <span aria-live="polite">Page {{ page }}</span>
      <BaseButton aria-label="Next video page" :disabled="isLoading || isDeleting || !hasMore" @click="setPage(page + 1)">Next</BaseButton>
    </nav>

    <section v-if="!isLoading && !fetchError && summary.total > 0" class="videos-brief" aria-label="Video library summary">
      <dl class="brief-stats">
        <div class="brief-stat total"><dt>Recordings</dt><dd>{{ summary.total }}</dd></div>
        <div class="brief-stat"><dt>Hours</dt><dd>{{ totalHoursDisplay || '0m' }}</dd></div>
        <div class="brief-stat"><dt>Size</dt><dd>{{ totalSizeDisplay || '0 B' }}</dd></div>
        <div v-if="failedCount > 0" class="brief-stat failed"><dt>Failed</dt><dd>{{ failedCount }}</dd></div>
        <div v-if="processingCount > 0" class="brief-stat processing"><dt>Processing</dt><dd>{{ processingCount }}</dd></div>
      </dl>
    </section>

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
        <button type="button" class="btn-action btn-danger" :disabled="isDeleting || isLoading || !!fetchError || selectedVideos.length === 0" @click="confirmBatchDelete">
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
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import type { CatalogVideo as Video, VideoCatalogPage, VideoCatalogQuery } from '@/types/video'
import { appStorage } from '@/services/storage'
import { useRoute, useRouter } from 'vue-router'
import { prepareVideoReturn, restoreVideoReturnScroll } from '@/composables/useNavigation'
import { videoApi } from '@/services/api'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIconButton from '@/components/base/BaseIconButton.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import VideoCard from '@/components/cards/VideoCard.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import PageHeader from '@/components/base/PageHeader.vue'

const router = useRouter()
const route = useRoute()

// State
const isLoading = ref(true)
const fetchError = ref('')
const videos = ref<Video[]>([])
const stringQuery = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] : fallback
const searchQuery = ref(stringQuery('q'))
const page = ref(Math.max(1, Number.parseInt(stringQuery('page', '1'), 10) || 1))
const pageSize = 50
const total = ref(0)
const hasMore = ref(false)
const summary = ref<VideoCatalogPage['summary']>({ total: 0, file_size: 0, duration: 0, streamers: [], categories: [] })
const catalogIndex = ref<VideoCatalogPage['index'] | null>(null)
let generation = 0
let request: AbortController | null = null
let searchTimer: ReturnType<typeof setTimeout> | undefined
// Grid/list choice survives reloads
const viewMode = ref<'grid' | 'list'>(stringQuery('view', appStorage.getViewMode('videos') ?? 'grid') === 'list' ? 'list' : 'grid')
watch(viewMode, (mode) => appStorage.setViewMode('videos', mode))
const sortBy = ref(stringQuery('sort', 'newest'))
const sortOptions = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'duration-desc', label: 'Longest Duration' },
  { value: 'duration-asc', label: 'Shortest Duration' },
  { value: 'size-desc', label: 'Largest Size' },
  { value: 'size-asc', label: 'Smallest Size' },
  { value: 'title', label: 'Title A-Z' },
  { value: 'streamer', label: 'Streamer A-Z' }
]
const currentSortLabel = computed(() =>
  sortOptions.find((option) => option.value === sortBy.value)?.label ?? 'Newest First'
)
const showFilters = ref(false)

// Filters
const filterStreamer = ref(stringQuery('streamer'))
const filterDate = ref(stringQuery('date', 'all'))
const filterDuration = ref(stringQuery('duration'))
const filterCategory = ref(stringQuery('category'))
const filterRecording = ref(stringQuery('recording'))

// Selection
const selectMode = ref(false)
const selectedVideos = ref<number[]>([])
const showDeleteConfirm = ref(false)
const isDeleting = ref(false)
const deleteError = ref('')

// Available filter options
const availableStreamers = computed(() => summary.value.streamers.map(streamer => streamer.name).sort())

// Active filters count
const activeFiltersCount = computed(() => {
  let count = 0
  if (filterStreamer.value) count++
  if (filterDate.value !== 'all') count++
  if (filterDuration.value) count++
  if (filterCategory.value) count++
  if (filterRecording.value) count++
  return count
})

// Summary metrics
const totalDuration = computed(() => summary.value.duration)
const totalHoursDisplay = computed(() => {
  const hours = totalDuration.value / 3600
  if (hours >= 1) return `${Math.round(hours * 10) / 10}h`
  const minutes = Math.round(totalDuration.value / 60)
  return `${minutes}m`
})
const totalSizeDisplay = computed(() => {
  const bytes = summary.value.file_size
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
// The player receives an explicit, same-app return URL. Query state is enough to
// rebuild this view after it is remounted; scroll is captured by VideoCard at click time.
const getVideoOrigin = () => {
  return router.resolve({ name: 'videos', query: {
    q: searchQuery.value,
    streamer: filterStreamer.value,
    date: filterDate.value,
    duration: filterDuration.value,
    sort: sortBy.value,
    view: viewMode.value,
    page: String(page.value),
    category: filterCategory.value,
    recording: filterRecording.value,
  } }).fullPath
}
// Keep Vue Router's current location in sync, not only window.history: its next
// push otherwise rewrites the origin entry with the stale entry-time query.
watch([searchQuery, filterStreamer, filterDate, filterDuration, filterCategory, filterRecording, sortBy, viewMode, page], () => {
  router.replace(getVideoOrigin())
})
const emptyResultsDescription = computed(() => (
  searchQuery.value
    ? `No videos match '${searchQuery.value}'. Try adjusting your search or filters.`
    : 'No videos match the selected filters. Try clearing one or more filters.'
))

// Filtering/order are SQL-side; never reinterpret only the current page.
const filteredAndSortedVideos = computed(() => videos.value)

function catalogQuery(): VideoCatalogQuery {
  const sorting = sortBy.value
  const sort: VideoCatalogQuery['sort'] = sorting.startsWith('size') ? 'size' : sorting.startsWith('duration') ? 'duration' : sorting === 'title' || sorting === 'streamer' ? sorting : 'date'
  const params: VideoCatalogQuery = {
    page: page.value, page_size: pageSize, sort,
    order: sorting === 'oldest' || sorting.endsWith('asc') || sorting === 'title' || sorting === 'streamer' ? 'asc' : 'desc',
    q: searchQuery.value || undefined, streamer: filterStreamer.value || undefined,
    category: filterCategory.value || undefined,
    recording: filterRecording.value ? filterRecording.value === 'true' : undefined,
    duration: (filterDuration.value || undefined) as VideoCatalogQuery['duration'],
  }
  if (filterDate.value !== 'all') {
    const boundary = new Date()
    if (filterDate.value === 'today') boundary.setHours(0, 0, 0, 0)
    else if (filterDate.value === 'week') boundary.setDate(boundary.getDate() - 7)
    else if (filterDate.value === 'month') boundary.setMonth(boundary.getMonth() - 1)
    params.created_from = boundary.toISOString()
  }
  return params
}


// Fetch videos
async function fetchVideos() {
  const current = ++generation
  request?.abort()
  const controller = request = new AbortController()
  isLoading.value = true
  fetchError.value = ''
  try {
    const params = catalogQuery()
    let response: VideoCatalogPage | undefined
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        response = await videoApi.getPage(params, controller.signal)
        if (current !== generation || controller.signal.aborted) return
      } catch (error: any) {
        if (current !== generation || controller.signal.aborted) return
        if (error?.status !== 409 || attempt > 0) throw error
        page.value = params.page = 1
        continue
      }
      if (attempt === 0 && response.items.length === 0 && response.total > 0 && page.value > 1) {
        page.value = params.page = 1
        continue
      }
      break
    }
    if (current !== generation || controller.signal.aborted) return
    if (!response || !Array.isArray(response.items)) throw new Error('Invalid catalog response.')
    videos.value = response.items
    total.value = response.total
    hasMore.value = response.has_more
    summary.value = response.summary
    catalogIndex.value = response.index
    if (selectedVideos.value.length) {
      const selected = [...selectedVideos.value]
      const checks = await Promise.allSettled(selected.map(id => videoApi.getMetadata(id)))
      if (current !== generation || controller.signal.aborted) return
      selectedVideos.value = selected.filter((_, index) => {
        const check = checks[index]!
        return check.status === 'fulfilled' || (check.reason as { status?: number })?.status !== 404
      })
      if (checks.some(check => check.status === 'rejected' && (check.reason as { status?: number })?.status !== 404)) {
        throw new Error('Could not verify selected videos. Reload before retrying deletion.')
      }
    }
  } catch (error: any) {
    if (current !== generation || controller.signal.aborted) return
    console.error('[VideosView] Failed to fetch videos:', error)
    fetchError.value = error?.message || 'An unexpected error occurred while loading videos.'
  } finally {
    if (current === generation) {
      isLoading.value = false
      await restoreVideoReturnScroll()
    }
  }
}

function setPage(value: number) {
  page.value = Math.max(1, value)
  selectedVideos.value = []
  fetchVideos()
}

watch(searchQuery, () => {
  clearTimeout(searchTimer)
  request?.abort()
  generation++
  selectedVideos.value = []
  page.value = 1
  isLoading.value = true
  searchTimer = setTimeout(fetchVideos, 300)
})
watch([filterStreamer, filterDate, filterDuration, filterCategory, filterRecording, sortBy], () => {
  clearTimeout(searchTimer)
  page.value = 1
  selectedVideos.value = []
  fetchVideos()
})
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  request?.abort()
  generation++
})

// Actions
function playVideo(video: Video) {
  if (!video.streamer_id || !video.id || video.status === 'failed') return

  prepareVideoReturn(getVideoOrigin())

  // Navigate to video player with correct route parameters
  // Route expects: /streamer/:streamerId/stream/:streamId/watch
  router.push({
    name: 'VideoPlayer',
    params: {
      streamerId: video.streamer_id,
      streamId: video.id  // video.id is actually the stream_id
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

function setSelected(id: number, selected: boolean) {
  if (selected === isSelected(id)) return
  if (selected) selectedVideos.value.push(id)
  else selectedVideos.value = selectedVideos.value.filter(videoId => videoId !== id)
}

const toggleSelection = (id: number) => setSelected(id, !isSelected(id))

function handleSelectionChange(id: number, event: Event) {
  setSelected(id, (event.target as HTMLInputElement).checked)
}

function handleBatchDelete() {
  if (selectedVideos.value.length === 0) return
  deleteError.value = ''
  showDeleteConfirm.value = true
}

async function confirmBatchDelete() {
  if (selectedVideos.value.length === 0 || isDeleting.value || isLoading.value || fetchError.value) return

  const idsToDelete = [...selectedVideos.value]
  isDeleting.value = true
  deleteError.value = ''

  try {
    const outcomes = await videoApi.deleteMultiple(idsToDelete)
    const failed = outcomes.filter(outcome => outcome.status === 'rejected')
    selectedVideos.value = failed.map(outcome => outcome.id)
    // A rejected response can still follow a committed delete; only the catalog confirms survivors.
    await fetchVideos()
    if (failed.length || fetchError.value) {
      const reason = failed[0]?.reason
      deleteError.value = `${outcomes.length - failed.length} deleted; ${failed.length} failed. ${reason instanceof Error ? reason.message : ''} ${fetchError.value
        ? 'Library refresh failed. Close and reload before retrying.'
        : selectedVideos.value.length ? 'Only remaining failed videos are selected for retry.' : 'No failed videos remain.'}`
    } else {
      selectMode.value = false
      showDeleteConfirm.value = false
    }
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
  filterCategory.value = ''
  filterRecording.value = ''
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
  margin-bottom: var(--spacing-5);
}

.brief-stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-4) var(--spacing-6);
  margin: 0;
  padding-bottom: var(--spacing-4);
  border-bottom: 1px solid var(--sv-sem-border-default);
}

.brief-stat {
  min-width: 88px;

  dt {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--text-xs);
    font-weight: v.$font-semibold;
    text-transform: uppercase;
    letter-spacing: v.$tracking-wide;
  }

  dd {
    margin: var(--spacing-1) 0 0;
    color: var(--text-primary);
    font-size: var(--text-lg);
    font-weight: v.$font-bold;
    line-height: 1;
  }

  &.failed dd {
    color: var(--danger-color);
  }

  &.processing dd {
    color: var(--warning-color);
  }
}

// Controls Bar
.controls-bar {
  display: flex;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-4);
  padding-bottom: var(--spacing-3);
  flex-wrap: wrap;
  align-items: center;
  border-bottom: 1px solid var(--sv-sem-border-default);
}

.search-box {
  position: relative;
  flex: 1;
  min-width: min(280px, 100%);

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
    min-height: 48px;
    padding: 0 var(--spacing-10);
    background: var(--background-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--text-sm);
    transition: all v.$duration-200 v.$ease-out;

    &:focus {
      outline: none;
      border-color: var(--sv-sem-action-foreground);
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
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition:
      background-color v.$duration-200 v.$ease-out,
      color v.$duration-200 v.$ease-out;

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
  border-radius: var(--radius-md);
  padding: 1px;
  border: 1px solid var(--border-color);
  min-height: 48px;
}

.toggle-btn {
  padding: var(--spacing-2);
  background: transparent;
  border: none;
  cursor: pointer;
  // Nested radius = container radius minus its padding, so the inner pill
  // follows the container corner instead of looking rounder than it
  border-radius: calc(var(--radius-lg) - var(--spacing-1));
  transition:
    background-color v.$duration-200 v.$ease-out,
    color v.$duration-200 v.$ease-out;

  .icon {
    width: 20px;
    height: 20px;
    stroke: var(--text-secondary);
    fill: none;
  }

  &.active {
    background: var(--sv-sem-surface-selected);

    .icon {
      stroke: var(--sv-sem-text-primary);
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
  min-height: 48px;
  padding: 0 var(--spacing-4);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
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
    border-color: var(--sv-sem-action-foreground);
    color: var(--sv-sem-action-foreground);
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
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  // Neutralize the global `label { margin-bottom }` form style - it pushed
  // this control 4px above its flex-centered neighbors
  margin: 0;
  min-height: 48px;
  padding: 0 var(--spacing-8) 0 var(--spacing-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--background-card);
  cursor: pointer;
  overflow: hidden;
}

.sort-control-wrap::after {
  content: '';
  position: absolute;
  right: var(--spacing-3);
  width: 0.45rem;
  height: 0.45rem;
  border-right: 2px solid var(--text-secondary);
  border-bottom: 2px solid var(--text-secondary);
  pointer-events: none;
  transform: translateY(-15%) rotate(45deg);
}

.sort-value {
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  white-space: nowrap;
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

// The real select covers the whole control invisibly so a click anywhere
// (icon, label, or value) opens the native picker; .sort-value renders the
// selection.
.sort-select {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  min-height: 0;
  appearance: none;
  background: transparent;
  border: 0;
  box-shadow: none;
  opacity: 0;
  cursor: pointer;
}

.sort-select:focus {
  outline: none;
}

.sort-control-wrap:focus-within {
  border-color: var(--sv-sem-action-foreground);
  box-shadow: 0 0 0 3px rgba(var(--primary-500-rgb), 0.1);
}

// Filter Panel
.filter-panel {
  display: flex;
  gap: var(--spacing-4);
  padding: var(--spacing-3) 0;
  border-bottom: 1px solid var(--sv-sem-border-default);
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
  min-height: 44px;

  &:hover {
    border-color: var(--sv-sem-action-foreground);
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
  min-height: 44px;

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
    background: var(--sv-sem-surface-raised);
    border: 1px solid var(--sv-sem-border-default);
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    font-weight: v.$font-medium;
    color: var(--text-primary);
    cursor: pointer;
    min-height: var(--control-target-min);
    font-family: inherit;
    transition:
      color v.$duration-200 v.$ease-out,
      background-color v.$duration-200 v.$ease-out,
      border-color v.$duration-200 v.$ease-out;
    max-width: 100%;
    white-space: normal;
    overflow-wrap: anywhere;

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

    &:focus-visible {
      outline: var(--focus-ring);
      outline-offset: 2px;
    }
  }
}

// Results Info
.results-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-3);
  flex-wrap: wrap;
  min-height: 44px;
  margin: 0 0 var(--spacing-3);
  font-size: var(--text-sm);
  color: var(--text-secondary);

  .selected-count {
    padding: var(--spacing-1) var(--spacing-2);
    background: var(--sv-sem-surface-selected);
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
  background: var(--sv-sem-surface-raised);
  color: var(--sv-sem-text-primary);
  border: none;
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &:hover {
    background: var(--sv-sem-surface-selected);
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
    border: 2px solid var(--sv-sem-text-secondary);
    border-radius: var(--radius-md);
    background: var(--sv-sem-surface-panel);
    color: var(--sv-sem-text-primary);
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
    border-color: var(--sv-sem-action-foreground);
    background: var(--sv-sem-action-primary);
    color: var(--sv-sem-text-inverse);
  }

  input[type="checkbox"]:checked + .checkbox-box .checkbox-check {
    opacity: 1;
    transform: scale(1);
  }

  input[type="checkbox"]:focus-visible + .checkbox-box {
    outline: 2px solid var(--sv-sem-action-focus);
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

// Filter panel collapse: grid-template-rows 0fr -> 1fr animates the actual
// content height without the per-frame layout thrash of a max-height guess.
.filter-collapse {
  display: grid;
  grid-template-rows: 0fr;
  margin-bottom: 0;
  transition:
    grid-template-rows v.$duration-300 v.$ease-out,
    margin-bottom v.$duration-300 v.$ease-out;

  > .filter-panel {
    overflow: hidden;
    min-height: 0;
    margin-bottom: 0;
    opacity: 0;
    // A grid item can shrink below its content but not below its own
    // padding/border, so those collapse along with the row
    padding-block: 0;
    border-color: transparent;
    transition:
      opacity v.$duration-200 v.$ease-out,
      padding v.$duration-300 v.$ease-out,
      border-color v.$duration-200 v.$ease-out;
  }

  &.open {
    grid-template-rows: 1fr;
    margin-bottom: var(--spacing-5);

    > .filter-panel {
      opacity: 1;
      padding-block: var(--spacing-5);
      border-color: var(--border-color);
    }
  }
}

// Responsive - Use SCSS mixins for breakpoints
@include m.respond-below('lg') {  // < 1024px
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
    margin-bottom: var(--spacing-4);
  }

  .brief-stat {
    min-width: 0;
  }

  // Filter and sort controls
  .filters-btn,
  .sort-control-wrap {
    min-height: 44px;  // Touch-friendly
  }

  .filter-panel {
    padding: var(--spacing-3) 0;
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
    .search-input { font-size: 16px; }

    order: -1;  // Move search to top on mobile
    width: 100%;
    margin-bottom: 0;
  }

  .controls-bar {
    display: grid;
    grid-template-columns: 100px auto minmax(0, 1fr);
    gap: var(--spacing-2);
  }

  .search-box {
    grid-column: 1 / -1;
    min-width: 0;
  }

  .view-toggle {
    gap: 0;

    .toggle-btn {
      flex: 0 0 48px;
      width: 48px;
      min-height: 48px;
    }
  }

  .filters-btn {
    justify-content: center;
    padding-inline: var(--spacing-2);
  }

  .sort-control-wrap {
    min-width: 0;
    min-height: 48px;
    justify-content: flex-start;
  }

  .sort-label,
  .sort-icon {
    display: none;
  }

  .sort-value {
    min-width: 0;
    white-space: normal;
    overflow-wrap: anywhere;
    line-height: 1.3;
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
@include m.respond-below('xs') {
  .controls-bar {
    grid-template-columns: 100px minmax(0, 1fr);
  }

  .sort-control-wrap {
    grid-column: 1 / -1;
  }
}
</style>
