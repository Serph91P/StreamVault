<template>
  <div class="page-view streamers-view">
    <PageHeader
      title="Meine Kanäle"
      icon="users"
      :subtitle="isLoading ? 'Kanäle werden geladen …' : `${liveStreamers.length} live · ${recordingStreamers.length} Aufnahmen laufen`"
    >
      <template #actions>
        <div class="header-actions">
          <router-link to="/add-streamer" class="btn btn-primary btn-sm add-streamer-link" v-ripple>
            <svg class="icon" aria-hidden="true">
              <use href="#icon-plus" />
            </svg>
            Kanal hinzufügen
          </router-link>
          <router-link to="/streamers/manage" class="btn btn-secondary btn-sm">Kanäle verwalten</router-link>
          <router-link to="/add-streamer/import" class="btn btn-secondary btn-sm">Follows importieren</router-link>
        </div>
      </template>
    </PageHeader>

    <p v-if="unreadProblems" class="channel-problems" role="status">
      {{ unreadProblems }} ungelesene Warnungen oder Fehler.
      <router-link to="/activity?tab=history">Meldungen ansehen</router-link>
    </p>

    <!-- Status counts live in the filter tabs below, where they are clickable;
         a separate stat-tile row duplicated the same numbers. -->

    <!-- Controls Bar -->
    <div class="controls-bar" aria-label="Kanäle suchen, filtern und sortieren">
      <!-- Search -->
      <div class="search-box">
        <svg class="icon">
          <use href="#icon-search" />
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Kanal suchen"
          class="search-input"
          aria-label="Kanäle suchen"
        />
        <button
          v-if="searchQuery"
          @click="searchQuery = ''"
          class="clear-btn"
          aria-label="Kanalsuche leeren"
          title="Kanalsuche leeren"
        >
          <svg class="icon">
            <use href="#icon-x" />
          </svg>
        </button>
      </div>

      <!-- Filter Tabs -->
      <div class="filter-tabs" aria-label="Kanäle nach Status filtern">
        <button
          v-for="tab in filterTabs"
          :key="tab.value"
          @click="activeFilter = tab.value"
          :class="{ active: activeFilter === tab.value }"
          :aria-pressed="activeFilter === tab.value"
          :aria-label="`${tab.label} ${tab.count}`"
          class="filter-tab"
          v-ripple
        >
          {{ tab.value === 'recording' ? 'Aufnahme' : tab.label }}
          <span v-if="tab.count !== undefined" class="tab-badge">
            {{ tab.count }}
          </span>
        </button>
      </div>

      <!-- View Toggle -->
      <div class="view-toggle" aria-label="Kanalansicht wählen">
        <button
          @click="viewMode = 'grid'"
          :class="{ active: viewMode === 'grid' }"
          :aria-pressed="viewMode === 'grid'"
          class="toggle-btn"
          aria-label="Kacheln anzeigen"
          title="Kacheln anzeigen"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-grid" />
          </svg>
        </button>
        <button
          @click="viewMode = 'list'"
          :class="{ active: viewMode === 'list' }"
          :aria-pressed="viewMode === 'list'"
          class="toggle-btn"
          aria-label="Liste anzeigen"
          title="Liste anzeigen"
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
        <span class="sort-label">Sortierung</span>
        <span class="sort-value">{{ currentSortLabel }}</span>
        <select
          v-model="sortBy"
          class="sort-control"
          aria-label="Kanäle sortieren"
        >
          <option v-for="option in sortOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>

      <div class="results-info">
        <span>
          {{ filteredAndSortedStreamers.length }} von {{ streamers.length }} Kanälen
          <template v-if="activeFilter !== 'all'"> · {{ activeFilterLabel }}</template>
          <template v-if="searchQuery"> · „{{ searchQuery }}“</template>
        </span>
        <span v-if="lastUpdateTime">Stand {{ formatLastUpdate(lastUpdateTime) }}</span>
        <BaseButton variant="ghost" size="sm" :aria-pressed="autoRefresh" @click="toggleAutoRefresh">
          Hintergrundabgleich: {{ autoRefresh ? 'an' : 'aus' }}
        </BaseButton>
        <button @click="handleRefresh" class="refresh-btn" aria-label="Kanalstatus erneut abrufen" title="Kanalstatus erneut abrufen" v-ripple>
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
      title="Kanäle konnten nicht geladen werden"
      :description="fetchError"
      icon="alert-circle"
      tone="danger"
      tone-label="Verbindung zum Server prüfen"
      retry-label="Erneut versuchen"
      retry-icon="refresh-cw"
      @retry="handleRefresh"
    />

    <EmptyState
      v-else-if="streamers.length === 0"
      title="Noch keine Kanäle"
      description="Füge einen Kanal hinzu oder importiere deine Twitch-Follows, um Streams automatisch aufzunehmen."
      icon="users"
      action-label="Kanal hinzufügen"
      action-icon="plus"
      @action="$router.push('/add-streamer')"
    />

    <!-- No Search Results -->
    <EmptyState
      v-else-if="filteredAndSortedStreamers.length === 0"
      title="Keine passenden Kanäle"
      description="Zu dieser Suche oder diesem Status gibt es gerade keine Kanäle. Die übrigen Kanäle sind weiterhin vorhanden."
      icon="search"
      action-label="Alle Kanäle anzeigen"
      @action="searchQuery = ''; activeFilter = 'all'"
    />

    <!-- Streamers Grid/List -->
    <div v-else class="streamers-container" :class="[`view-${viewMode}`, viewMode === 'grid' ? 'grid-streamers' : '']">
      <div
        v-for="streamer in filteredAndSortedStreamers"
        :key="streamer.id"
        class="streamer-wrapper"
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { appStorage } from '@/services/storage'
import { useRoute } from 'vue-router'
import { streamersApi } from '@/services/api'
import { useRealtimeStore } from '@/stores/realtime'
import { useNotificationStore } from '@/stores/notifications'
import { hasRealtimeEventType } from '@/types/events'
import { useForceRecording } from '@/composables/useForceRecording'  // NEW: Import composable
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import PageHeader from '@/components/base/PageHeader.vue'
import StreamerCard from '@/components/cards/StreamerCard.vue'

// Real-time store for live updates
const realtime = useRealtimeStore()
const notifications = useNotificationStore()
const unreadProblems = computed(() => notifications.notifications.filter(
  event => !event.read && ['warning', 'error', 'critical'].includes(event.severity)
).length)
const route = useRoute()

// Force recording composable
const { forceStartRecording } = useForceRecording()  // NEW: Use composable

// State
const isLoading = ref(true)
const isRefreshing = ref(false)
const streamers = ref<any[]>([])
const searchQuery = ref('')
// Grid/list choice survives reloads
const viewMode = ref<'grid' | 'list'>(appStorage.getViewMode('streamers') ?? 'list')
watch(viewMode, (mode) => appStorage.setViewMode('streamers', mode))
const sortBy = ref('live-first')
const activeFilter = ref('all')
const autoRefresh = ref(true)
const lastUpdateTime = ref<Date | null>(null)
const fetchError = ref('')

const validFilters = new Set(['all', 'live', 'recording', 'offline'])

function applyFilterFromRoute() {
  const routeFilter = Array.isArray(route.query.filter) ? route.query.filter[0] : route.query.filter
  if (typeof routeFilter === 'string' && validFilters.has(routeFilter)) {
    activeFilter.value = routeFilter
  }
}

// Auto-refresh interval
let refreshInterval: number | null = null
const REFRESH_INTERVAL = 30000 // 30 seconds

const sortOptions = [
  { label: 'Live zuerst', value: 'live-first' },
  { label: 'Name A-Z', value: 'name' },
  { label: 'Name Z-A', value: 'name-desc' },
  { label: 'Zuletzt hinzugefügt', value: 'recently-added' },
  { label: 'Meiste Aufzeichnungen', value: 'most-videos' },
]

const currentSortLabel = computed(() =>
  sortOptions.find((option) => option.value === sortBy.value)?.label ?? 'Live zuerst'
)

// Filter tabs with counts
const filterTabs = computed(() => [
  {
    label: 'Alle',
    value: 'all',
    count: streamers.value.length
  },
  {
    label: 'Live',
    value: 'live',
    count: liveStreamers.value.length
  },
  {
    label: 'Wird aufgenommen',
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
    fetchError.value = 'Prüfe die Verbindung zum Server und lade die Kanäle erneut.'
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

  if (diffSec < 60) return 'gerade eben'

  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `vor ${diffMin} Min.`

  const diffHour = Math.floor(diffMin / 60)
  return `vor ${diffHour} Std.`
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
  applyFilterFromRoute()
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

watch(
  () => route.query.filter,
  () => applyFilterFromRoute()
)

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

.channel-problems {
  margin-bottom: var(--spacing-5);
  padding: var(--spacing-3) var(--spacing-4);
  border: 1px solid var(--warning-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  background: var(--background-card);

  a { margin-left: var(--spacing-2); }
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

// Controls Bar
.controls-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(180px, auto);
  gap: var(--spacing-3);
  align-items: center;
  margin-bottom: var(--spacing-4);
  padding-bottom: var(--spacing-3);
  border-bottom: 1px solid var(--sv-sem-border-default);
}

$ctrl-h: 44px;

.search-box {
  grid-column: 1 / -1;
  position: relative;
  min-width: 0;

  .icon {
    position: absolute;
    left: var(--spacing-3);
    top: 50%;
    transform: translateY(-50%);
    width: 18px;
    height: 18px;
    pointer-events: none;
    z-index: 10;
  }

  .search-input {
    width: 100%;
    // Match the 48px filter/sort groups (40px controls in 3px padding + border)
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
    width: 44px;
    height: 44px;
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
      position: static;
      transform: none;
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
  border-radius: var(--radius-md);
  padding: 1px;
  border: 1px solid var(--border-color);
}

.filter-tab {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1-5);
  min-height: $ctrl-h;
  padding: 0 var(--spacing-3);
  background: transparent;
  border: none;
  // Nested radius = container radius minus its 3px padding, so the active
  // pill follows the container corner instead of looking rounder than it
  border-radius: calc(var(--radius-lg) - 3px);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &.active {
    background: var(--sv-sem-surface-selected);
    color: var(--sv-sem-text-primary);

    .tab-badge {
      background: var(--sv-sem-surface-panel);
      color: var(--sv-sem-text-primary);
    }
  }

  &:hover:not(.active) {
    background: rgba(var(--primary-500-rgb), 0.1);
    color: var(--sv-sem-action-foreground);
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
  border-radius: var(--radius-md);
  padding: 1px;
  border: 1px solid var(--border-color);
}

.toggle-btn {
  width: 48px;
  min-height: 48px;
  padding: 0;
  background: transparent;
  border: none;
  cursor: pointer;
  border-radius: calc(var(--radius-lg) - 3px);
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 18px;
    height: 18px;
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

.sort-control-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  // Neutralize the global `label { margin-bottom }` form style
  margin: 0;
  // Match the visual height of .filter-tabs / .view-toggle, whose 40px
  // buttons sit inside 3px padding + 1px border.
  min-height: 48px;
  min-width: 180px;
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

.sort-icon {
  width: 16px;
  height: 16px;
  color: var(--text-secondary);
  stroke: currentColor;
  fill: none;
  flex-shrink: 0;
}

.sort-label {
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  white-space: nowrap;
}

.sort-value {
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  white-space: nowrap;
}

// The real select covers the whole control invisibly so a click anywhere
// (icon, label, or value) opens the native picker; .sort-value renders the
// selection.
.sort-control {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  min-height: 0;
  margin: 0;
  padding: 0;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  background: transparent;
  border: 0;
  box-shadow: none;
  opacity: 0;
  cursor: pointer;
}

.sort-control:focus {
  outline: none;
}

.sort-control-wrap:focus-within {
  border-color: var(--sv-sem-action-foreground);
  box-shadow: 0 0 0 3px rgba(var(--primary-500-rgb), 0.1);
}

// Results Info
.results-info {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: var(--spacing-2);
  grid-column: 1 / -1;
  min-height: $ctrl-h;
  padding: 0 var(--spacing-2);
  font-size: var(--text-sm);
  color: var(--sv-sem-text-secondary);
}

.results-info span {
  white-space: nowrap;
}

.refresh-btn {
  display: flex;
  flex: 0 0 $ctrl-h;
  align-items: center;
  justify-content: center;
  width: $ctrl-h;
  min-width: $ctrl-h;
  min-height: $ctrl-h;
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
  // Grid mode uses global .grid-streamers class; rows stretch (grid default)
  // so all cards in a row share the same height.
  &.view-grid .streamer-wrapper {
    display: flex;

    > :deep(*) {
      width: 100%;
    }
  }

  &.view-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
  }
}

@include m.respond-below('lg') {  // < 1024px
  .controls-bar {
    grid-template-columns: minmax(0, 1fr) auto minmax(204px, auto);
  }

  .filter-tabs {
    min-width: 0;
  }
}

@include m.respond-below('md') {
  .controls-bar {
    grid-template-columns: 102px minmax(0, 1fr);
    gap: var(--spacing-2);
  }

  .filter-tabs {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: minmax(0, 0.9fr) minmax(0, 0.9fr) minmax(0, 1.25fr) minmax(0, 1fr);
    width: 100%;
    min-width: 0;
  }

  .filter-tab {
    justify-content: center;
    min-width: 0;
    padding-inline: 2px;
    flex-wrap: wrap;
    white-space: nowrap;
    gap: var(--spacing-1);
    font-size: var(--text-xs);

    .tab-badge {
      min-width: 18px;
      height: 18px;
      font-size: 11px;
    }
  }

  .view-toggle {
    width: auto;
    gap: 0;

    .toggle-btn {
      flex: 0 0 48px;
      width: 48px;
      min-width: 48px;
      min-height: 48px;
    }
  }

  .sort-control-wrap {
    width: 100%;
    min-width: 0;
    min-height: 48px;
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

  .results-info {
    justify-content: flex-start;
    padding-inline: 0;
  }
}

@include m.respond-below('sm') {
  .streamers-view {
    padding: var(--spacing-4) var(--spacing-3);

    :deep(.page-header-content),
    :deep(.page-header-end),
    .header-actions {
      width: 100%;
    }

    .header-actions {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);

      :deep(.btn) {
        justify-content: center;
        min-width: 0;
        padding-inline: var(--spacing-2);
      }

      .add-streamer-link {
        grid-column: 1 / -1;
      }
    }
  }

  .search-box .search-input {
    min-height: 48px;
    font-size: 16px;
  }

  .sort-control {
    min-width: 0;
    font-size: 16px;
  }
}

// At the narrowest supported width, give all status names and counts room.
@include m.respond-below('xs') {
  .filter-tabs {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
