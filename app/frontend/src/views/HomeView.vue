<template>
  <div class="page-view home-view">

    <section class="dashboard-brief" aria-labelledby="dashboard-brief-title">
      <div class="brief-header">
        <div>
          <p class="section-eyebrow">At a glance</p>
          <h2 id="dashboard-brief-title">{{ dashboardStateHeadline }}</h2>
          <p>{{ dashboardStateDescription }}</p>
        </div>
      </div>
      <div class="brief-grid" aria-label="Dashboard status snapshot">
        <!-- Tiles with a matching destination (live/recording filters) are
             links; pure status tiles (queue, errors, activity) are not -
             they used to all point at the library, which led nowhere useful. -->
        <component
          :is="item.route ? 'router-link' : 'div'"
          v-for="item in dashboardBriefItems"
          :key="item.label"
          :to="item.route || undefined"
          class="brief-item"
          :class="[`brief-item-${item.tone}`, { 'brief-item-static': !item.route }]"
        >
          <span class="brief-item-icon" aria-hidden="true">
            <svg><use :href="item.icon" /></svg>
          </span>
          <span>
            <span class="brief-item-label">{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <span class="brief-item-detail">{{ item.detail }}</span>
          </span>
          <span v-if="item.route" class="brief-item-arrow" aria-hidden="true">
            <svg><use href="#icon-chevron-right" /></svg>
          </span>
        </component>
      </div>
    </section>

    <div class="dashboard-layout">
      <div class="dashboard-main" aria-label="Dashboard primary content">
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

          <EmptyState
            v-if="streamersError"
            variant="inline"
            tone="danger"
            title="Could not load live streamers"
            :description="streamersError"
            retry-label="Retry"
            @retry="fetchStreamers"
          />

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
            description="No tracked streamer is live right now. Recent recordings and the dashboard summary stay available below."
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

        <!-- No separate "Active Recordings" panel: a recording session is
             visible as the Recording badge on its live card above, in the
             "Recording" glance tile, and in the header queue monitor. -->

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

          <EmptyState
            v-if="videosError"
            variant="inline"
            tone="danger"
            title="Could not load latest videos"
            :description="videosError"
            retry-label="Retry"
            @retry="fetchVideos"
          />

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
              @play="playVideo(video)"
            />
          </div>
        </BasePanel>
      </div>

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
  type CanonicalNotificationEvent
} from '@/types/events'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StreamerCard from '@/components/cards/StreamerCard.vue'
import VideoCard from '@/components/cards/VideoCard.vue'
import BasePanel from '@/components/base/BasePanel.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'

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

interface DashboardBriefItem {
  label: string
  value: string
  detail: string
  icon: string
  tone: 'live' | 'recording' | 'queue' | 'danger' | 'success' | 'info'
  /** Omitted for pure status tiles that have no meaningful destination */
  route?: string
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
  workers: number | Record<string, unknown> | unknown[]
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
const isDashboardLoading = computed(() => isLoadingStreamers.value || isLoadingRecordings.value || isLoadingQueue.value)

const recentRecordings = computed(() => {
  return [...videos.value]
    .sort((a, b) => {
      const dateA = new Date(a.stream_date || a.created_at || 0).getTime()
      const dateB = new Date(b.stream_date || b.created_at || 0).getTime()
      return dateB - dateA
    })
    .slice(0, 6)
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

const latestActivitySummary = computed(() => {
  const event = recentActivity.value[0]
  if (!event) return 'No recent realtime event yet'
  return event.title || event.body || 'Realtime event received'
})

const dashboardStateHeadline = computed(() => {
  if (failureItems.value.length > 0) return 'Attention needed now'
  if (isDashboardLoading.value && totalStreamers.value === 0 && activeRecordings.value.length === 0) return 'Checking dashboard status'
  if (liveStreamers.value.length > 0) return `${liveStreamers.value.length} streamer${liveStreamers.value.length === 1 ? '' : 's'} live now`
  if (activeRecordings.value.length > 0) return `${activeRecordings.value.length} recording${activeRecordings.value.length === 1 ? '' : 's'} active`
  if (queueStats.value.active_tasks + queueStats.value.pending_tasks > 0) return 'Queue work is in progress'
  return 'All core systems are quiet'
})

const dashboardStateDescription = computed(() => {
  if (failureItems.value.length > 0) return `${failureItems.value.length} alert${failureItems.value.length === 1 ? '' : 's'} need review before the queue looks healthy.`
  if (isDashboardLoading.value && totalStreamers.value === 0 && activeRecordings.value.length === 0) return 'Refreshing live, recording, queue and activity signals for the first read.'
  if (liveStreamers.value.length > 0) return 'Open a live stream, confirm recording, or keep watching queue health from this screen.'
  if (activeRecordings.value.length > 0) return 'Recording is underway. Follow the live session or watch the queue for processing.'
  if (queueStats.value.active_tasks + queueStats.value.pending_tasks > 0) return 'Background jobs are visible here so processing state stays easy to scan.'
  return 'No active failures, recordings or queue work are currently reported.'
})

const dashboardBriefItems = computed<DashboardBriefItem[]>(() => [
  {
    label: 'Live',
    value: isLoadingStreamers.value ? 'Checking' : `${liveStreamers.value.length} online`,
    detail: `${totalStreamers.value} tracked`,
    icon: '#icon-radio',
    tone: liveStreamers.value.length > 0 ? 'live' : 'info',
    route: '/streamers?filter=live'
  },
  {
    label: 'Recording',
    value: isLoadingRecordings.value ? 'Checking' : `${activeRecordings.value.length} active`,
    detail: `${recordingStreamers.value.length} streamer${recordingStreamers.value.length === 1 ? '' : 's'} marked`,
    icon: '#icon-video',
    tone: activeRecordings.value.length > 0 ? 'recording' : 'success',
    route: '/streamers?filter=recording'
  },
  {
    label: 'Queue',
    value: isLoadingQueue.value ? 'Checking' : queueStateLabel.value,
    detail: `${queueStats.value.active_tasks} active, ${queueStats.value.pending_tasks} pending`,
    icon: '#icon-activity',
    tone: queueStats.value.failed_tasks > 0 ? 'danger' : 'queue'
  },
  {
    label: 'Errors',
    value: `${failureItems.value.length} alert${failureItems.value.length === 1 ? '' : 's'}`,
    detail: failureItems.value.length > 0 ? 'Needs review' : 'No active alerts',
    icon: failureItems.value.length > 0 ? '#icon-alert-triangle' : '#icon-check-circle',
    tone: failureItems.value.length > 0 ? 'danger' : 'success'
  },
  {
    label: 'Recent activity',
    value: recentActivity.value.length > 0 ? `${recentActivity.value.length} event${recentActivity.value.length === 1 ? '' : 's'}` : 'Quiet',
    detail: latestActivitySummary.value,
    icon: '#icon-clock',
    tone: recentActivity.value.length > 0 ? 'info' : 'success'
  }
])

const queueStateLabel = computed(() => {
  if (queueStats.value.active_tasks > 0) return 'Active'
  if (queueStats.value.pending_tasks > 0) return 'Queued'
  if (queueStats.value.failed_tasks > 0) return 'Needs attention'
  return queueStats.value.is_running ? 'Idle' : 'Paused'
})

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
  try {
    const response = await recordingApi.getActiveRecordings()
    activeRecordings.value = Array.isArray(response) ? response : response?.active_recordings || []
  } catch (error) {
    console.error('Failed to fetch active recordings:', error)
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
    queueError.value = 'Queue status is unavailable.'
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
    fetchActiveRecordings(),
    refreshQueueFromAPI()
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

.dashboard-brief {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-5);
  padding: var(--spacing-5);
  border: 1px solid var(--glass-border, var(--border-color));
  border-radius: var(--radius-xl);
  background:
    linear-gradient(135deg, rgba(var(--primary-color-rgb), 0.14), transparent 46%),
    rgba(var(--background-darker-rgb, 10, 10, 10), 0.34);
  box-shadow: var(--glass-shadow-sm, 0 8px 24px rgba(0, 0, 0, 0.18));
}

.brief-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-4);

  h2 {
    margin: var(--spacing-1) 0 var(--spacing-2);
    color: var(--text-primary);
    font-size: clamp(1.35rem, 3vw, 2rem);
    line-height: 1.1;
    font-weight: v.$font-bold;
  }

  p {
    margin: 0;
    color: var(--text-secondary);
    line-height: v.$leading-relaxed;
  }
}

.section-eyebrow,
.brief-item-label {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-weight: v.$font-semibold;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.brief-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--spacing-3);
}

.brief-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--spacing-3);
  min-width: 0;
  padding: var(--spacing-4);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: rgba(var(--background-card-rgb, 20, 22, 29), 0.58);
  color: inherit;
  text-decoration: none;
  transition: border-color v.$duration-200 v.$ease-out, transform v.$duration-200 v.$ease-out, box-shadow v.$duration-200 v.$ease-out;

  strong,
  .brief-item-detail {
    display: block;
    min-width: 0;
  }

  .brief-item-detail {
    overflow-wrap: anywhere;
  }

  strong {
    margin: var(--spacing-1) 0;
    color: var(--text-primary);
    font-size: var(--text-lg);
    font-weight: v.$font-bold;
  }

  &:hover {
    border-color: var(--primary-color);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(var(--primary-color-rgb), 0.15);
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }

  // Pure status tiles: no pointer affordance, no hover lift
  &.brief-item-static {
    cursor: default;

    &:hover {
      border-color: var(--border-color);
      transform: none;
      box-shadow: none;
    }
  }
}

.brief-item-arrow {
  display: flex;
  align-items: center;
  color: var(--text-secondary);
  opacity: 0;

  svg {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
  }

  .brief-item:hover & {
    opacity: 1;
    color: var(--primary-color);
  }
}

.brief-item-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  background: rgba(var(--primary-color-rgb), 0.16);
  color: var(--primary-color);

  svg {
    width: 20px;
    height: 20px;
    stroke: currentColor;
    fill: none;
  }
}

.brief-item-detail {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.brief-item-live .brief-item-icon,
.brief-item-danger .brief-item-icon {
  background: rgba(var(--danger-color-rgb), 0.18);
  color: var(--danger-color);
}

.brief-item-recording .brief-item-icon {
  background: rgba(var(--warning-color-rgb), 0.18);
  color: var(--warning-color);
}

.brief-item-queue .brief-item-icon,
.brief-item-info .brief-item-icon {
  background: rgba(var(--primary-color-rgb), 0.16);
  color: var(--primary-color);
}

.brief-item-success .brief-item-icon {
  background: rgba(var(--success-color-rgb), 0.18);
  color: var(--success-color);
}

.dashboard-panel {
  min-width: 0;
}

.dashboard-layout {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-6);
}

.dashboard-main {
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

.view-all-link,
.panel-text-button {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  min-height: 36px;
  border: 0;
  background: transparent;
  color: var(--text-primary);
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



@include m.respond-below('xl') {
  .brief-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@include m.respond-below('md') {
  .dashboard-brief {
    padding: var(--spacing-4);
  }

  .brief-header {
    flex-direction: column;
  }

  .brief-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .brief-item {
    padding: var(--spacing-3);
  }

  .brief-item:last-child {
    grid-column: 1 / -1;
  }
}

@include m.respond-below('sm') {
  .home-view {
    gap: var(--spacing-4);
  }

  // Two columns get too narrow below 640px and force mid-word breaks in the
  // stat values - stack the snapshot tiles as full-width rows instead.
  .brief-grid {
    grid-template-columns: minmax(0, 1fr);
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
