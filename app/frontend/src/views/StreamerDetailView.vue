<template>
  <div class="page-view streamer-detail-view">
    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <LoadingSkeleton type="streamer" />
      <div class="stats-grid">
        <LoadingSkeleton v-for="i in 3" :key="i" type="status" />
      </div>
    </div>

    <!-- Content -->
    <template v-else-if="streamer">
      <!-- Compact Profile Header -->
      <section class="streamer-control-header" :class="{ 'is-live': streamer.is_live, 'is-recording': streamer.is_recording }" aria-labelledby="streamer-detail-title">
        <div class="streamer-control-topline">
          <button @click="goBackToStreamers" class="back-button" aria-label="Back to streamers list">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            Streamers
          </button>

          <div class="streamer-status-strip" :aria-label="statusSummary">
            <StatusBadge :tone="streamerStatusTone" size="sm" dot :pulse="streamer.is_live || streamer.is_recording" :uppercase="false">
              {{ streamerStatusLabel }}
            </StatusBadge>
            <StatusBadge v-if="streamer.category_name" tone="info" size="sm" :uppercase="false">
              {{ streamer.category_name }}
            </StatusBadge>
          </div>
        </div>

        <div class="streamer-control-body">
          <div class="streamer-identity-area">
            <div class="compact-avatar" :class="{ 'is-live': streamer.is_live }">
              <img
                v-if="streamer.profile_image_url && !avatarLoadFailed"
                :src="streamer.profile_image_url"
                :alt="streamerDisplayName"
                @error="avatarLoadFailed = true"
              />
              <div v-else class="avatar-placeholder">
                <svg class="icon-user">
                  <use href="#icon-user" />
                </svg>
              </div>
              <div v-if="streamer.is_live" class="status-dot status-live" />
              <div v-else-if="streamer.is_recording" class="status-dot status-recording" />
              <div v-else class="status-dot status-offline" />
            </div>

            <div class="compact-info">
              <h1 id="streamer-detail-title" class="compact-name">{{ streamerDisplayName }}</h1>
              <p v-if="streamerHandle" class="compact-username">{{ streamerHandle }}</p>
              <p class="compact-title" :class="{ muted: !streamer.title }">
                {{ streamer.title || 'No active stream title' }}
              </p>
            </div>
          </div>

          <dl class="compact-stats" aria-label="Streamer recording summary">
            <div class="compact-stat">
              <dt class="compact-stat-label">Streams</dt>
              <dd class="compact-stat-value">{{ streamCount }}</dd>
            </div>
            <div class="compact-stat">
              <dt class="compact-stat-label">Recorded</dt>
              <dd class="compact-stat-value">{{ recordedStreamsCount }}</dd>
            </div>
            <div class="compact-stat">
              <dt class="compact-stat-label">Avg</dt>
              <dd class="compact-stat-value">{{ averageDuration }}</dd>
            </div>
          </dl>

          <div class="compact-actions" aria-label="Primary streamer actions">
            <BaseButton
              v-if="streamer?.is_live"
              variant="danger"
              @click="handleWatchLive(null)"
              aria-label="Watch live stream"
            >
              <svg class="icon">
                <use href="#icon-play" />
              </svg>
              Watch Live
            </BaseButton>
            <BaseButton
              v-else-if="latestRecording"
              variant="primary"
              @click="handleWatchRecording(latestRecording)"
              aria-label="Watch latest recording"
            >
              <svg class="icon">
                <use href="#icon-play" />
              </svg>
              Latest Recording
            </BaseButton>
            <BaseButton
              v-if="streamer && !streamer.is_recording"
              :variant="streamer.is_live ? 'secondary' : 'primary'"
              :loading="forceRecordingStreamerId === Number(streamerId)"
              loading-label="Starting recording"
              @click="forceStartRecording(Number(streamerId))"
              aria-label="Start recording"
            >
              <svg class="icon">
                <use href="#icon-video" />
              </svg>
              Record Now
            </BaseButton>
            <BaseButton v-else variant="secondary" disabled aria-label="Recording is active">
              <svg class="icon">
                <use href="#icon-video" />
              </svg>
              Recording
            </BaseButton>
          </div>
        </div>

        <p class="safe-action-note">
          Destructive stream cleanup stays in the separated Danger Zone below and requires confirmation.
        </p>
      </section>

      <!-- Tab Navigation with horizontal scroll -->
      <div
        class="cockpit-tabs"
        role="tablist"
        aria-label="Streamer detail sections"
        @keydown="handleCockpitTabKeydown"
      >
        <button
          v-for="tab in cockpitTabs"
          :key="tab.id"
          @click="activeCockpitTab = tab.id"
          :class="['cockpit-tab', { active: activeCockpitTab === tab.id }]"
          :id="`streamer-detail-tab-${tab.id}`"
          :aria-selected="activeCockpitTab === tab.id"
          :aria-controls="`streamer-detail-panel-${tab.id}`"
          :tabindex="activeCockpitTab === tab.id ? 0 : -1"
          role="tab"
        >
          <svg class="icon">
            <use :href="tab.icon" />
          </svg>
          <span class="tab-label">{{ tab.label }}</span>
        </button>
      </div>

      <!-- Overview Tab -->
      <div
        v-if="activeCockpitTab === 'overview'"
        id="streamer-detail-panel-overview"
        class="cockpit-panel"
        role="tabpanel"
        aria-labelledby="streamer-detail-tab-overview"
      >
        <!-- Status Summary -->
        <div class="stats-section">
          <StatusCard
            :value="streamer.is_live ? 'Live' : 'Offline'"
            label="Status"
            :icon="streamer.is_live ? 'radio' : 'user'"
            :type="streamer.is_live ? 'danger' : 'primary'"
            :subtitle="streamer.is_live ? (streamer.title || 'Currently streaming') : 'No active stream'"
          />
          <StatusCard
            :value="streamer.is_recording ? 'Recording' : 'Idle'"
            label="Recording"
            :icon="streamer.is_recording ? 'video' : 'clock'"
            :type="streamer.is_recording ? 'danger' : 'info'"
            :subtitle="streamer.is_recording ? 'Capture in progress' : 'Ready to record'"
          />
          <StatusCard
            :value="streamCount"
            label="Total Streams"
            icon="film"
            type="primary"
            :format-as-number="true"
          />
          <StatusCard
            :value="recordedStreamsCount"
            label="Recorded"
            icon="check-circle"
            type="success"
            :format-as-number="true"
          />
          <StatusCard
            :value="averageDuration"
            label="Avg Duration"
            icon="clock"
            type="info"
            :format-as-number="false"
          />
        </div>

        <!-- Latest Recording / Last Stream Info -->
        <div v-if="latestStream" class="overview-section">
          <div class="section-header">
            <h2 class="section-title">Latest Stream</h2>
          </div>
          <div class="latest-stream-card">
            <div class="latest-stream-info">
              <span class="latest-stream-title">{{ latestStream.title || 'Untitled Stream' }}</span>
              <span v-if="latestStream.category_name" class="latest-stream-category">{{ latestStream.category_name }}</span>
            </div>
            <div class="latest-stream-meta">
              <span class="meta-item">
                <svg class="meta-icon"><use href="#icon-clock" /></svg>
                {{ formatDateShort(latestStream.started_at) }}
              </span>
              <span class="meta-item">
                <svg class="meta-icon"><use href="#icon-clock" /></svg>
                {{ formatDuration(latestStream.started_at, latestStream.ended_at) }}
              </span>
            </div>
          </div>
        </div>
        <div v-else class="overview-section">
          <EmptyState
            variant="compact"
            title="No Activity Yet"
            description="This streamer has no recorded streams. Activity will appear here once streams are recorded."
            icon="info"
          />
        </div>

        <!-- Danger Zone -->
        <div class="overview-section danger-zone">
          <div class="section-header">
            <h2 class="section-title danger-title">Danger Zone</h2>
          </div>
          <div class="danger-zone-card">
            <div class="danger-zone-content">
              <div class="danger-zone-info">
                <svg class="danger-icon"><use href="#icon-alert-triangle" /></svg>
                <div>
                  <strong>Delete All Streams</strong>
                  <p class="danger-description">Permanently remove all streams for this streamer. Active recordings will be skipped.</p>
                </div>
              </div>
              <button @click="confirmDeleteAll" class="btn-action btn-danger-outline" aria-label="Delete all streams">
                <svg class="icon"><use href="#icon-trash" /></svg>
                Delete All
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Videos Tab -->
      <div
        v-if="activeCockpitTab === 'videos'"
        id="streamer-detail-panel-videos"
        class="cockpit-panel"
        role="tabpanel"
        aria-labelledby="streamer-detail-tab-videos"
      >
        <div class="history-header">
          <h2 class="section-title">Stream History</h2>
          <div class="view-controls">
            <div class="select-wrapper">
              <svg class="select-icon">
                <use href="#icon-filter" />
              </svg>
              <select v-model="sortBy" class="sort-select">
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
                <option value="duration-desc">Longest Duration</option>
                <option value="duration-asc">Shortest Duration</option>
              </select>
            </div>
          </div>
        </div>

        <div v-if="isLoadingStreams" class="streams-container">
          <LoadingSkeleton v-for="i in 6" :key="i" type="list-item" />
        </div>

        <EmptyState
          v-else-if="sortedStreams.length === 0"
          title="No Streams Yet"
          description="Start recording this streamer to see their streams here."
          icon="video"
          action-label="Record Now"
          action-icon="video"
          @action="forceStartRecording(Number(streamerId))"
        />

        <div v-else class="streams-container">
          <div class="streams-summary">
            {{ sortedStreams.length }} stream{{ sortedStreams.length !== 1 ? 's' : '' }}
            <template v-if="recordedStreamsCount > 0"> &middot; {{ recordedStreamsCount }} recorded</template>
            <template v-else-if="sortedStreams.length > 0"> &middot; No recordings</template>
          </div>
          <StreamCard
            v-for="stream in sortedStreams"
            :key="stream.id"
            :stream="stream"
            @watch-live="handleWatchLive"
            @force-record="handleForceRecord"
            @watch="handleWatchRecording"
            @delete="handleDeleteStream"
          />
        </div>
      </div>

      <!-- Recording Settings Tab -->
      <div
        v-if="activeCockpitTab === 'settings'"
        id="streamer-detail-panel-settings"
        class="cockpit-panel"
        role="tabpanel"
        aria-labelledby="streamer-detail-tab-settings"
      >
        <div class="settings-header">
          <p class="settings-description">
            Configure recording behavior and notifications for this streamer. Changes take effect on the next stream.
          </p>
        </div>
        <StreamerSettingsFields v-model="streamerSettings" :disabled="savingSettings" />
        <div class="settings-actions">
          <BaseButton variant="secondary" @click="loadSettings">Cancel</BaseButton>
          <BaseButton variant="primary" :loading="savingSettings" @click="saveSettings">
            {{ savingSettings ? 'Saving...' : 'Save Settings' }}
          </BaseButton>
        </div>
      </div>

      <!-- Events Tab -->
      <div
        v-if="activeCockpitTab === 'events'"
        id="streamer-detail-panel-events"
        class="cockpit-panel"
        role="tabpanel"
        aria-labelledby="streamer-detail-tab-events"
      >
        <div class="events-header">
          <h2 class="section-title">Recent Events</h2>
          <span v-if="streamerEvents.length > 0" class="events-count">Last {{ streamerEvents.length }}</span>
        </div>
        <div v-if="streamerEvents.length === 0" class="events-empty">
          <EmptyState
            title="Waiting for Events"
            description="Real-time events for this streamer appear here automatically. Events include stream notifications, recording status changes, and channel updates."
            icon="activity"
          />
        </div>
        <div v-else class="events-list">
          <div
            v-for="(evt, idx) in streamerEvents"
            :key="idx"
            class="event-item"
          >
            <span class="event-dot" :class="eventDotClass(evt.type)"></span>
            <div class="event-content">
              <span class="event-type">{{ eventTypeLabel(evt.type) }}</span>
              <span class="event-message">{{ eventDisplayMessage(evt) }}</span>
            </div>
            <span class="event-time">{{ formatEventTime(evt.timestamp) }}</span>
          </div>
          <details class="events-legend">
            <summary class="legend-toggle">Event type legend</summary>
            <div class="legend-items">
              <span class="legend-item">
                <span class="event-dot dot-success"></span>
                <span>Online / Started</span>
              </span>
              <span class="legend-item">
                <span class="event-dot dot-info"></span>
                <span>Offline / Finished</span>
              </span>
              <span class="legend-item">
                <span class="event-dot dot-warning"></span>
                <span>Update</span>
              </span>
              <span class="legend-item">
                <span class="event-dot dot-danger"></span>
                <span>Error / Failed</span>
              </span>
              <span class="legend-item">
                <span class="event-dot dot-default"></span>
                <span>Other</span>
              </span>
            </div>
          </details>
        </div>
      </div>
    </template>

    <!-- Error State -->
    <EmptyState
      v-else
      title="Streamer Not Found"
      description="The streamer you're looking for doesn't exist."
      icon="alert-circle"
      action-label="Back to Streamers"
      @action="$router.push('/streamers')"
    />

    <!-- Delete Confirmation Modal -->
    <BaseModal v-model="showConfirm" title="Delete All Streams" size="md">
      <p>Are you sure you want to delete all streams for this streamer?</p>
      <p class="warning">
        <svg class="icon-warning">
          <use href="#icon-alert-triangle" />
        </svg>
        Active recordings will be skipped to avoid data loss.
      </p>
      <template #footer>
        <BaseButton variant="secondary" @click="showConfirm = false">Cancel</BaseButton>
        <BaseButton variant="danger" :loading="deletingAll" @click="deleteAll">
          {{ deletingAll ? 'Deleting...' : 'Delete All' }}
        </BaseButton>
      </template>
    </BaseModal>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { streamersApi } from '@/services/api'
import { useForceRecording } from '@/composables/useForceRecording'
import { useToast } from '@/composables/useToast'
import { useRealtimeStore } from '@/stores/realtime'
import { hasRealtimeEventType } from '@/types/events'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusCard from '@/components/cards/StatusCard.vue'
import StreamCard from '@/components/cards/StreamCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import StreamerSettingsFields from '@/components/streamers/StreamerSettingsFields.vue'
import { buildDefaultState } from '@/schemas/streamerSettings.schema'

// Router & URL params
const route = useRoute()
const router = useRouter()
const streamerId = computed(() => route.params.id as string)
const toast = useToast()

// Navigation
const goBackToStreamers = () => {
  router.push('/streamers')
}

// Loading states
const isLoading = ref(true)
const isLoadingStreams = ref(true)

// Data
const streamer = ref<any>(null)
const streams = ref<any[]>([])
const avatarLoadFailed = ref(false)

// View controls
const sortBy = ref('newest')

// Delete flow
const showConfirm = ref(false)
const deletingAll = ref(false)

// Force recording
const { forceRecordingStreamerId, forceStartRecording } = useForceRecording()

// Cockpit tabs
const activeCockpitTab = ref('overview')
const cockpitTabs = [
  { id: 'overview', label: 'Overview', icon: '#icon-activity' },
  { id: 'videos', label: 'Videos', icon: '#icon-film' },
  { id: 'settings', label: 'Settings', icon: '#icon-settings' },
  { id: 'events', label: 'Events', icon: '#icon-clock' },
]

const focusActiveCockpitTab = async () => {
  await nextTick()
  document.getElementById(`streamer-detail-tab-${activeCockpitTab.value}`)?.focus()
}

const handleCockpitTabKeydown = async (event: KeyboardEvent) => {
  const currentIndex = cockpitTabs.findIndex((tab) => tab.id === activeCockpitTab.value)
  let nextIndex = currentIndex

  if (event.key === 'ArrowRight') {
    nextIndex = (currentIndex + 1) % cockpitTabs.length
  } else if (event.key === 'ArrowLeft') {
    nextIndex = (currentIndex - 1 + cockpitTabs.length) % cockpitTabs.length
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = cockpitTabs.length - 1
  } else {
    return
  }

  event.preventDefault()
  activeCockpitTab.value = cockpitTabs[nextIndex].id
  await focusActiveCockpitTab()
}

// Settings inline - schema-driven
const savingSettings = ref(false)
const streamerSettings = ref<Record<string, unknown>>(buildDefaultState())

const loadSettings = () => {
  const defaults = buildDefaultState()
  const s = streamer.value || {}

  streamerSettings.value = {
    ...defaults,
    quality: s.quality || s.recording_quality || (defaults.quality as string) || 'best',
    recording: {
      ...((defaults.recording as Record<string, unknown>) || {}),
      ...((s.recording as Record<string, unknown>) || {}),
    },
    notifications: {
      ...((defaults.notifications as Record<string, unknown>) || {}),
      ...((s.notifications as Record<string, unknown>) || {}),
    },
  }
}

const saveSettings = async () => {
  savingSettings.value = true

  try {
    const response = await fetch(`/api/streamers/streamer/${streamerId.value}/settings`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(streamerSettings.value),
    })

    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.detail || `HTTP error! Status: ${response.status}`)
    }

    toast.success('Settings saved successfully!')
    await fetchStreamer()
  } catch (error) {
    console.error('Failed to save settings:', error)
    toast.error('Failed to save settings. Please try again.')
  } finally {
    savingSettings.value = false
  }
}

// Events tab
const streamerEvents = computed(() => {
  const events = realtime.recentEvents
  if (!events || !Array.isArray(events)) return []
  return events.filter((evt: any) => {
    const data = evt.data || evt
    const idMatch =
      (data.streamer_id !== undefined && String(data.streamer_id) === streamerId.value) ||
      (data.id !== undefined && String(data.id) === streamerId.value)
    if (idMatch) return true
    if (!streamer.value) return false
    const username = (data.username || data.streamer_name || '').toLowerCase()
    if (!username) return false
    return (
      streamer.value.username?.toLowerCase() === username ||
      streamer.value.name?.toLowerCase() === username
    )
  }).slice(-50).reverse()
})

const formatEventTime = (ts: string | number | undefined): string => {
  if (!ts) return ''
  const date = new Date(ts)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}h ago`
  const diffDay = Math.floor(diffHour / 24)
  return `${diffDay}d ago`
}

const eventDotClass = (type: string): string => {
  if (type.includes('online') || type.includes('started')) return 'dot-success'
  if (type.includes('offline') || type.includes('stopped') || type.includes('finished') || type.includes('completed')) return 'dot-info'
  if (type.includes('failed') || type.includes('error')) return 'dot-danger'
  if (type.includes('update')) return 'dot-warning'
  return 'dot-default'
}

const eventTypeLabel = (type: string): string => {
  const labels: Record<string, string> = {
    'stream.online': 'Went Live',
    'stream.offline': 'Went Offline',
    'stream.update': 'Stream Updated',
    'channel.update': 'Channel Updated',
    'recording.started': 'Recording Started',
    'recording.completed': 'Recording Completed',
    'recording.finished': 'Recording Finished',
    'recording.stopped': 'Recording Stopped',
    'recording.failed': 'Recording Failed',
    'recording.available': 'Recording Available',
    'recording.status_update': 'Status Update',
    'active_recordings_update': 'Active Recordings Updated',
  }
  return labels[type] || type
}

const eventDisplayMessage = (evt: any): string => {
  if (evt.message) return evt.message
  const type = evt.type || ''
  if (type.includes('online')) return 'Stream is now live'
  if (type.includes('offline')) return 'Stream has ended'
  if (type.includes('update')) return 'Title or category was updated'
  if (type.includes('started')) return 'Recording has started'
  if (type.includes('completed') || type.includes('finished')) return 'Recording completed'
  if (type.includes('stopped')) return 'Recording stopped'
  if (type.includes('failed')) return 'Recording failed'
  if (type.includes('available')) return 'Recording is available'
  if (type.includes('status_update')) return 'Recording status changed'
  return 'No additional details'
}

// Load settings when the settings tab is activated
watch(activeCockpitTab, (tab) => {
  if (tab === 'settings') {
    loadSettings()
  }
})

// Latest stream
const latestStream = computed(() => {
  if (streams.value.length === 0) return null
  return [...streams.value].sort((a, b) => {
    const dateA = new Date(a.started_at || 0).getTime()
    const dateB = new Date(b.started_at || 0).getTime()
    return dateB - dateA
  })[0]
})

const latestRecording = computed(() => {
  return [...streams.value]
    .filter((stream) => stream.recording_path)
    .sort((a, b) => {
      const dateA = new Date(a.started_at || 0).getTime()
      const dateB = new Date(b.started_at || 0).getTime()
      return dateB - dateA
    })[0] || null
})

const streamerDisplayName = computed(() => {
  return streamer.value?.display_name || streamer.value?.name || streamer.value?.username || 'Streamer'
})

const streamerHandle = computed(() => {
  if (!streamer.value?.username) return ''
  return `@${streamer.value.username}`
})

const streamerStatusLabel = computed(() => {
  if (streamer.value?.is_recording) return 'Recording'
  if (streamer.value?.is_live) return 'Live'
  return 'Offline'
})

const streamerStatusTone = computed(() => {
  if (streamer.value?.is_recording) return 'recording'
  if (streamer.value?.is_live) return 'live'
  return 'offline'
})

// Stats computed
const streamCount = computed(() => streams.value.length)

const recordedStreamsCount = computed(() => {
  return streams.value.filter(s => s.recording_path).length
})

const statusSummary = computed(() => {
  const parts = [streamerStatusLabel.value]
  if (streamer.value?.category_name) parts.push(streamer.value.category_name)
  if (streamCount.value > 0) parts.push(`${streamCount.value} streams`)
  if (recordedStreamsCount.value > 0) parts.push(`${recordedStreamsCount.value} recorded`)
  return parts.join(', ')
})

const averageDuration = computed(() => {
  if (streams.value.length === 0) return '0m'

  const totalSeconds = streams.value.reduce((sum, s) => {
    if (!s.started_at) return sum
    const start = new Date(s.started_at).getTime()
    const end = s.ended_at ? new Date(s.ended_at).getTime() : new Date().getTime()
    return sum + Math.floor((end - start) / 1000)
  }, 0)

  const avgSeconds = totalSeconds / streams.value.length
  const hours = Math.floor(avgSeconds / 3600)
  const minutes = Math.floor((avgSeconds % 3600) / 60)

  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
})

// Sorted streams
const sortedStreams = computed(() => {
  const sorted = [...streams.value]

  switch (sortBy.value) {
    case 'newest':
      return sorted.sort((a, b) => {
        const dateA = new Date(a.started_at || 0).getTime()
        const dateB = new Date(b.started_at || 0).getTime()
        return dateB - dateA
      })
    case 'oldest':
      return sorted.sort((a, b) => {
        const dateA = new Date(a.started_at || 0).getTime()
        const dateB = new Date(b.started_at || 0).getTime()
        return dateA - dateB
      })
    case 'duration-desc':
      return sorted.sort((a, b) => {
        const aDur = a.ended_at ? new Date(a.ended_at).getTime() - new Date(a.started_at).getTime() : 0
        const bDur = b.ended_at ? new Date(b.ended_at).getTime() - new Date(b.started_at).getTime() : 0
        return bDur - aDur
      })
    case 'duration-asc':
      return sorted.sort((a, b) => {
        const aDur = a.ended_at ? new Date(a.ended_at).getTime() - new Date(a.started_at).getTime() : 0
        const bDur = b.ended_at ? new Date(b.ended_at).getTime() - new Date(b.started_at).getTime() : 0
        return aDur - bDur
      })
    default:
      return sorted
  }
})

// Format helpers
const formatDateShort = (dateStr?: string): string => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

const formatDuration = (start?: string, end?: string): string => {
  if (!start) return '-'
  const startDate = new Date(start)
  const endDate = end ? new Date(end) : new Date()
  const diffMs = endDate.getTime() - startDate.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const hours = Math.floor(diffMins / 60)
  const mins = diffMins % 60
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}

// Fetch streamer data
async function fetchStreamer() {
  isLoading.value = true
  try {
    const response = await streamersApi.get(Number(streamerId.value))
    streamer.value = response
    avatarLoadFailed.value = false
  } catch {
    streamer.value = null
    avatarLoadFailed.value = false
  } finally {
    isLoading.value = false
  }
}

// Fetch streams
async function fetchStreams() {
  isLoadingStreams.value = true
  try {
    const response = await streamersApi.getStreams(Number(streamerId.value))
    streams.value = response?.streams || []
  } catch {
    streams.value = []
  } finally {
    isLoadingStreams.value = false
  }
}

// Actions
function confirmDeleteAll() {
  showConfirm.value = true
}

async function deleteAll() {
  if (!streamerId.value) return

  try {
    deletingAll.value = true
    await streamersApi.deleteAllStreams(Number(streamerId.value), { excludeActive: true })
    showConfirm.value = false
    router.push('/streamers')
  } catch (error) {
    console.error('Failed to delete all streams:', error)
  } finally {
    deletingAll.value = false
  }
}

function handleWatchLive(_stream: any) {
  if (!streamer.value) return
  router.push(`/live/${streamer.value.username}`)
}

function handleForceRecord(_stream: any) {
  forceStartRecording(Number(streamerId.value))
}

async function handleWatchRecording(stream: any) {
  if (!stream.recording_path) return

  try {
    const response = await fetch(`/api/stream/${stream.id}/has-recording`, {
      credentials: 'include'
    })
    const data = await response.json()

    if (data.has_recording) {
      router.push(`/videos/${stream.id}`)
    }
  } catch {
    // silently fail
  }
}

function handleDeleteStream(_stream: any) {
  // Deletion handled by StreamCard's own actions
}

// Real-time store
const realtime = useRealtimeStore()

const matchesCurrentStreamer = (data: any): boolean => {
  if (!data || !streamer.value) return false
  const idMatch =
    (data.streamer_id !== undefined && String(data.streamer_id) === streamerId.value) ||
    (data.id !== undefined && String(data.id) === streamerId.value)
  if (idMatch) return true
  const username = (data.username || data.streamer_name || '').toLowerCase()
  if (!username) return false
  return (
    streamer.value.username?.toLowerCase() === username ||
    streamer.value.name?.toLowerCase() === username
  )
}

// Real-time event handlers
const realtimeCleanups: (() => void)[] = []

// Initialize
onMounted(async () => {
  await Promise.all([
    fetchStreamer(),
    fetchStreams()
  ])

  // Subscribe to real-time events
  realtimeCleanups.push(
    realtime.onEvents(
      ['stream.online', 'stream.offline', 'channel.update', 'stream.update', 'recording.started', 'recording.finished', 'recording.stopped', 'recording.completed', 'recording_status_update'],
      (event: any) => {
        if (!streamer.value) return
        const data = event.data
        if (!data || !matchesCurrentStreamer(data)) return

        const updated = { ...streamer.value }
        let changed = false

        if (hasRealtimeEventType(event, 'stream.online')) {
          updated.is_live = true
          if (data.title) updated.title = data.title
          if (data.category_name) updated.category_name = data.category_name
          changed = true
        } else if (hasRealtimeEventType(event, 'stream.offline')) {
          updated.is_live = false
          updated.title = null
          updated.category_name = null
          changed = true
        } else if (hasRealtimeEventType(event, 'channel.update', 'stream.update')) {
          if (data.title) { updated.title = data.title; changed = true }
          if (data.category_name) { updated.category_name = data.category_name; changed = true }
        } else if (hasRealtimeEventType(event, 'recording.started')) {
          updated.is_recording = true
          if (!updated.is_live) updated.is_live = true
          changed = true
        } else if (hasRealtimeEventType(event, 'recording_status_update')) {
          if (data.status === 'recording' || data.status === 'started') {
            updated.is_recording = true
            changed = true
          } else if (data.status === 'completed' || data.status === 'finished' || data.status === 'stopped' || data.status === 'failed') {
            updated.is_recording = false
            changed = true
            fetchStreams()
          }
        } else if (hasRealtimeEventType(event, 'recording.finished', 'recording.stopped', 'recording.completed')) {
          updated.is_recording = false
          changed = true
          fetchStreams()
        }

        if (changed) {
          streamer.value = updated
        }
      }
    ),
    realtime.onEvent('active_recordings_update', (event: any) => {
      if (!streamer.value) return
      const list = event.data?.recordings ?? event.data
      if (!Array.isArray(list)) return
      const activeForThis = list.some((r: any) => matchesCurrentStreamer(r))
      if (Boolean(streamer.value.is_recording) !== activeForThis) {
        streamer.value = { ...streamer.value, is_recording: activeForThis }
      }
    }),
  )
})

onUnmounted(() => {
  realtimeCleanups.forEach((fn) => fn())
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.streamer-detail-view {
  // Page-specific overrides
}

// Compact Profile Header
.streamer-control-header {
  display: grid;
  gap: var(--spacing-4);
  padding: var(--spacing-4);
  margin-bottom: var(--spacing-6);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl);

  &.is-live {
    border-color: rgba(var(--danger-500-rgb), 0.45);
    box-shadow: 0 16px 44px rgba(var(--danger-500-rgb), 0.12);
  }

  &.is-recording {
    border-color: rgba(var(--danger-500-rgb), 0.5);
  }
}

.streamer-control-topline,
.streamer-control-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-4);
}

.streamer-control-topline {
  padding-bottom: var(--spacing-3);
  border-bottom: 1px solid var(--border-color);
}

.back-button {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  min-height: 40px;
  padding: var(--spacing-2) var(--spacing-3);
  color: var(--text-secondary);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
  }

  &:hover,
  &:focus-visible {
    color: var(--text-primary);
    border-color: var(--primary-color);
    outline: none;
  }
}

.streamer-status-strip {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--spacing-2);
}

.streamer-identity-area {
  display: flex;
  align-items: center;
  gap: var(--spacing-4);
  min-width: min(360px, 100%);
}

.compact-avatar {
  position: relative;
  width: 64px;
  height: 64px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 3px solid var(--border-color);
  background: var(--background-darker);
  flex-shrink: 0;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .avatar-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--background-darker);

    .icon-user {
      width: 32px;
      height: 32px;
      stroke: var(--text-secondary);
      fill: none;
    }
  }

  &.is-live {
    border-color: var(--danger-color);
  }

  .status-dot {
    position: absolute;
    bottom: -2px;
    right: -2px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    border: 3px solid var(--background-card);

    &.status-live {
      background: var(--danger-color);
    }

    &.status-recording {
      background: var(--warning-color);
    }

    &.status-offline {
      background: var(--text-tertiary);
    }
  }
}

.compact-info {
  flex: 1;
  min-width: 180px;
}

.compact-name {
  font-size: var(--text-xl);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.15;
}

.compact-username {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin: var(--spacing-1) 0 0 0;
}

.compact-title {
  font-size: var(--text-sm);
  color: var(--text-primary);
  margin: var(--spacing-1) 0 0 0;
  font-weight: v.$font-medium;

  &.muted {
    color: var(--text-tertiary);
    font-weight: v.$font-normal;
  }
}

.compact-stats {
  display: flex;
  gap: var(--spacing-2);
  flex-shrink: 0;
  margin: 0;
}

.compact-stat {
  display: flex;
  flex-direction: column-reverse;
  align-items: center;
  gap: 2px;
  min-width: 84px;
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.compact-stat-value {
  font-size: var(--text-lg);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  margin: 0;
}

.compact-stat-label {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0;
}

.compact-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
  flex-shrink: 0;

  :deep(.btn) {
    min-height: 44px;
  }

  .icon {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
  }
}

.safe-action-note {
  margin: calc(var(--spacing-1) * -1) 0 0;
  color: var(--text-tertiary);
  font-size: var(--text-xs);
  line-height: 1.4;
}

// Action buttons (used in header and danger zone)
.btn-action {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  border-radius: var(--radius-lg);
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  border: none;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  min-height: 44px;
  text-decoration: none;

  .icon {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
    flex-shrink: 0;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  &.btn-primary {
    background: var(--primary-color);
    color: white;

    &:hover:not(:disabled) {
      background: var(--primary-600);
    }
  }

  &.btn-live {
    background: var(--danger-color);
    color: white;

    &:hover:not(:disabled) {
      background: var(--danger-600);
    }
  }

  &.btn-danger-outline {
    background: transparent;
    color: var(--danger-text-color);
    border: 1px solid rgba(var(--danger-500-rgb), 0.4);

    &:hover:not(:disabled) {
      background: rgba(var(--danger-500-rgb), 0.1);
      border-color: var(--danger-color);
    }
  }
}

// Cockpit Tabs - horizontal scroll
.cockpit-tabs {
  display: flex;
  gap: var(--spacing-1);
  margin-bottom: var(--spacing-6);
  background: var(--background-card);
  border-radius: var(--radius-lg);
  padding: var(--spacing-1);
  border: 1px solid var(--border-color);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: var(--primary-color) transparent;
  scroll-padding-inline: var(--spacing-2);

  &::-webkit-scrollbar {
    height: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(var(--primary-500-rgb), 0.55);
    border-radius: var(--radius-full);
  }
}

.cockpit-tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  white-space: nowrap;
  flex: 0 0 auto;
  min-height: 44px;
  min-width: max-content;
  scroll-snap-align: start;

  .icon {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
    flex-shrink: 0;
  }

  &.active {
    background: var(--primary-color-dark);
    color: white;
    box-shadow: 0 8px 22px rgba(var(--primary-500-rgb), 0.25);
  }

  &:hover:not(.active) {
    background: rgba(var(--primary-500-rgb), 0.1);
    color: var(--primary-color);
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

// Cockpit Panel
.cockpit-panel {
  animation: fade-in v.$duration-500 v.$ease-out backwards;
}

// Stats Section
.stats-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--spacing-4);
  margin-bottom: var(--spacing-6);
}

// Section header
.section-header {
  margin-bottom: var(--spacing-4);
}

.section-title {
  font-size: var(--text-lg);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  margin: 0;
}

.danger-title {
  color: var(--danger-color);
}

// Overview section
.overview-section {
  margin-bottom: var(--spacing-8);
}

// Latest Stream Card
.latest-stream-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-4);
  padding: var(--spacing-4);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.latest-stream-info {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
}

.latest-stream-title {
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
}

.latest-stream-category {
  font-size: var(--text-xs);
  color: var(--text-primary);
}

.latest-stream-meta {
  display: flex;
  gap: var(--spacing-3);
  flex-shrink: 0;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  font-size: var(--text-xs);
  color: var(--text-secondary);

  .meta-icon {
    width: 14px;
    height: 14px;
    stroke: currentColor;
    fill: none;
  }
}

// Danger Zone
.danger-zone-card {
  background: rgba(var(--danger-500-rgb), 0.05);
  border: 1px solid rgba(var(--danger-500-rgb), 0.2);
  border-radius: var(--radius-lg);
  padding: var(--spacing-4);
}

.danger-zone-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-4);
}

.danger-zone-info {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-3);

  strong {
    color: var(--text-primary);
    font-size: var(--text-sm);
  }
}

.danger-icon {
  width: 20px;
  height: 20px;
  stroke: var(--danger-color);
  fill: none;
  flex-shrink: 0;
  margin-top: 2px;
}

.danger-description {
  margin: var(--spacing-1) 0 0 0;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

// History Header
.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-4);
  gap: var(--spacing-4);
  flex-wrap: wrap;
}

.view-controls {
  display: flex;
  gap: var(--spacing-3);
  align-items: center;
}

.select-wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.select-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  stroke: var(--text-secondary);
  fill: none;
  pointer-events: none;
  z-index: 1;
  flex-shrink: 0;
}

.sort-select {
  padding: var(--spacing-2) var(--spacing-4);
  padding-left: 38px;
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  min-width: 160px;
  min-height: 44px;

  &:hover {
    border-color: var(--primary-color);

    ~ .select-icon {
      stroke: var(--primary-color);
    }
  }

  &:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

// Streams Container
.streams-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.streams-summary {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  padding-bottom: var(--spacing-1);
}

// Settings Tab
.settings-header {
  margin-bottom: var(--spacing-4);
}

.settings-description {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.settings-actions {
  display: flex;
  gap: var(--spacing-3);
  margin-top: var(--spacing-6);
  padding-top: var(--spacing-6);
  border-top: 1px solid var(--border-color);
}

// Events Tab
.events-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-4);
}

.events-count {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.event-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  transition: all v.$duration-200 v.$ease-out;

  &:hover {
    border-color: var(--primary-color);
  }
}

.event-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;

  &.dot-success { background: var(--success-color); }
  &.dot-info { background: var(--info-color); }
  &.dot-danger { background: var(--danger-color); }
  &.dot-warning { background: var(--warning-color); }
  &.dot-default { background: var(--text-tertiary); }
}

.event-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
}

.event-type {
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  color: var(--text-primary);
  word-break: break-all;
}

.event-message {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-time {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.events-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-8);
}

.events-legend {
  margin-top: var(--spacing-4);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-3);
}

.legend-toggle {
  cursor: pointer;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  font-weight: v.$font-medium;
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-3);
  margin-top: var(--spacing-2);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  font-size: var(--text-xs);
  color: var(--text-secondary);

  .event-dot {
    width: 8px;
    height: 8px;
  }
}

// Animations
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

// Responsive
@include m.respond-below('lg') {
  .compact-avatar {
    width: 56px;
    height: 56px;
  }

  .compact-name {
    font-size: var(--text-lg);
  }

  .stats-section {
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }
}

@include m.respond-below('md') {
  .streamer-control-body {
    flex-direction: column;
    align-items: stretch;
    gap: var(--spacing-3);
  }

  .streamer-control-topline {
    align-items: flex-start;
  }

  .streamer-identity-area {
    min-width: 0;
  }

  .compact-avatar {
    width: 48px;
    height: 48px;
  }

  .compact-info {
    min-width: 0;
  }

  .compact-stats {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .compact-actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .latest-stream-card {
    flex-direction: column;
    align-items: flex-start;
  }

  .danger-zone-content {
    flex-direction: column;
    align-items: stretch;
  }

  .danger-zone-info {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .history-header {
    flex-direction: column;
    align-items: stretch;
    gap: var(--spacing-3);
  }

  .sort-select {
    width: 100%;
  }

  .stats-section {
    grid-template-columns: 1fr;
    gap: var(--spacing-3);
  }
}

@include m.respond-below('sm') {
  .streamer-control-header {
    padding: var(--spacing-3);
  }

  .streamer-control-topline {
    flex-direction: column;
    gap: var(--spacing-3);
  }

  .streamer-status-strip {
    justify-content: flex-start;
  }

  .compact-stat {
    min-width: 0;
    padding-inline: var(--spacing-2);
  }

  .streams-summary {
    text-align: center;
  }
}
</style>
