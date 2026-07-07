<template>
  <div class="page-view streamers-view">
    <PageHeader
      title="Streamers"
      icon="users"
      :subtitle="isLoading ? 'Manage your tracked streamers' : `Manage your tracked streamers \u2022 ${liveStreamers.length} live now`"
    >
      <template #actions>
        <div class="header-actions">
          <BaseButton
            :variant="autoRefresh ? 'primary' : 'secondary'"
            size="sm"
            @click="toggleAutoRefresh"
          >
            <svg class="icon" aria-hidden="true">
              <use href="#icon-refresh-cw" />
            </svg>
            Auto refresh {{ autoRefresh ? 'On' : 'Off' }}
          </BaseButton>
          <router-link to="/add-streamer" class="btn btn-primary btn-sm add-streamer-link" v-ripple>
            <svg class="icon" aria-hidden="true">
              <use href="#icon-plus" />
            </svg>
            Add Streamer
          </router-link>
        </div>
      </template>
    </PageHeader>

    <section class="streamers-brief" aria-labelledby="streamers-brief-title">
      <div>
        <p class="eyebrow">Creator grid</p>
        <h2 id="streamers-brief-title">Scan every creator by current action</h2>
        <p class="brief-copy">
          Search, filter, and sort without leaving the grid. Live and recording states stay visible on every card.
        </p>
      </div>
      <dl class="brief-stats" aria-label="Streamer status summary">
        <div class="brief-stat live">
          <dt>Live</dt>
          <dd>{{ liveStreamers.length }}</dd>
        </div>
        <div class="brief-stat recording">
          <dt>Recording</dt>
          <dd>{{ recordingStreamers.length }}</dd>
        </div>
        <div class="brief-stat offline">
          <dt>Offline</dt>
          <dd>{{ offlineStreamersCount }}</dd>
        </div>
        <div class="brief-stat total">
          <dt>Total</dt>
          <dd>{{ streamers.length }}</dd>
        </div>
      </dl>
    </section>

    <!-- Controls Bar -->
    <div class="controls-bar" aria-label="Search, filter, and sort streamers">
      <!-- Search -->
      <div class="search-box">
        <svg class="icon">
          <use href="#icon-search" />
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search channel name or display name"
          class="search-input"
          aria-label="Search streamers"
        />
        <button
          v-if="searchQuery"
          @click="searchQuery = ''"
          class="clear-btn"
          aria-label="Clear streamer search"
          title="Clear streamer search"
        >
          <svg class="icon">
            <use href="#icon-x" />
          </svg>
        </button>
      </div>

      <!-- Filter Tabs -->
      <div class="filter-tabs" aria-label="Filter streamers by status">
        <button
          v-for="tab in filterTabs"
          :key="tab.value"
          @click="activeFilter = tab.value"
          :class="{ active: activeFilter === tab.value }"
          :aria-pressed="activeFilter === tab.value"
          class="filter-tab"
          v-ripple
        >
          {{ tab.label }}
          <span v-if="tab.count !== undefined" class="tab-badge">
            {{ tab.count }}
          </span>
        </button>
      </div>

      <!-- View Toggle -->
      <div class="view-toggle" aria-label="Choose streamer layout">
        <button
          @click="viewMode = 'grid'"
          :class="{ active: viewMode === 'grid' }"
          class="toggle-btn"
          aria-label="Show streamers as grid"
          title="Show streamers as grid"
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
          aria-label="Show streamers as list"
          title="Show streamers as list"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-list" />
          </svg>
        </button>
      </div>

      <!-- Sort -->
      <label class="sort-control-wrap">
        <svg class="sort-icon" aria-hidden="true">
          <use href="#icon-list-ordered" />
        </svg>
        <span class="sort-label">Sort</span>
        <select
          v-model="sortBy"
          class="sort-control"
          aria-label="Sort streamers"
        >
          <option v-for="option in sortOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>

      <div class="results-info">
        <span>
          Showing {{ filteredAndSortedStreamers.length }} of {{ streamers.length }} streamers
          <template v-if="activeFilter !== 'all'">in {{ activeFilterLabel }}</template>
          <template v-if="searchQuery"> matching "{{ searchQuery }}"</template>
        </span>
        <span v-if="lastUpdateTime">Updated {{ formatLastUpdate(lastUpdateTime) }}</span>
        <button @click="handleRefresh" class="refresh-btn" aria-label="Refresh streamers" title="Refresh streamers" v-ripple>
          <svg class="icon" :class="{ spinning: isRefreshing }">
            <use href="#icon-refresh-cw" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="streamers-container" :class="[`view-${viewMode}`, viewMode === 'grid' ? 'grid-streamers' : '']">
      <LoadingSkeleton
        v-for="i in 6"
        :key="i"
        type="streamer"
      />
    </div>

    <!-- Empty State -->
    <EmptyState
      v-else-if="fetchError"
      title="Streamers could not load"
      :description="fetchError"
      icon="alert-circle"
      tone="danger"
      tone-label="Recoverable streamers loading error"
      retry-label="Try Again"
      retry-icon="refresh-cw"
      @retry="handleRefresh"
    />

    <EmptyState
      v-else-if="filteredAndSortedStreamers.length === 0 && !searchQuery"
      title="No Streamers Yet"
      description="Add your first streamer to start tracking and recording their content."
      icon="users"
      action-label="Add Streamer"
      action-icon="plus"
      @action="$router.push('/add-streamer')"
    />

    <!-- No Search Results -->
    <EmptyState
      v-else-if="filteredAndSortedStreamers.length === 0 && searchQuery"
      title="No Results Found"
      :description="`No streamers match '${searchQuery}'`"
      icon="search"
      action-label="Clear Search"
      @action="searchQuery = ''"
    />

    <!-- Streamers Grid/List -->
    <div v-else class="streamers-container" :class="[`view-${viewMode}`, viewMode === 'grid' ? 'grid-streamers' : '']">
      <div
        v-for="(streamer, index) in filteredAndSortedStreamers"
        :key="streamer.id"
        class="streamer-wrapper"
        :style="{ animationDelay: `${index * 50}ms` }"
      >
        <StreamerCard
          :streamer="streamer"
          :view-mode="viewMode"
          @watch="handleWatch"
          @force-record="handleForceRecord"
          @delete="handleDelete"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { streamersApi } from '@/services/api'
import { useRealtimeStore } from '@/stores/realtime'
import { hasRealtimeEventType } from '@/types/events'
import { useForceRecording } from '@/composables/useForceRecording'  // NEW: Import composable
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import PageHeader from '@/components/base/PageHeader.vue'
import StreamerCard from '@/components/cards/StreamerCard.vue'

// Real-time store for live updates
const realtime = useRealtimeStore()

// Force recording composable
const { forceStartRecording } = useForceRecording()  // NEW: Use composable

// State
const isLoading = ref(true)
const isRefreshing = ref(false)
const streamers = ref<any[]>([])
const searchQuery = ref('')
const viewMode = ref<'grid' | 'list'>('grid')
const sortBy = ref('live-first')
const activeFilter = ref('all')
const autoRefresh = ref(true)
const lastUpdateTime = ref<Date | null>(null)
const fetchError = ref('')

// Auto-refresh interval
let refreshInterval: number | null = null
const REFRESH_INTERVAL = 30000 // 30 seconds

const sortOptions = [
  { label: 'Live first', value: 'live-first' },
  { label: 'Name A-Z', value: 'name' },
  { label: 'Name Z-A', value: 'name-desc' },
  { label: 'Recently added', value: 'recently-added' },
  { label: 'Most videos', value: 'most-videos' },
]

// Filter tabs with counts
const filterTabs = computed(() => [
  {
    label: 'All',
    value: 'all',
    count: streamers.value.length
  },
  {
    label: 'Live',
    value: 'live',
    count: liveStreamers.value.length
  },
  {
    label: 'Recording',
    value: 'recording',
    count: recordingStreamers.value.length
  },
  {
    label: 'Offline',
    value: 'offline',
    count: streamers.value.length - liveStreamers.value.length
  }
])

const activeFilterLabel = computed(() => {
  return filterTabs.value.find(tab => tab.value === activeFilter.value)?.label.toLowerCase() || 'all'
})

// Live streamers
const liveStreamers = computed(() => {
  return streamers.value.filter(s => s.is_live)
})

// Recording streamers
const recordingStreamers = computed(() => {
  return streamers.value.filter(s => s.is_recording)
})

const offlineStreamersCount = computed(() => {
  return streamers.value.filter(s => !s.is_live).length
})

// Filtered and sorted streamers
const filteredAndSortedStreamers = computed(() => {
  let filtered = [...streamers.value]

  // Search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(s =>
      s.username?.toLowerCase().includes(query) ||
      s.display_name?.toLowerCase().includes(query)
    )
  }

  // Status filter
  switch (activeFilter.value) {
    case 'live':
      filtered = filtered.filter(s => s.is_live)
      break
    case 'recording':
      filtered = filtered.filter(s => s.is_recording)
      break
    case 'offline':
      filtered = filtered.filter(s => !s.is_live)
      break
    // 'all' - no filtering
  }

  // Sorting
  const sorted = [...filtered]
  switch (sortBy.value) {
    case 'name':
      sorted.sort((a, b) => (a.username || '').localeCompare(b.username || ''))
      break
    case 'name-desc':
      sorted.sort((a, b) => (b.username || '').localeCompare(a.username || ''))
      break
    case 'live-first':
      sorted.sort((a, b) => {
        if (a.is_live && !b.is_live) return -1
        if (!a.is_live && b.is_live) return 1
        return (a.username || '').localeCompare(b.username || '')
      })
      break
    case 'recently-added':
      sorted.sort((a, b) => {
        const dateA = new Date(a.created_at || 0).getTime()
        const dateB = new Date(b.created_at || 0).getTime()
        return dateB - dateA
      })
      break
    case 'most-videos':
      sorted.sort((a, b) => (b.video_count || 0) - (a.video_count || 0))
      break
  }

  return sorted
})

// Fetch streamers
async function fetchStreamers() {
  try {
    const response = await streamersApi.getAll()
    // Backend returns {streamers: [...]} format
    streamers.value = response.streamers || []
    lastUpdateTime.value = new Date()
    fetchError.value = ''
  } catch (error) {
    console.error('Failed to fetch streamers:', error)
    streamers.value = []
    fetchError.value = 'Check your backend connection, then retry the streamers list.'
  }
}

// Initial load
async function loadStreamers() {
  isLoading.value = true
  await fetchStreamers()
  isLoading.value = false
}

// Refresh
async function handleRefresh() {
  isRefreshing.value = true
  await fetchStreamers()
  isRefreshing.value = false
}

// Auto-refresh setup
function startAutoRefresh() {
  if (refreshInterval !== null) return
  refreshInterval = window.setInterval(() => {
    if (autoRefresh.value && document.visibilityState === 'visible') {
      fetchStreamers()
    }
  }, REFRESH_INTERVAL)
}

function stopAutoRefresh() {
  if (refreshInterval !== null) {
    window.clearInterval(refreshInterval)
    refreshInterval = null
  }
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    startAutoRefresh()
    handleRefresh()
  } else {
    stopAutoRefresh()
  }
}

// Format last update time
function formatLastUpdate(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return `${diffSec}s ago`

  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`

  const diffHour = Math.floor(diffMin / 60)
  return `${diffHour}h ago`
}

// Handle force record action
async function handleForceRecord(streamer: any) {
  await forceStartRecording(streamer.id, async () => {
    // Refresh streamers after successful force record
    await fetchStreamers()
  })
}

// Handle watch live action
function handleWatch(streamer: any) {
  // Open Twitch stream in new tab
  window.open(`https://twitch.tv/${streamer.username}`, '_blank')
}

// Handle delete streamer action
async function handleDelete(streamer: any) {
  const displayName = streamer.display_name || streamer.username || 'this streamer'

  // First confirmation: Delete streamer?
  if (!confirm(`Delete streamer "${displayName}"?\n\nThis will remove the streamer from your database and unsubscribe from EventSub notifications.`)) {
    return
  }

  // Second confirmation: Delete recordings too?
  const deleteRecordings = confirm(
    `Do you want to delete ALL recordings for "${displayName}" as well?\n\n` +
    `⚠️ WARNING: This cannot be undone!\n\n` +
    `• Click OK to DELETE all recording files\n` +
    `• Click Cancel to KEEP recording files (only remove streamer from database)`
  )

  try {
    // Call API with delete_recordings parameter
    await streamersApi.delete(streamer.id, deleteRecordings)

    // Show success message with details
    if (deleteRecordings) {
      alert(`✅ Streamer "${displayName}" deleted successfully!\nAll recording files were removed.`)
    } else {
      alert(`✅ Streamer "${displayName}" deleted successfully!\nRecording files were kept on disk.`)
    }

    // Remove from UI
    streamers.value = streamers.value.filter(s => s.id !== streamer.id)
  } catch (error) {
    console.error('Failed to delete streamer:', error)
    alert('Failed to delete streamer. Please try again.')
  }
}

// Real-time event handlers
const realtimeCleanups: (() => void)[] = []

// Lifecycle
onMounted(async () => {
  await loadStreamers()
  if (autoRefresh.value) {
    startAutoRefresh()
  }

  // Subscribe to real-time events
  realtimeCleanups.push(
    realtime.onEvents(
      ['stream.online', 'stream.offline', 'channel.update', 'stream.update', 'recording.started', 'recording.finished', 'recording.stopped', 'recording.completed', 'recording_status_update'],
      (event: any) => {
        const username = event.data?.username || event.data?.streamer_name
        if (!username) return

        const streamerIndex = streamers.value.findIndex(
          s => s.username?.toLowerCase() === username.toLowerCase() ||
               s.name?.toLowerCase() === username.toLowerCase()
        )
        if (streamerIndex === -1) return

        const streamer = { ...streamers.value[streamerIndex] }

        if (hasRealtimeEventType(event, 'stream.online')) {
          streamer.is_live = true
          streamer.title = event.data?.title
          streamer.category_name = event.data?.category_name
        } else if (hasRealtimeEventType(event, 'stream.offline')) {
          streamer.is_live = false
          streamer.title = null
          streamer.category_name = null
        } else if (hasRealtimeEventType(event, 'recording.started')) {
          streamer.is_recording = true
          if (!streamer.is_live) streamer.is_live = true
        } else if (hasRealtimeEventType(event, 'recording.finished', 'recording.stopped', 'recording.completed', 'recording_status_update')) {
          if (hasRealtimeEventType(event, 'recording_status_update')) {
            const recording = event.data
            if (recording?.status === 'recording' || recording?.status === 'started') {
              streamer.is_recording = true
            } else if (recording?.status === 'completed' || recording?.status === 'finished' || recording?.status === 'stopped' || recording?.status === 'failed') {
              streamer.is_recording = false
            }
          } else {
            streamer.is_recording = false
          }
        } else {
          if (event.data?.title) streamer.title = event.data.title
          if (event.data?.category_name) streamer.category_name = event.data.category_name
        }

        streamers.value = [
          ...streamers.value.slice(0, streamerIndex),
          streamer,
          ...streamers.value.slice(streamerIndex + 1)
        ]
      }
    ),
    realtime.onEvent('streamer.added', (event: any) => {
      const newId = event.data?.id
      if (newId && !streamers.value.some(s => s.id === newId)) {
        fetchStreamers()
      }
    }),
    realtime.onEvent('streamer.removed', (event: any) => {
      const removedId = event.data?.streamer_id
      if (removedId !== undefined && removedId !== null) {
        streamers.value = streamers.value.filter(s => String(s.id) !== String(removedId))
      }
    }),
    realtime.onEvent('active_recordings_update', (event: any) => {
      const list = event.data?.recordings ?? event.data
      if (!Array.isArray(list)) return
      const recordingUsernames = new Set(
        list.map((r: any) => (r.username || r.streamer_name || '').toLowerCase()).filter(Boolean)
      )
      const recordingStreamerIds = new Set(
        list
          .map((r: any) => r.streamer_id)
          .filter((id: unknown) => id !== undefined && id !== null)
          .map((id: unknown) => String(id))
      )
      streamers.value = streamers.value.map(s => {
        const match =
          recordingStreamerIds.has(String(s.id)) ||
          recordingUsernames.has((s.username || s.name || '').toLowerCase())
        if (Boolean(s.is_recording) !== match) {
          return { ...s, is_recording: match }
        }
        return s
      })
    }),
  )
})

onUnmounted(() => {
  stopAutoRefresh()
  realtimeCleanups.forEach(fn => fn())
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;
.streamers-view {
  // .page-view provides padding/sizing via global styles
  // Page-specific overrides only
}

.streamers-brief {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--spacing-5);
  align-items: stretch;
  margin-bottom: var(--spacing-5);
  padding: var(--spacing-5);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);
  background: linear-gradient(135deg, rgba(var(--primary-500-rgb), 0.14), rgba(var(--info-500-rgb), 0.08)), var(--background-card);
  box-shadow: var(--shadow-sm);
}

.eyebrow {
  margin: 0 0 var(--spacing-2);
  color: var(--primary-color);
  font-size: var(--text-xs);
  font-weight: v.$font-bold;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.streamers-brief h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: clamp(var(--text-xl), 2.4vw, var(--text-3xl));
  line-height: v.$leading-tight;
}

.brief-copy {
  max-width: 680px;
  margin: var(--spacing-2) 0 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  line-height: v.$leading-relaxed;
}

.brief-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(72px, 1fr));
  gap: var(--spacing-2);
  margin: 0;
  align-items: stretch;
}

.brief-stat {
  display: flex;
  min-height: 92px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  padding: var(--spacing-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--background-card);
  text-align: center;

  dt {
    color: var(--text-secondary);
    font-size: var(--text-xs);
    font-weight: v.$font-semibold;
    line-height: 1.2;
  }

  dd {
    margin: var(--spacing-1) 0 0;
    color: var(--text-primary);
    font-size: var(--text-2xl);
    font-weight: v.$font-bold;
    line-height: 1;
  }

  &.live dd,
  &.recording dd {
    color: var(--danger-text-color);
  }

  &.offline dd {
    color: var(--text-secondary);
  }

  &.total dd {
    color: var(--primary-color);
  }
}

.auto-refresh-indicator {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-1) var(--spacing-2);
  background: rgba(var(--success-500-rgb), 0.1);
  color: var(--success-text-color);
  border-radius: var(--radius-md);
  font-size: var(--text-xs);
  font-weight: v.$font-medium;
}

.pulse-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  background: var(--success-text-color);
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  flex-wrap: wrap;

  .icon {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
  }
}

.header-actions :deep(.btn),
.add-streamer-link {
  min-height: 44px;
  min-width: 148px;
  justify-content: center;
}

.add-streamer-link {
  text-decoration: none;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(1.2);
  }
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  min-height: 44px;
  border-radius: var(--radius-lg);
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  border: none;
  cursor: pointer;
  text-decoration: none;
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
      background: v.$primary-800;  /* Darker green when ON */
      box-shadow: var(--shadow-md);
    }
  }

  &.btn-secondary {
    background: var(--background-card);
    color: var(--text-primary);
    border: 1px solid var(--border-color);

    &:hover {
      background: var(--primary-color);  /* Green background when hovering OFF state */
      border-color: var(--primary-color);
      color: white;  /* White text when hovering */
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

.filter-tabs {
  display: flex;
  gap: var(--spacing-1);
  background: var(--background-card);
  border-radius: var(--radius-lg);
  padding: var(--spacing-1);
  border: 1px solid var(--border-color);
}

.filter-tab {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  min-height: 44px;
  padding: var(--spacing-2) var(--spacing-3);
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &.active {
    background: v.$primary-700;
    color: white;

    .tab-badge {
      background: rgba(255, 255, 255, 0.2);
      color: white;
    }
  }

  &:hover:not(.active) {
    background: rgba(var(--primary-500-rgb), 0.1);
    color: var(--primary-color);
  }

  .tab-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 20px;
    padding: 0 var(--spacing-1);
    background: var(--background-darker);
    color: var(--text-primary);
    font-size: var(--text-xs);
    font-weight: v.$font-bold;
    border-radius: var(--radius-full);
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
  min-width: 44px;
  min-height: 44px;
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
  overflow: hidden;
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

.sort-control {
  min-width: 132px;
  min-height: 40px;
  margin: 0;
  padding: 0 var(--spacing-6) 0 0;
  appearance: none;
  background: transparent;
  background-color: transparent;
  border: 0;
  box-shadow: none;
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
}

.sort-control:focus {
  outline: none;
}

.sort-control-wrap:focus-within {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(var(--primary-500-rgb), 0.1);
}

// Results Info
.results-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-3);
  flex: 0 1 auto;
  margin-left: auto;
  min-height: 44px;
  padding: 0 var(--spacing-2) 0 var(--spacing-3);
  background: transparent;
  border: 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.results-info span {
  white-space: nowrap;
}

.refresh-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  padding: 0;
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
    transition: transform v.$duration-200 v.$ease-out;

    &.spinning {
      animation: spin 1s linear infinite;
    }
  }

  &:hover {
    background: rgba(var(--primary-500-rgb), 0.1);

    .icon {
      stroke: var(--primary-color);
    }
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

// Streamers Container
.streamers-container {
  // Grid mode uses global .grid-streamers class
  &.view-grid {
    align-items: start;  // Prevent cards from stretching
  }

  &.view-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
  }
}

.streamer-wrapper {
  animation: fade-in-up v.$duration-500 v.$ease-out backwards;
}

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@include m.respond-below('lg') {  // < 1024px
  .streamers-brief {
    grid-template-columns: 1fr;
  }

  .brief-stats {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .controls-bar {
    flex-wrap: wrap;
  }

  .search-box {
    order: -1;
    width: 100%;
    flex-basis: 100%;
    min-width: unset;
  }

  .filter-tabs {
    flex: 1;
  }
}

@include m.respond-below('sm') {  // < 640px
  .streamers-view {
    padding: var(--spacing-4) var(--spacing-3);

    :deep(.page-header-content),
    :deep(.page-header-end),
    .header-actions {
      width: 100%;
    }

    :deep(.page-header-content) {
      flex-direction: column;
      gap: var(--spacing-3);
    }

    .header-actions {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);

      :deep(.btn),
      .add-streamer-link {
        justify-content: center;
        min-width: 0;
      }
    }
  }

  .streamers-brief {
    padding: var(--spacing-4);
    margin-bottom: var(--spacing-4);
  }

  .brief-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .brief-stat {
    min-width: 0;
  }

  .results-info {
    align-items: stretch;
    flex-direction: column;
  }

  .btn-action {
    flex: 1;
    justify-content: center;
    min-height: 44px;  // Touch-friendly
  }

  .controls-bar {
    gap: var(--spacing-2);
  }

  .search-box {
    .search-input {
      min-height: 44px;  // Touch-friendly
      font-size: 16px;  // Prevent iOS zoom
      padding: var(--spacing-3) var(--spacing-10);
    }

    .clear-btn {
      width: 32px;  // Larger touch target
      height: 32px;

      .icon {
        width: 18px;
        height: 18px;
      }
    }
  }

  .filter-tabs {
    width: 100%;
    justify-content: stretch;
    flex: none;  // Don't shrink

    .filter-tab {
      flex: 1;
      justify-content: center;
      min-height: 44px;  // WCAG 2.5.5 / Apple HIG touch-target
      padding: var(--spacing-2) var(--spacing-2);
      font-size: var(--text-xs);

      .tab-badge {
        font-size: 10px;
        min-width: 18px;
        height: 18px;
      }
    }
  }

  .view-toggle {
    flex: none;  // Fixed width

    .toggle-btn {
      min-width: 44px;  // Touch-friendly
      min-height: 44px;
      padding: var(--spacing-2);

      .icon {
        width: 22px;
        height: 22px;
      }
    }
  }

  .sort-control {
    flex: 1;
    min-width: 0;

    :deep(select) {
      min-height: 44px;
      font-size: 16px;
      padding: var(--spacing-3);
      padding-left: var(--spacing-4);
    }
  }

}
</style>
