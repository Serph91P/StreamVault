<template>
  <div class="page-view home-view">
    <section class="dashboard-hero" aria-labelledby="dashboard-title">
      <div class="hero-copy">
        <StatusBadge
          :tone="connectionBadgeTone"
          size="sm"
          dot
          :pulse="realtime.connectionStatus === 'connected'"
        >
          {{ connectionLabel }}
        </StatusBadge>
        <h1 id="dashboard-title">Dashboard</h1>
        <p>
          Monitor live streams, active recordings, queue health and the latest media from one operational view.
        </p>
      </div>

      <div class="hero-actions">
        <router-link to="/add-streamer" class="hero-action hero-action-primary">
          <svg aria-hidden="true"><use href="#icon-users" /></svg>
          Add Streamer
        </router-link>
        <router-link to="/videos" class="hero-action">
          <svg aria-hidden="true"><use href="#icon-film" /></svg>
          Open Library
        </router-link>
      </div>
    </section>

    <section class="summary-section" aria-label="Operational status">
      <div v-if="isLoadingStreamers || isLoadingRecordings" class="stats-grid">
        <LoadingSkeleton
          v-for="i in 5"
          :key="`summary-skeleton-${i}`"
          type="status"
        />
      </div>

      <div v-else class="stats-grid">
        <StatusCard
          v-for="metric in dashboardMetrics"
          :key="metric.label"
          :value="metric.value"
          :label="metric.label"
          :subtitle="metric.subtitle"
          :icon="metric.icon"
          :type="metric.type"
          :show-progress="metric.showProgress"
          :progress="metric.progress"
        />
      </div>
    </section>

    <div class="dashboard-layout">
      <main class="dashboard-main" aria-label="Dashboard primary content">
        <BasePanel labelled-by="live-section-title" tone="strong" class="dashboard-panel live-panel">
          <template #title>
            <span id="live-section-title" class="panel-title-inline">
              <span class="live-dot" aria-hidden="true" />
              Live Streamers
            </span>
          </template>
          <template #description>
            Streams that are currently online and ready to watch or record.
          </template>
          <template #actions>
            <StatusBadge tone="live" size="sm" dot :pulse="liveStreamers.length > 0">
              {{ liveStreamers.length }} live
            </StatusBadge>
          </template>

          <div v-if="streamersError" class="inline-error" role="alert">
            <svg aria-hidden="true"><use href="#icon-alert-circle" /></svg>
            <span>{{ streamersError }}</span>
            <button type="button" @click="fetchStreamers">Retry</button>
          </div>

          <div v-if="isLoadingStreamers" class="grid-scroll-hybrid dashboard-card-grid">
            <LoadingSkeleton
              v-for="i in 4"
              :key="`live-skeleton-${i}`"
              type="streamer"
              class="live-card"
            />
          </div>

          <EmptyState
            v-else-if="liveStreamers.length === 0 && totalStreamers === 0"
            variant="compact"
            title="Welcome to StreamVault"
            description="Add your first streamer to start recording streams automatically."
            icon="users"
            action-label="Add Streamer"
            action-icon="plus"
            :show-decoration="false"
            @action="navigateToAddStreamer"
          />

          <EmptyState
            v-else-if="liveStreamers.length === 0"
            variant="compact"
            title="No Live Streams"
            description="No tracked streamer is live right now. Recent recordings and queue state stay available below."
            icon="video-off"
            :show-decoration="false"
          />

          <div v-else class="grid-scroll-hybrid dashboard-card-grid">
            <StreamerCard
              v-for="streamer in liveStreamers"
              :key="streamer.id"
              :streamer="streamer"
              class="live-card"
              @force-record="handleForceRecord"
            />
          </div>
        </BasePanel>

        <BasePanel labelled-by="recordings-section-title" class="dashboard-panel">
          <template #title>
            <span id="recordings-section-title">Active Recordings</span>
          </template>
          <template #description>
            Recording sessions reported by the backend and realtime updates.
          </template>
          <template #actions>
            <StatusBadge tone="recording" size="sm" dot :pulse="activeRecordings.length > 0">
              {{ activeRecordings.length }} recording
            </StatusBadge>
          </template>

          <div v-if="recordingsError" class="inline-error" role="alert">
            <svg aria-hidden="true"><use href="#icon-alert-circle" /></svg>
            <span>{{ recordingsError }}</span>
            <button type="button" @click="fetchActiveRecordings">Retry</button>
          </div>

          <div v-if="isLoadingRecordings" class="recording-list">
            <LoadingSkeleton
              v-for="i in 3"
              :key="`recording-skeleton-${i}`"
              type="status"
            />
          </div>

          <EmptyState
            v-else-if="activeRecordings.length === 0"
            variant="compact"
            title="No Active Recordings"
            description="Active recordings will appear here as soon as a tracked stream starts recording."
            icon="video"
            :show-decoration="false"
          />

          <div v-else class="recording-list">
            <article
              v-for="recording in visibleActiveRecordings"
              :key="recordingKey(recording)"
              class="recording-card"
            >
              <div class="recording-card-main">
                <StatusBadge tone="recording" size="sm" dot pulse>Recording</StatusBadge>
                <h3>{{ recordingTitle(recording) }}</h3>
                <p>{{ recordingSubtitle(recording) }}</p>
              </div>
              <div class="recording-card-actions">
                <router-link :to="recordingStreamerLink(recording)">Streamer</router-link>
                <router-link :to="recordingLiveLink(recording)">Live</router-link>
              </div>
            </article>
          </div>
        </BasePanel>

        <BasePanel labelled-by="recent-section-title" class="dashboard-panel">
          <template #title>
            <span id="recent-section-title">Latest Videos</span>
          </template>
          <template #description>
            Recently completed recordings, sorted newest first.
          </template>
          <template #actions>
            <router-link to="/videos" class="view-all-link">
              View All
              <svg class="arrow-icon" aria-hidden="true">
                <use href="#icon-arrow-right" />
              </svg>
            </router-link>
          </template>

          <div v-if="videosError" class="inline-error" role="alert">
            <svg aria-hidden="true"><use href="#icon-alert-circle" /></svg>
            <span>{{ videosError }}</span>
            <button type="button" @click="fetchVideos">Retry</button>
          </div>

          <div v-if="isLoadingVideos" class="grid-recordings dashboard-video-grid">
            <LoadingSkeleton
              v-for="i in 6"
              :key="`video-skeleton-${i}`"
              type="video"
            />
          </div>

          <EmptyState
            v-else-if="recentRecordings.length === 0"
            title="No Recordings Yet"
            description="Start recording your favorite streamers to see completed videos here."
            icon="video"
            action-label="Add Streamer"
            action-icon="plus"
            @action="navigateToAddStreamer"
          />

          <div v-else class="grid-recordings dashboard-video-grid">
            <VideoCard
              v-for="video in recentRecordings"
              :key="video.id"
              :video="video"
              @click="playVideo(video)"
            />
          </div>
        </BasePanel>
      </main>

      <aside class="dashboard-sidebar" aria-label="Dashboard side content">
        <BasePanel labelled-by="queue-section-title" class="dashboard-panel queue-panel">
          <template #title>
            <span id="queue-section-title">Queue</span>
          </template>
          <template #description>
            Background work for recordings and processing.
          </template>
          <template #actions>
            <StatusBadge :tone="queueBadgeTone" size="sm" dot>
              {{ queueStateLabel }}
            </StatusBadge>
          </template>

          <div class="queue-progress" aria-label="Average active task progress">
            <div class="queue-progress-header">
              <span>Active progress</span>
              <strong>{{ Math.round(totalProgress) }}%</strong>
            </div>
            <div class="queue-progress-bar">
              <span :style="{ width: `${Math.round(totalProgress)}%` }" />
            </div>
          </div>

          <dl class="queue-stats">
            <div>
              <dt>Active</dt>
              <dd>{{ queueStats.active_tasks }}</dd>
            </div>
            <div>
              <dt>Pending</dt>
              <dd>{{ queueStats.pending_tasks }}</dd>
            </div>
            <div>
              <dt>Failed</dt>
              <dd>{{ queueStats.failed_tasks }}</dd>
            </div>
            <div>
              <dt>Workers</dt>
              <dd>{{ queueStats.workers }}</dd>
            </div>
          </dl>

          <div v-if="isLoadingQueue" class="muted-row">Loading queue fallback data.</div>
          <div v-if="queueError" class="muted-row">{{ queueError }}</div>
          <button type="button" class="panel-text-button" @click="refreshQueueFromAPI">
            Refresh queue fallback
          </button>
        </BasePanel>

        <BasePanel labelled-by="failures-section-title" class="dashboard-panel failures-panel">
          <template #title>
            <span id="failures-section-title">Failures and Alerts</span>
          </template>
          <template #description>
            Critical recording and queue events that may need attention.
          </template>

          <EmptyState
            v-if="failureItems.length === 0"
            variant="compact"
            title="No Failures"
            description="Queue and realtime events do not report active failures."
            icon="check-circle"
            :show-decoration="false"
          />

          <ul v-else class="activity-list">
            <li v-for="item in failureItems" :key="item.id" class="activity-item danger-item">
              <StatusBadge tone="danger" size="sm">{{ item.kind }}</StatusBadge>
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.body }}</p>
              </div>
            </li>
          </ul>
        </BasePanel>

        <BasePanel labelled-by="activity-section-title" class="dashboard-panel activity-panel">
          <template #title>
            <span id="activity-section-title">Realtime Activity</span>
          </template>
          <template #description>
            Latest product events from the central realtime store.
          </template>

          <EmptyState
            v-if="recentActivity.length === 0"
            variant="compact"
            title="Waiting for Events"
            description="Realtime stream, recording and notification updates will appear here."
            icon="activity"
            :show-decoration="false"
          />

          <ul v-else class="activity-list">
            <li v-for="event in recentActivity" :key="event.event_id" class="activity-item">
              <StatusBadge :tone="activityTone(event.severity)" size="sm">
                {{ event.severity }}
              </StatusBadge>
              <div>
                <strong>{{ event.title }}</strong>
                <p>{{ event.body }}</p>
              </div>
            </li>
          </ul>
        </BasePanel>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { streamersApi, videoApi, recordingApi, backgroundQueueApi } from '@/services/api'
import { useRealtimeStore } from '@/stores/realtime'
import { useForceRecording } from '@/composables/useForceRecording'
import {
  hasRealtimeEventType,
  toCanonicalNotificationEvent,
  type CanonicalNotificationEvent,
  type NotificationSeverity
} from '@/types/events'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StreamerCard from '@/components/cards/StreamerCard.vue'
import VideoCard from '@/components/cards/VideoCard.vue'
import StatusCard, { type StatusType } from '@/components/cards/StatusCard.vue'
import BasePanel from '@/components/base/BasePanel.vue'
import StatusBadge, { type StatusBadgeTone } from '@/components/base/StatusBadge.vue'

interface StreamerSummary {
  id: number
  username: string
  name?: string
  display_name?: string
  is_live?: boolean
  is_recording?: boolean
  title?: string
  current_title?: string
  category_name?: string
  current_category?: string
  [key: string]: unknown
}

interface VideoSummary {
  id: number
  title: string
  stream_date?: string
  created_at?: string
  [key: string]: unknown
}

interface ActiveRecording {
  id?: string | number
  recording_id?: string | number
  streamer_id?: string | number
  streamer_name?: string
  username?: string
  title?: string
  stream_title?: string
  started_at?: string
  created_at?: string
  status?: string
  [key: string]: unknown
}

interface DashboardMetric {
  label: string
  value: number | string
  subtitle: string
  icon: string
  type: StatusType
  showProgress?: boolean
  progress?: number
}

interface FailureItem {
  id: string
  kind: string
  title: string
  body: string
}

interface QueueTask {
  id: string
  task_type: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'retrying'
  progress: number
  error_message?: string
  [key: string]: unknown
}

interface QueueStats {
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  retried_tasks: number
  pending_tasks: number
  active_tasks: number
  workers: number
  is_running: boolean
}

const router = useRouter()
const realtime = useRealtimeStore()
const realtimeUnsubs: Array<() => void> = []
const { forceStartRecording } = useForceRecording()

const isLoadingStreamers = ref(true)
const isLoadingVideos = ref(true)
const isLoadingRecordings = ref(true)
const isLoadingQueue = ref(false)
const streamersError = ref('')
const videosError = ref('')
const recordingsError = ref('')
const queueError = ref('')

const streamers = ref<StreamerSummary[]>([])
const videos = ref<VideoSummary[]>([])
const activeRecordings = ref<ActiveRecording[]>([])
const activeTasks = ref<QueueTask[]>([])
const recentTasks = ref<QueueTask[]>([])
const queueStats = ref<QueueStats>({
  total_tasks: 0,
  completed_tasks: 0,
  failed_tasks: 0,
  retried_tasks: 0,
  pending_tasks: 0,
  active_tasks: 0,
  workers: 0,
  is_running: false
})

const liveStreamers = computed(() => streamers.value.filter((s) => s.is_live))
const recordingStreamers = computed(() => streamers.value.filter((s) => s.is_recording))
const totalStreamers = computed(() => streamers.value.length)

const recentRecordings = computed(() => {
  return [...videos.value]
    .sort((a, b) => {
      const dateA = new Date(a.stream_date || a.created_at || 0).getTime()
      const dateB = new Date(b.stream_date || b.created_at || 0).getTime()
      return dateB - dateA
    })
    .slice(0, 6)
})

const visibleActiveRecordings = computed(() => activeRecordings.value.slice(0, 5))

const totalProgress = computed(() => {
  if (activeTasks.value.length === 0) return 0
  const sum = activeTasks.value.reduce((total, task) => total + (task.progress || 0), 0)
  return sum / activeTasks.value.length
})

const recentActivity = computed<CanonicalNotificationEvent[]>(() => {
  return realtime.recentEvents
    .map((event) => toCanonicalNotificationEvent(event))
    .filter((event): event is CanonicalNotificationEvent => Boolean(event))
    .slice(-6)
    .reverse()
})

const failedQueueTasks = computed(() => {
  return recentTasks.value
    .filter((task) => task.status === 'failed')
    .slice(0, 3)
})

const failureItems = computed<FailureItem[]>(() => {
  const queueFailures = failedQueueTasks.value.map((task) => ({
    id: `queue-${task.id}`,
    kind: 'Queue',
    title: task.task_type || 'Background task failed',
    body: task.error_message || 'No error details reported.'
  }))

  const eventFailures = recentActivity.value
    .filter((event) => event.severity === 'critical' || event.severity === 'error')
    .map((event) => ({
      id: `event-${event.event_id}`,
      kind: 'Event',
      title: event.title,
      body: event.body
    }))

  return [...queueFailures, ...eventFailures].slice(0, 5)
})

const connectionLabel = computed(() => {
  switch (realtime.connectionStatus) {
    case 'connected':
      return 'Realtime connected'
    case 'connecting':
      return 'Realtime connecting'

    default:
      return 'Realtime offline'
  }
})

const connectionBadgeTone = computed<StatusBadgeTone>(() => {
  if (realtime.connectionStatus === 'connected') return 'success'
  if (realtime.connectionStatus === 'connecting') return 'warning'
  return 'danger'
})

const queueStateLabel = computed(() => {
  if (queueStats.value.active_tasks > 0) return 'Active'
  if (queueStats.value.pending_tasks > 0) return 'Queued'
  if (queueStats.value.failed_tasks > 0) return 'Needs attention'
  return queueStats.value.is_running ? 'Idle' : 'Paused'
})

const queueBadgeTone = computed<StatusBadgeTone>(() => {
  if (queueStats.value.failed_tasks > 0) return 'danger'
  if (queueStats.value.active_tasks > 0) return 'processing'
  if (queueStats.value.pending_tasks > 0) return 'warning'
  return queueStats.value.is_running ? 'success' : 'neutral'
})

const dashboardMetrics = computed<DashboardMetric[]>(() => [
  {
    label: 'Live Now',
    value: liveStreamers.value.length,
    subtitle: `${totalStreamers.value} tracked streamers`,
    icon: 'radio',
    type: liveStreamers.value.length > 0 ? 'danger' : 'info'
  },
  {
    label: 'Recording',
    value: activeRecordings.value.length,
    subtitle: `${recordingStreamers.value.length} streamers marked recording`,
    icon: 'video',
    type: activeRecordings.value.length > 0 ? 'warning' : 'success'
  },
  {
    label: 'Queue',
    value: queueStats.value.active_tasks + queueStats.value.pending_tasks,
    subtitle: queueStateLabel.value,
    icon: 'activity',
    type: queueStats.value.failed_tasks > 0 ? 'danger' : 'primary',
    showProgress: activeTasks.value.length > 0,
    progress: Math.round(totalProgress.value)
  },
  {
    label: 'Failures',
    value: failureItems.value.length,
    subtitle: failureItems.value.length > 0 ? 'Needs review' : 'No active alerts',
    icon: failureItems.value.length > 0 ? 'alert-triangle' : 'check-circle',
    type: failureItems.value.length > 0 ? 'danger' : 'success'
  },
  {
    label: 'Latest Videos',
    value: recentRecordings.value.length,
    subtitle: 'Ready in library',
    icon: 'film',
    type: 'info'
  }
])

async function fetchStreamers() {
  isLoadingStreamers.value = true
  streamersError.value = ''
  try {
    const response = await streamersApi.getAll()
    streamers.value = response?.streamers || []
  } catch (error) {
    console.error('Failed to fetch streamers:', error)
    streamersError.value = 'Could not load streamer status.'
    streamers.value = []
  } finally {
    isLoadingStreamers.value = false
  }
}

async function fetchVideos() {
  isLoadingVideos.value = true
  videosError.value = ''
  try {
    const response = await videoApi.getAll({ limit: 12 })
    videos.value = response || []
  } catch (error) {
    console.error('Failed to fetch videos:', error)
    videosError.value = 'Could not load latest videos.'
    videos.value = []
  } finally {
    isLoadingVideos.value = false
  }
}

async function fetchActiveRecordings() {
  isLoadingRecordings.value = true
  recordingsError.value = ''
  try {
    const response = await recordingApi.getActiveRecordings()
    activeRecordings.value = Array.isArray(response) ? response : response?.active_recordings || []
  } catch (error) {
    console.error('Failed to fetch active recordings:', error)
    recordingsError.value = 'Could not load active recordings.'
    activeRecordings.value = []
  } finally {
    isLoadingRecordings.value = false
  }
}

async function refreshQueueFromAPI() {
  isLoadingQueue.value = true
  queueError.value = ''
  try {
    const [stats, active, recent] = await Promise.all([
      backgroundQueueApi.getStats(),
      backgroundQueueApi.getActiveTasks(),
      backgroundQueueApi.getRecentTasks()
    ])

    queueStats.value = stats
    activeTasks.value = Array.isArray(active) ? active : []
    recentTasks.value = Array.isArray(recent) ? recent : []
  } catch (error) {
    console.error('Failed to refresh queue:', error)
    queueError.value = 'Queue fallback is unavailable.'
  } finally {
    isLoadingQueue.value = false
  }
}

function navigateToAddStreamer() {
  router.push('/add-streamer')
}

function playVideo(video: VideoSummary) {
  router.push(`/videos/${video.id}`)
}

async function handleForceRecord(streamer: { id: number }) {
  await forceStartRecording(streamer.id, async () => {
    await Promise.all([fetchStreamers(), fetchActiveRecordings()])
  })
}

function recordingKey(recording: ActiveRecording) {
  return String(recording.id ?? recording.recording_id ?? recording.streamer_id ?? recording.streamer_name ?? recording.title)
}

function recordingTitle(recording: ActiveRecording) {
  return recording.title || recording.stream_title || `${recording.streamer_name || recording.username || 'Unknown streamer'} recording`
}

function recordingSubtitle(recording: ActiveRecording) {
  const name = recording.streamer_name || recording.username || 'Unknown streamer'
  const started = recording.started_at || recording.created_at
  if (!started) return name

  const date = new Date(started)
  if (Number.isNaN(date.getTime())) return name
  return `${name} started ${date.toLocaleString()}`
}

function recordingStreamerLink(recording: ActiveRecording) {
  return recording.streamer_id ? `/streamers/${recording.streamer_id}` : '/streamers'
}

function recordingLiveLink(recording: ActiveRecording) {
  const target = recording.streamer_name || recording.username || recording.streamer_id
  return target ? `/live/${target}` : '/streamers'
}

function activityTone(severity: NotificationSeverity): StatusBadgeTone {
  if (severity === 'critical' || severity === 'error') return 'danger'
  if (severity === 'warning') return 'warning'
  if (severity === 'success') return 'success'
  return 'info'
}

onMounted(() => {
  const updateStreamerFromEvent = (event: any) => {
    const username = event.data?.username || event.data?.streamer_name
    if (!username) return
    const idx = streamers.value.findIndex(
      (s) => s.username?.toLowerCase() === String(username).toLowerCase() ||
        s.name?.toLowerCase() === String(username).toLowerCase()
    )
    if (idx === -1) return

    const streamer = { ...streamers.value[idx] }
    if (hasRealtimeEventType(event, 'stream.online')) {
      streamer.is_live = true
      streamer.title = event.data?.title
      streamer.category_name = event.data?.category_name
    } else if (hasRealtimeEventType(event, 'stream.offline')) {
      streamer.is_live = false
      streamer.title = undefined
      streamer.category_name = undefined
    } else if (hasRealtimeEventType(event, 'channel.update', 'stream.update')) {
      if (event.data?.title) streamer.title = event.data.title
      if (event.data?.category_name) streamer.category_name = event.data.category_name
    }

    streamers.value = [
      ...streamers.value.slice(0, idx),
      streamer,
      ...streamers.value.slice(idx + 1)
    ]
  }

  realtimeUnsubs.push(
    realtime.onEvents(['stream.online', 'stream.offline', 'channel.update', 'stream.update'], updateStreamerFromEvent),

    realtime.onEvent('active_recordings_update', (event) => {
      const list = event.data?.recordings ?? event.data
      if (Array.isArray(list)) activeRecordings.value = list
    }),

    realtime.onEvents(['recording.started', 'recording.stopped'], (event) => {
      if (hasRealtimeEventType(event, 'recording.started')) {
        upsertActiveRecording(event.data)
      } else {
        removeActiveRecording(event.data)
      }
    }),

    realtime.onEvents(['recording.completed', 'recording.failed', 'recording.available'], () => {
      fetchVideos()
      fetchActiveRecordings()
    }),

    realtime.onEvent('background_queue_update', (event) => {
      if (event.data?.stats) Object.assign(queueStats.value, event.data.stats)
      if (Array.isArray(event.data?.active_tasks)) activeTasks.value = event.data.active_tasks
      if (Array.isArray(event.data?.recent_tasks)) recentTasks.value = event.data.recent_tasks
    }),

    realtime.onEvent('queue_stats_update', (event) => {
      Object.assign(queueStats.value, event.data)
    }),

    realtime.onEvent('task_status_update', (event) => {
      updateQueueTask(event.data)
    }),

    realtime.onEvent('task_progress_update', (event) => {
      const task = activeTasks.value.find((item) => item.id === event.data?.task_id)
      if (task) task.progress = event.data?.progress || 0
    }),

    realtime.onEvent('streamer.added', (event) => {
      const newId = event.data?.id
      if (newId && !streamers.value.some((s) => s.id === newId)) fetchStreamers()
    }),

    realtime.onEvent('streamer.removed', (event) => {
      const removedId = event.data?.streamer_id
      if (removedId !== undefined && removedId !== null) {
        streamers.value = streamers.value.filter((s) => String(s.id) !== String(removedId))
      }
    })
  )
})

onUnmounted(() => {
  realtimeUnsubs.forEach((fn) => fn())
})

function upsertActiveRecording(recording: ActiveRecording | undefined) {
  if (!recording) {
    fetchActiveRecordings()
    return
  }

  const recId = recording.id ?? recording.recording_id ?? recording.streamer_id
  const exists = activeRecordings.value.some((current) => {
    const currentId = current.id ?? current.recording_id ?? current.streamer_id
    return currentId !== undefined && recId !== undefined && String(currentId) === String(recId)
  })

  if (!exists) {
    activeRecordings.value = [...activeRecordings.value, recording]
  }

  const username = recording.streamer_name || recording.username
  if (username) markStreamerRecording(username)
}

function removeActiveRecording(recording: ActiveRecording | undefined) {
  const recId = recording?.id ?? recording?.recording_id ?? recording?.streamer_id
  if (recId === undefined) {
    fetchActiveRecordings()
    return
  }

  activeRecordings.value = activeRecordings.value.filter((current) => {
    const currentId = current.id ?? current.recording_id ?? current.streamer_id
    return currentId === undefined || String(currentId) !== String(recId)
  })
}

function markStreamerRecording(username: string) {
  const idx = streamers.value.findIndex(
    (s) => s.username?.toLowerCase() === username.toLowerCase() ||
      s.name?.toLowerCase() === username.toLowerCase()
  )
  if (idx === -1) return

  streamers.value = [
    ...streamers.value.slice(0, idx),
    { ...streamers.value[idx], is_live: true, is_recording: true },
    ...streamers.value.slice(idx + 1)
  ]
}

function updateQueueTask(task: QueueTask | undefined) {
  if (!task?.id) return

  const existingIndex = activeTasks.value.findIndex((item) => item.id === task.id)
  if (existingIndex >= 0) {
    activeTasks.value = [
      ...activeTasks.value.slice(0, existingIndex),
      task,
      ...activeTasks.value.slice(existingIndex + 1)
    ]
  } else if (task.status === 'running' || task.status === 'pending') {
    activeTasks.value = [...activeTasks.value, task]
  }

  if (task.status === 'completed' || task.status === 'failed') {
    activeTasks.value = activeTasks.value.filter((item) => item.id !== task.id)
    recentTasks.value = [task, ...recentTasks.value].slice(0, 50)
  }
}

onMounted(async () => {
  await Promise.all([
    fetchStreamers(),
    fetchVideos(),
    fetchActiveRecordings()
  ])
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.home-view {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-6);
}

.dashboard-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--spacing-6);
  padding: var(--spacing-8);
  border: 1px solid var(--glass-border, var(--border-color));
  border-radius: var(--radius-2xl);
  background:
    radial-gradient(circle at top left, rgba(var(--primary-color-rgb), 0.24), transparent 34rem),
    var(--glass-bg-medium, var(--background-card));
  box-shadow: var(--glass-shadow-md, 0 12px 40px rgba(0, 0, 0, 0.24));
  overflow: hidden;
}

.hero-copy {
  max-width: 720px;

  h1 {
    margin: var(--spacing-3) 0 var(--spacing-2);
    color: var(--text-primary);
    font-size: clamp(2rem, 5vw, 4rem);
    line-height: 1;
    font-weight: v.$font-bold;
  }

  p {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--text-lg);
    line-height: v.$leading-relaxed;
  }
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-3);
  justify-content: flex-end;
}

.hero-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  min-height: 44px;
  padding: var(--spacing-3) var(--spacing-4);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  color: var(--text-primary);
  background: rgba(var(--background-darker-rgb, 10, 10, 10), 0.36);
  text-decoration: none;
  font-weight: v.$font-semibold;
  transition: all v.$duration-200 v.$ease-out;

  svg {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
  }

  &:hover {
    transform: translateY(-1px);
    border-color: var(--primary-color);
    color: var(--primary-color);
  }
}

.hero-action-primary {
  border-color: rgba(var(--primary-color-rgb), 0.38);
  background: rgba(var(--primary-color-rgb), 0.18);
  color: var(--primary-color);
}

.summary-section,
.dashboard-panel {
  min-width: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: var(--spacing-4);
}

.dashboard-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.38fr);
  gap: var(--spacing-6);
  align-items: start;
}

.dashboard-main,
.dashboard-sidebar {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-6);
  min-width: 0;
}

.panel-title-inline {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
}

.live-dot {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 999px;
  background: var(--danger-color);
  box-shadow: 0 0 0 6px rgba(var(--danger-color-rgb), 0.14);
}

.dashboard-card-grid,
.dashboard-video-grid {
  padding: 0;
}

.live-card {
  animation: fade-in v.$duration-300 v.$ease-out;

  @for $i from 1 through 10 {
    &:nth-child(#{$i}) {
      animation-delay: #{$i * 50}ms;
    }
  }
}

.recording-list,
.activity-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.recording-card,
.activity-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-4);
  padding: var(--spacing-4);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: rgba(var(--background-darker-rgb, 10, 10, 10), 0.28);
}

.recording-card-main,
.activity-item > div {
  min-width: 0;

  h3,
  strong {
    display: block;
    margin: var(--spacing-2) 0 var(--spacing-1);
    color: var(--text-primary);
    font-size: var(--text-base);
    font-weight: v.$font-semibold;
  }

  p {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--text-sm);
    line-height: v.$leading-relaxed;
  }
}

.recording-card-actions {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--spacing-2);

  a {
    min-height: 36px;
    display: inline-flex;
    align-items: center;
    padding: 0 var(--spacing-3);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-full);
    color: var(--primary-color);
    text-decoration: none;
    font-size: var(--text-sm);
    font-weight: v.$font-semibold;
  }
}

.view-all-link,
.panel-text-button,
.inline-error button {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  min-height: 36px;
  border: 0;
  background: transparent;
  color: var(--primary-color);
  text-decoration: none;
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  cursor: pointer;
}

.arrow-icon {
  width: 16px;
  height: 16px;
  stroke: currentColor;
  fill: none;
}

.inline-error {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-4);
  padding: var(--spacing-3) var(--spacing-4);
  border: 1px solid rgba(var(--danger-color-rgb), 0.28);
  border-radius: var(--radius-lg);
  background: rgba(var(--danger-color-rgb), 0.12);
  color: var(--danger-color);

  svg {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
  }
}

.queue-progress {
  margin-bottom: var(--spacing-4);
}

.queue-progress-header {
  display: flex;
  justify-content: space-between;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-2);
  color: var(--text-secondary);
  font-size: var(--text-sm);

  strong {
    color: var(--text-primary);
  }
}

.queue-progress-bar {
  height: 8px;
  overflow: hidden;
  border-radius: var(--radius-full);
  background: var(--background-darker);

  span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--primary-color), var(--accent-color));
    transition: width v.$duration-300 v.$ease-out;
  }
}

.queue-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--spacing-3);
  margin: 0 0 var(--spacing-4);

  div {
    padding: var(--spacing-3);
    border-radius: var(--radius-md);
    background: rgba(var(--background-darker-rgb, 10, 10, 10), 0.26);
  }

  dt {
    color: var(--text-secondary);
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  dd {
    margin: var(--spacing-1) 0 0;
    color: var(--text-primary);
    font-size: var(--text-2xl);
    font-weight: v.$font-bold;
  }
}

.muted-row {
  margin-bottom: var(--spacing-3);
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.danger-item {
  border-color: rgba(var(--danger-color-rgb), 0.24);
}

@include m.respond-below('xl') {
  .dashboard-layout {
    grid-template-columns: 1fr;
  }
}

@include m.respond-below('md') {
  .dashboard-hero {
    align-items: flex-start;
    flex-direction: column;
    padding: var(--spacing-5);
  }

  .hero-actions {
    justify-content: flex-start;
    width: 100%;
  }

  .hero-action {
    flex: 1 1 180px;
  }

  .recording-card,
  .activity-item {
    flex-direction: column;
  }

  .recording-card-actions {
    width: 100%;
    justify-content: flex-start;
  }
}

@include m.respond-below('sm') {
  .home-view {
    gap: var(--spacing-4);
  }

  .hero-copy p {
    font-size: var(--text-base);
  }

  .stats-grid,
  .queue-stats {
    grid-template-columns: 1fr;
  }
}

@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
