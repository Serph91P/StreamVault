<template>
  <GlassCard
    tag="article"
    variant="subtle"
    class="stream-card"
    :class="{
      'is-expanded': isExpanded
    }"
  >
    <div class="stream-card-content">
      <!-- Compact View (Always Visible) -->
      <div class="stream-compact">
        <div class="stream-summary">
          <h3 class="stream-title">
            {{ stream.title || 'Untitled Stream' }}
          </h3>
          <div class="stream-meta">
            <time class="stream-start" :datetime="stream.started_at || undefined">
              {{ formatDateShort(stream.started_at) }}
            </time>
            <span class="meta-separator" aria-hidden="true">&middot;</span>
            <span class="stream-duration">{{ formatDuration(stream.started_at, stream.ended_at) }}</span>
            <template v-if="stream.category_name">
              <span class="meta-separator" aria-hidden="true">&middot;</span>
              <span class="category-badge">
                <svg class="icon" aria-hidden="true">
                  <use href="#icon-gamepad" />
                </svg>
                {{ stream.category_name }}
              </span>
            </template>
          </div>
        </div>

        <div class="stream-status" :aria-label="statusSummary">
          <StatusBadge
            class="stream-lifecycle"
            :tone="isLive ? 'live' : 'neutral'"
            size="sm"
            :dot="isLive"
            :pulse="isLive"
            :uppercase="false"
          >
            {{ isLive ? 'In progress' : 'Ended' }}
          </StatusBadge>
          <span class="stream-recording-availability">
            {{ hasRecording ? 'Recording available' : 'Recording unavailable' }}
          </span>
        </div>

        <!-- Expand Icon -->
        <button
          class="expand-btn"
          :class="{ rotated: isExpanded }"
          :aria-label="isExpanded ? 'Collapse stream details' : 'Expand stream details'"
          :aria-expanded="isExpanded"
          :aria-controls="detailsId"
          type="button"
          @click="toggleExpand"
          @keydown.enter.stop
          @keydown.space.stop
        >
          <svg class="icon">
            <use href="#icon-chevron-down" />
          </svg>
        </button>
      </div>

      <!-- Expanded View (Collapsible) -->
      <transition name="expand">
        <div
          v-if="isExpanded"
          :id="detailsId"
          class="stream-expanded"
          role="region"
          :aria-label="`Details for ${stream.title || 'Untitled Stream'}`"
        >
          <!-- Stream Information Panel -->
          <div class="info-panel">
            <h4 class="panel-title">Stream Information</h4>
            <div class="info-grid">
              <div class="info-item">
                <svg class="info-icon">
                  <use href="#icon-clock" />
                </svg>
                <div class="info-text">
                  <span class="info-label">Duration</span>
                  <span class="info-value">{{ formatDuration(stream.started_at, stream.ended_at) }}</span>
                </div>
              </div>
              <div class="info-item">
                <svg class="info-icon">
                  <use href="#icon-calendar" />
                </svg>
                <div class="info-text">
                  <span class="info-label">Started</span>
                  <span class="info-value">{{ formatDate(stream.started_at) }}</span>
                </div>
              </div>
              <div v-if="stream.language" class="info-item">
                <svg class="info-icon">
                  <use href="#icon-globe" />
                </svg>
                <div class="info-text">
                  <span class="info-label">Language</span>
                  <span class="info-value">{{ stream.language?.toUpperCase() }}</span>
                </div>
              </div>
              <div class="info-item">
                <svg class="info-icon">
                  <use href="#icon-hash" />
                </svg>
                <div class="info-text">
                  <span class="info-label">Stream ID</span>
                  <span class="info-value">{{ stream.id }}</span>
                </div>
              </div>
              <div v-if="stream.twitch_stream_id" class="info-item">
                <svg class="info-icon">
                  <use href="#icon-twitch" />
                </svg>
                <div class="info-text">
                  <span class="info-label">Twitch Stream ID</span>
                  <span class="info-value">{{ stream.twitch_stream_id }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Categories Timeline -->
          <div v-if="categoryEvents.length > 0" class="categories-panel">
            <h4 class="panel-title">Categories</h4>
            <div class="categories-timeline">
              <div
                v-for="(event, index) in categoryEvents"
                :key="index"
                class="category-event"
              >
                <div class="category-icon">
                  <svg class="icon">
                    <use href="#icon-gamepad" />
                  </svg>
                </div>
                <div class="category-info">
                  <span class="category-name">{{ event.category_name }}</span>
                  <span class="category-duration">{{ formatEventDuration(event, index) }}</span>
                </div>
              </div>
            </div>
          </div>

          <button
            v-if="hasRecording && !isLive"
            @click.stop="handleWatch"
            class="btn-watch"
            type="button"
          >
            <svg class="icon">
              <use href="#icon-play" />
            </svg>
            Watch Recording
          </button>

          <div class="expanded-actions" role="group" aria-label="Stream actions">
            <button v-if="isLive" @click.stop="handleWatchLive" class="action-item" type="button">
              <svg class="icon">
                <use href="#icon-external-link" />
              </svg>
              Watch Live
            </button>
            <button v-if="isLive" @click.stop="handleForceRecord" class="action-item" type="button">
              <svg class="icon">
                <use href="#icon-video" />
              </svg>
              Force Record
            </button>
            <button @click.stop="handleDelete" class="action-item action-danger" type="button">
              <svg class="icon">
                <use href="#icon-trash" />
              </svg>
              Delete Stream
            </button>
          </div>
        </div>
      </transition>
    </div>
  </GlassCard>
</template>

<script setup lang="ts">
import { ref, computed, useId } from 'vue'
import type { Stream, StreamEvent } from '@/types/streams'
import StatusBadge from '@/components/base/StatusBadge.vue'
import GlassCard from './GlassCard.vue'

interface Props {
  stream: Stream
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'watch-live': [stream: Stream]
  'force-record': [stream: Stream]
  watch: [stream: Stream]
  delete: [stream: Stream]
}>()

const isExpanded = ref(false)
const detailsId = useId()

const isLive = computed(() => props.stream.ended_at == null)
const hasRecording = computed(() => Boolean(props.stream.recording_path?.trim()))
const statusSummary = computed(() => {
  const lifecycle = isLive.value ? 'in progress' : 'ended'
  const availability = hasRecording.value ? 'recording available' : 'recording unavailable'
  return `Stream ${lifecycle}, ${availability}`
})

// Filter category change events
const categoryEvents = computed(() => {
  if (!props.stream.events) return []
  // Backend sends 'channel.update' for category changes
  return props.stream.events.filter(e =>
    e.event_type === 'channel.update' || e.event_type === 'category_change'
  )
})

function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

function formatDuration(start: string | null, end: string | null) {
  if (!start) return '-'

  const startDate = new Date(start)
  const endDate = end ? new Date(end) : new Date()

  const diffMs = endDate.getTime() - startDate.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const hours = Math.floor(diffMins / 60)
  const mins = diffMins % 60

  if (hours > 0) {
    return `${hours}h ${mins}m`
  }
  return `${mins}m`
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '-'

  const date = new Date(dateStr)
  return date.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function formatDateShort(dateStr: string | null) {
  if (!dateStr) return 'Start unavailable'

  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatEventDuration(event: StreamEvent, index: number) {
  if (!event.timestamp) return ''

  const eventDate = new Date(event.timestamp)
  const nextEvent = categoryEvents.value[index + 1]

  let endDate: Date
  if (nextEvent && nextEvent.timestamp) {
    endDate = new Date(nextEvent.timestamp)
  } else if (props.stream.ended_at) {
    endDate = new Date(props.stream.ended_at)
  } else {
    endDate = new Date()
  }

  const diffMs = endDate.getTime() - eventDate.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const hours = Math.floor(diffMins / 60)
  const mins = diffMins % 60

  if (hours > 0) {
    return `${hours}h ${mins}m`
  }
  return `${mins}m`
}

function handleWatchLive() {
  emit('watch-live', props.stream)
}

function handleForceRecord() {
  emit('force-record', props.stream)
}

function handleWatch() {
  emit('watch', props.stream)
}

function handleDelete() {
  emit('delete', props.stream)
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.stream-card {
  touch-action: pan-y;

  :deep(.glass-card-content) {
    padding: 0;
    overflow: hidden;
  }

  &.actions-open {
    position: relative;
    z-index: 100;
  }
}

.stream-card-content {
  display: flex;
  flex-direction: column;
  position: relative;
  touch-action: pan-y;
}

/* Compact View */
.stream-compact {
  min-height: 72px;
  padding: var(--spacing-4);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto 44px;
  align-items: center;
  gap: var(--spacing-3);
  touch-action: pan-y;
}

.stream-summary {
  min-width: 0;
}

.stream-title {
  font-size: var(--text-lg);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  line-height: 1.25;
}

.stream-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-1);
  min-width: 0;
  margin-top: var(--spacing-1);
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.stream-start,
.stream-duration {
  white-space: nowrap;
}

.meta-separator {
  color: var(--text-tertiary);
}

.category-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  max-width: 220px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;

  .icon {
    width: 14px;
    height: 14px;
    stroke: currentColor;
    fill: none;
  }
}

.stream-status {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--spacing-1);
  flex-shrink: 0;
}

.stream-recording-availability {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  white-space: nowrap;
}

.expand-btn {
  width: 44px;
  height: 44px;
  padding: 0;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 18px;
    height: 18px;
    stroke: var(--text-secondary);
    fill: none;
    transition: transform v.$duration-200 v.$ease-out;
  }

  &.rotated .icon {
    transform: rotate(180deg);
  }

  &:hover {
    background: rgba(var(--primary-500-rgb), 0.1);
    border-color: var(--primary-color);

    .icon {
      stroke: var(--primary-color);
    }
  }
}

/* Expanded View */
.stream-expanded {
  padding: 0 var(--spacing-4) var(--spacing-4);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
  padding-top: var(--spacing-4);
}

.expand-enter-active,
.expand-leave-active {
  transition: all v.$duration-300 v.$ease-out;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 800px;
}

/* Info Panel */
.info-panel,
.categories-panel {
  background: rgba(var(--background-darker-rgb), 0.5);
  border-radius: var(--radius-md);
  padding: var(--spacing-3);
}

.panel-title {
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 var(--spacing-3);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-3);
}

.info-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-2);
}

.info-icon {
  width: 18px;
  height: 18px;
  stroke: var(--primary-color);
  fill: none;
  flex-shrink: 0;
  margin-top: 2px;
}

.info-text {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
  min-width: 0;
}

.info-label {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.info-value {
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Categories Timeline */
.categories-timeline {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.category-event {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2);
  background: rgba(var(--primary-500-rgb), 0.05);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--primary-color);
}

.category-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--primary-500-rgb), 0.1);
  border-radius: var(--radius-sm);
  flex-shrink: 0;

  .icon {
    width: 18px;
    height: 18px;
    stroke: var(--primary-color);
    fill: none;
  }
}

.category-info {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-2);
}

.category-name {
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  color: var(--text-primary);
}

.category-duration {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  white-space: nowrap;
}

/* Watch Button */
.btn-watch {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  min-height: 44px;
  padding: var(--spacing-3) var(--spacing-4);
  background: var(--primary-color);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: v.$font-semibold;
  color: white;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
  }

  &:hover {
    background: var(--primary-600);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }

  &:active {
    transform: translateY(0);
  }
}

.expanded-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
  align-items: center;
}

.expanded-actions .action-item {
  width: auto;
  min-height: 44px;
  border: 1px solid var(--border-color);
  background: var(--background-darker);
}

.action-item {
  width: 100%;
  padding: var(--spacing-2) var(--spacing-3);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  transition: background v.$duration-150 v.$ease-out;

  .icon {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
    flex-shrink: 0;
  }

  &:hover {
    background: rgba(var(--primary-500-rgb), 0.1);
  }

  &.action-danger {
    color: var(--danger-color);

    &:hover {
      background: rgba(var(--danger-500-rgb), 0.1);
    }
  }
}

/* Mobile Responsive */
@include m.respond-below('sm') {
  .stream-compact {
    min-height: 80px;
    grid-template-columns: minmax(0, 1fr) 44px;
    padding: var(--spacing-3);
  }

  .stream-status {
    grid-column: 1 / 2;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
  }

  .stream-recording-availability {
    white-space: normal;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
