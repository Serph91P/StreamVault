<template>
  <GlassCard
    variant="medium"
    hoverable
    class="stream-card"
    :class="{ 
      'is-expanded': isExpanded, 
      'actions-open': showActions,
      'is-recording': isRecording 
    }"
  >
    <div class="stream-card-content">
      <!-- Compact View (Always Visible) -->
      <div class="stream-compact" @click="toggleExpand">
        <!-- Stream Title -->
        <h3 class="stream-title">
          {{ stream.title || 'Untitled Stream' }}
        </h3>

        <!-- Category Badge -->
        <div v-if="stream.category_name" class="category-badge">
          <svg class="icon">
            <use href="#icon-gamepad" />
          </svg>
          {{ stream.category_name }}
        </div>

        <!-- Recording Status Badge (Pulsing if recording) -->
        <div v-if="isRecording" class="recording-badge">
          <span class="recording-indicator"></span>
          <span class="recording-text">RECORDING</span>
        </div>

        <!-- Expand Icon -->
        <button class="expand-btn" :class="{ rotated: isExpanded }" @click.stop="toggleExpand">
          <svg class="icon">
            <use href="#icon-chevron-down" />
          </svg>
        </button>
      </div>

      <!-- Expanded View (Collapsible) -->
      <transition name="expand">
        <div v-if="isExpanded" class="stream-expanded">
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

          <!-- Watch Button (if recording finished) -->
          <button
            v-if="hasRecording && !isRecording"
            @click.stop="handleWatch"
            class="btn-watch"
          >
            <svg class="icon">
              <use href="#icon-play" />
            </svg>
            Watch Recording
          </button>
        </div>
      </transition>

      <!-- Context Menu (Top Right) -->
      <div class="stream-actions">
        <button
          ref="moreButtonRef"
          @click.stop="toggleActions"
          class="btn-action btn-more"
          :class="{ active: showActions }"
        >
          <svg class="icon">
            <use href="#icon-more-vertical" />
          </svg>
        </button>

        <Teleport to="body">
          <div
            v-if="showActions"
            class="actions-dropdown"
            :style="dropdownStyle"
            @click.stop
          >
            <button v-if="isRecording" @click="handleWatchLive" class="action-item">
              <svg class="icon">
                <use href="#icon-external-link" />
              </svg>
              Watch Live
            </button>
            <button v-if="!isRecording && isLive" @click="handleForceRecord" class="action-item">
              <svg class="icon">
                <use href="#icon-video" />
              </svg>
              Force Record
            </button>
            <button v-if="hasRecording && !isRecording" @click="handleWatch" class="action-item">
              <svg class="icon">
                <use href="#icon-play" />
              </svg>
              Watch Recording
            </button>
            <button @click="handleDelete" class="action-item action-danger">
              <svg class="icon">
                <use href="#icon-trash" />
              </svg>
              Delete Stream
            </button>
          </div>
        </Teleport>
      </div>
    </div>
  </GlassCard>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import GlassCard from './GlassCard.vue'

interface StreamEvent {
  id: number
  event_type: string
  title?: string
  category_name?: string
  language?: string
  timestamp?: string
}

interface Stream {
  id: number
  streamer_id: number
  started_at?: string
  ended_at?: string
  title?: string
  category_name?: string
  language?: string
  twitch_stream_id?: string
  recording_path?: string
  episode_number?: number
  events?: StreamEvent[]
  is_recording?: boolean
  is_live?: boolean
}

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

const router = useRouter()
const isExpanded = ref(false)
const showActions = ref(false)
const moreButtonRef = ref<HTMLButtonElement | null>(null)

const isRecording = computed(() => props.stream.is_recording || false)
const isLive = computed(() => props.stream.is_live || false)
const hasRecording = computed(() => !!props.stream.recording_path)

// Filter category change events
const categoryEvents = computed(() => {
  if (!props.stream.events) return []
  // Backend sends 'channel.update' for category changes
  return props.stream.events.filter(e => 
    e.event_type === 'channel.update' || e.event_type === 'category_change'
  )
})

// Dropdown positioning
const dropdownStyle = computed(() => {
  if (!moreButtonRef.value) {
    return {
      position: 'fixed' as const,
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      zIndex: 10000
    }
  }

  const rect = moreButtonRef.value.getBoundingClientRect()
  return {
    position: 'fixed' as const,
    top: `${rect.bottom + 8}px`,
    left: `${rect.left - 140}px`,
    zIndex: 10000
  }
})

function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

function toggleActions() {
  showActions.value = !showActions.value
}

function formatDuration(start?: string, end?: string) {
  if (!start) return '—'
  
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

function formatDate(dateStr?: string) {
  if (!dateStr) return '—'
  
  const date = new Date(dateStr)
  return date.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
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
  showActions.value = false
  emit('watch-live', props.stream)
}

function handleForceRecord() {
  showActions.value = false
  emit('force-record', props.stream)
}

function handleWatch() {
  showActions.value = false
  emit('watch', props.stream)
}

function handleDelete() {
  showActions.value = false
  emit('delete', props.stream)
}

// Close dropdown when clicking outside
const handleClickOutside = (event: MouseEvent) => {
  if (!showActions.value) return

  const dropdown = document.querySelector('.actions-dropdown')
  const target = event.target as Node

  if (
    moreButtonRef.value &&
    !moreButtonRef.value.contains(target) &&
    dropdown &&
    !dropdown.contains(target)
  ) {
    showActions.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.stream-card {
  :deep(.glass-card-content) {
    padding: 0;
    overflow: hidden;
  }

  &.is-recording {
    :deep(.glass-card-content) {
      animation: pulse-recording 2s ease-in-out infinite;
    }
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
}

/* Compact View */
.stream-compact {
  padding: var(--spacing-4);
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  cursor: pointer;
  transition: background v.$duration-200 v.$ease-out;

  &:hover {
    background: rgba(var(--primary-500-rgb), 0.05);
  }
}

.stream-title {
  flex: 1;
  font-size: var(--text-lg);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.category-badge {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: var(--spacing-1) var(--spacing-2);
  background: rgba(var(--primary-500-rgb), 0.1);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--primary-color);
  white-space: nowrap;

  .icon {
    width: 14px;
    height: 14px;
    stroke: currentColor;
    fill: none;
  }
}

.recording-badge {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: var(--spacing-1) var(--spacing-2);
  background: var(--danger-color);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: v.$font-bold;
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  animation: pulse-recording 2s ease-in-out infinite;
}

.recording-indicator {
  width: 6px;
  height: 6px;
  background: white;
  border-radius: 50%;
  animation: pulse-live 2s ease-in-out infinite;
}

.expand-btn {
  width: 32px;
  height: 32px;
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

/* Actions Dropdown */
.stream-actions {
  position: absolute;
  top: var(--spacing-2);
  right: var(--spacing-2);
  z-index: 10;
}

.btn-action {
  width: 32px;
  height: 32px;
  padding: 0;
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 16px;
    height: 16px;
    stroke: var(--text-secondary);
    fill: none;
    transition: stroke v.$duration-200 v.$ease-out;
  }

  &:hover {
    background: var(--primary-color);
    border-color: var(--primary-color);

    .icon {
      stroke: white;
    }
  }

  &.active {
    background: var(--primary-color);
    border-color: var(--primary-color);

    .icon {
      stroke: white;
    }
  }
}

.actions-dropdown {
  position: fixed;
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-xl);
  min-width: 160px;
  padding: var(--spacing-1);
  overflow: hidden;
  z-index: 10000;
  animation: dropdown-appear 0.15s ease-out;
}

@keyframes dropdown-appear {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
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

/* Animations */
@keyframes pulse-live {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.2);
  }
}

@keyframes pulse-recording {
  0% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
  }
}

/* Mobile Responsive */
@include m.respond-below('sm') {
  .stream-compact {
    flex-wrap: wrap;
  }

  .stream-title {
    flex-basis: 100%;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
