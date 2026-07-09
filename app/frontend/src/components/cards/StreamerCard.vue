<template>
  <GlassCard
    variant="subtle"
    hoverable
    class="streamer-card"
    :class="{ 'actions-open': showActions, 'is-live': isLive, 'is-recording': streamer.is_recording, 'list-mode': viewMode === 'list' }"
  >
    <div class="streamer-card-content">
      <router-link
        class="streamer-card-body-link"
        :to="streamerRoute"
        :aria-label="`View details for ${streamer.display_name || streamer.username}`"
        @click="handleCardLinkClick"
        @contextmenu="handleContextMenu"
        @touchstart.passive="handleTouchStart"
        @touchmove.passive="handleTouchMove"
        @touchend.passive="handleTouchEnd"
        @touchcancel.passive="handleTouchEnd"
      />
      <!-- Avatar/Thumbnail - CENTERED -->
      <div class="streamer-avatar-container">
        <div class="streamer-avatar" :class="{ 'is-live': isLive }">
          <img
            v-if="(streamer.profile_image_url || streamer.avatar) && !imageError"
            :src="streamer.profile_image_url || streamer.avatar"
            :alt="streamer.display_name || streamer.username"
            loading="lazy"
            @error="imageError = true"
          />
          <div v-else class="avatar-placeholder">
            <svg class="icon-user">
              <use href="#icon-users" />
            </svg>
          </div>

        </div>
      </div>

      <!-- Streamer Name - ALWAYS VISIBLE, FULL WIDTH, MAX 2 LINES -->
      <a
        :href="`https://twitch.tv/${streamer.username}`"
        target="_blank"
        rel="noopener noreferrer"
        class="streamer-name-link"
        @click.stop
        :title="`Open ${streamer.display_name || streamer.username} on Twitch`"
      >
        <h2 class="streamer-name">
          {{ streamer.display_name || streamer.username }}
        </h2>
      </a>

      <div class="status-row" :aria-label="statusSummary">
        <StatusBadge
          v-for="badge in statusBadges"
          :key="badge.label"
          :tone="badge.tone"
          size="sm"
          :dot="badge.dot"
          :pulse="badge.pulse"
          :uppercase="false"
        >
          {{ badge.label }}
        </StatusBadge>
      </div>

      <!-- Live Stream Info OR Offline Info -->
      <div class="stream-info-container">
        <!-- LIVE: Only show title (category is in stats below) -->
        <div v-if="isLive" class="live-info">
          <p v-if="streamer.title" class="stream-title" :title="streamer.title">
            {{ streamer.title }}
          </p>
          <p v-else class="stream-title no-title">
            No stream title
          </p>
        </div>

        <!-- OFFLINE: Show last stream info if available -->
        <p v-else-if="streamer.description" class="streamer-description" :title="streamer.description">
          {{ truncatedDescription }}
        </p>

        <div v-else-if="streamer.last_stream_title" class="offline-last-stream">
          <p class="last-stream-title" :title="streamer.last_stream_title">
            {{ streamer.last_stream_title }}
          </p>
          <p v-if="streamer.last_stream_category_name" class="last-stream-category">
            {{ streamer.last_stream_category_name }}
          </p>
        </div>

        <p v-else class="streamer-description no-description">
          No description available
        </p>
      </div>

      <!-- Stats - AT BOTTOM -->
      <div class="streamer-stats">
        <!-- Viewers (only when live) -->
        <div v-if="isLive && displayViewerCount !== null" class="stat stat-viewers">
          <svg class="stat-icon">
            <use href="#icon-users" />
          </svg>
          <span>{{ formatViewers(displayViewerCount) }} viewers</span>
        </div>

        <!-- Category (live or last stream) -->
        <div v-if="displayCategory" class="stat stat-category">
          <svg class="stat-icon">
            <use href="#icon-gamepad" />
          </svg>
          <span>{{ displayCategory }}</span>
        </div>

        <!-- VOD Count (always visible if has recordings) -->
        <div v-if="recordingCount" class="stat stat-vods">
          <svg class="stat-icon">
            <use href="#icon-video" />
          </svg>
          <span>{{ recordingCount }} VODs</span>
        </div>

        <!-- Last stream time (only when offline) -->
        <div v-if="!isLive && lastStreamTime" class="stat stat-time">
          <svg class="stat-icon">
            <use href="#icon-clock" />
          </svg>
          <span>Last stream {{ lastStreamTime }}</span>
        </div>

      </div>

      <!-- Actions Dropdown - TOP RIGHT CORNER -->
      <div class="streamer-actions">
        <button
          ref="moreButtonRef"
          @click.stop="toggleActions"
          class="btn-action btn-more"
          :class="{ active: showActions }"
          :aria-label="`Actions for ${streamer.display_name || streamer.username}`"
          aria-haspopup="menu"
          :aria-expanded="showActions"
          title="More actions"
        >
          <svg class="icon">
            <use href="#icon-more-vertical" />
          </svg>
        </button>

        <!-- Actions dropdown menu - Using Teleport to avoid clipping -->
        <Teleport to="body">
          <div
            v-if="showActions"
            class="actions-dropdown"
            :style="dropdownStyle"
            @click.stop
          >
            <button v-if="isLive" @click="handleWatchInternal" class="action-item action-primary">
              <svg class="icon">
                <use href="#icon-play" />
              </svg>
              Watch Live
            </button>
            <button v-if="isLive" @click="handleWatchExternal" class="action-item">
              <svg class="icon">
                <use href="#icon-external-link" />
              </svg>
              Watch on Twitch
            </button>
            <button v-if="!streamer.is_recording" @click="handleForceRecord" class="action-item">
              <svg class="icon">
                <use href="#icon-video" />
              </svg>
              Force Record
            </button>
            <button @click="handleViewDetails" class="action-item">
              <svg class="icon">
                <use href="#icon-eye" />
              </svg>
              View Details
            </button>
            <button @click="handleDelete" class="action-item action-danger">
              <svg class="icon">
                <use href="#icon-trash" />
              </svg>
              Delete Streamer
            </button>
          </div>
        </Teleport>
      </div>
    </div>
  </GlassCard>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import StatusBadge, { type StatusBadgeTone } from '@/components/base/StatusBadge.vue'
import GlassCard from './GlassCard.vue'

interface Streamer {
  id: number
  username: string
  display_name?: string
  profile_image_url?: string
  avatar?: string
  description?: string
  recording_count?: number
  video_count?: number
  viewer_count?: number
  is_live?: boolean
  is_recording?: boolean  // NEW: Recording status
  last_stream_time?: string
  title?: string  // Stream title when live
  category_name?: string  // Game/category when live
  // Last stream info (shown when offline)
  last_stream_title?: string
  last_stream_category_name?: string
  last_stream_viewer_count?: number
  last_stream_ended_at?: string
}

interface Stream {
  viewer_count?: number
}

interface Props {
  streamer: Streamer
  currentStream?: Stream | null
  viewMode?: 'grid' | 'list'
}

const props = withDefaults(defineProps<Props>(), {
  viewMode: 'grid'
})
const emit = defineEmits<{
  watch: [streamer: Streamer]
  'force-record': [streamer: Streamer]  // CRITICAL FIX: kebab-case for Vue event naming
  delete: [streamer: Streamer]
}>()

const router = useRouter()
const showActions = ref(false)
const imageError = ref(false)
const moreButtonRef = ref<HTMLButtonElement | null>(null)

const isLive = computed(() => props.streamer.is_live || false)
const statusSummary = computed(() => {
  if (isLive.value && props.streamer.is_recording) return 'Streamer status: live and recording'
  if (isLive.value) return 'Streamer status: live'
  if (props.streamer.is_recording) return 'Streamer status: recording'
  return 'Streamer status: offline'
})
const statusBadges = computed<Array<{ label: string; tone: StatusBadgeTone; dot: boolean; pulse: boolean }>>(() => {
  const badges: Array<{ label: string; tone: StatusBadgeTone; dot: boolean; pulse: boolean }> = []
  if (isLive.value) {
    badges.push({ label: 'Live now', tone: 'live', dot: true, pulse: Boolean(props.streamer.is_recording) })
  } else {
    badges.push({ label: 'Offline', tone: 'offline', dot: false, pulse: false })
  }
  if (props.streamer.is_recording) {
    badges.push({ label: 'Recording', tone: 'recording', dot: true, pulse: true })
  }
  return badges
})
const streamerRoute = computed(() => `/streamers/${props.streamer.id}`)
const displayViewerCount = computed(() => {
  if (typeof props.currentStream?.viewer_count === 'number') return props.currentStream.viewer_count
  if (typeof props.streamer.viewer_count === 'number') return props.streamer.viewer_count
  return null
})
const recordingCount = computed(() => props.streamer.recording_count || props.streamer.video_count || 0)

// Show category from live stream or last known stream
const displayCategory = computed(() => {
  if (isLive.value && props.streamer.category_name) return props.streamer.category_name
  if (!isLive.value && props.streamer.last_stream_category_name) return props.streamer.last_stream_category_name
  return null
})

// Calculate dropdown position: at the finger for long-press, otherwise
// relative to the trigger button
const dropdownStyle = computed(() => {
  if (longPressPoint.value) {
    const menuWidth = 220
    const menuHeight = 280
    const left = Math.min(Math.max(8, longPressPoint.value.x - menuWidth / 2), window.innerWidth - menuWidth - 8)
    const top = Math.min(longPressPoint.value.y + 12, window.innerHeight - menuHeight - 8)
    return {
      position: 'fixed' as const,
      top: `${Math.max(8, top)}px`,
      left: `${left}px`,
      zIndex: 10000
    }
  }

  if (!moreButtonRef.value) {
    // Fallback positioning if button ref not available
    return {
      position: 'fixed' as const,
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      zIndex: 10000
    }
  }

  // Get button position relative to viewport
  const rect = moreButtonRef.value.getBoundingClientRect()

  // Position dropdown below and to the right of button
  return {
    position: 'fixed' as const,
    top: `${rect.bottom + 8}px`,  // 8px below button
    right: `${Math.max(8, window.innerWidth - rect.right)}px`,
    zIndex: 10000
  }
})

const truncatedDescription = computed(() => {
  const desc = props.streamer.description || ''
  return desc.length > 100 ? desc.substring(0, 100) + '...' : desc
})

const lastStreamTime = computed(() => {
  // Prefer last_stream_ended_at (new field), fallback to last_stream_time (legacy)
  const timestamp = props.streamer.last_stream_ended_at || props.streamer.last_stream_time
  if (!timestamp) return null

  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
})

const formatViewers = (count?: number) => {
  if (!count) return '0'
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`
  return count.toString()
}

watch(
  () => props.streamer.profile_image_url || props.streamer.avatar,
  () => {
    imageError.value = false
  },
)

// Once the menu closes, the next open (via the ⋮ button) anchors to the
// button again instead of the stale finger position
watch(showActions, (open) => {
  if (!open) longPressPoint.value = null
})

const _truncateText = (text: string, maxLength: number) => {
  if (!text || text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

const handleCardLinkClick = (event: MouseEvent) => {
  // A finished long-press must not also navigate to the detail page
  if (suppressNextClick.value) {
    suppressNextClick.value = false
    event.preventDefault()
    return
  }
  if (isTouchScrolling.value) {
    isTouchScrolling.value = false
    event.preventDefault()
  }
}

// Touch scroll detection to prevent accidental clicks when swiping
const isTouchScrolling = ref(false)
const touchStartY = ref(0)
const touchStartX = ref(0)
const SCROLL_THRESHOLD = 10 // pixels of movement before considering it a scroll

// Long-press opens the actions menu at the finger position - the ⋮ button is
// a small target on mobile, holding the card is the natural gesture there.
const LONG_PRESS_MS = 500
const longPressTimer = ref<number | null>(null)
const longPressPoint = ref<{ x: number; y: number } | null>(null)
const suppressNextClick = ref(false)

const cancelLongPress = () => {
  if (longPressTimer.value !== null) {
    clearTimeout(longPressTimer.value)
    longPressTimer.value = null
  }
}

// Lifting the finger after a long-press emits a synthetic click at that
// position - which would instantly hit the menu item that just appeared
// under it. Swallow exactly that one click in the capture phase.
const armClickSuppression = () => {
  const swallow = (e: MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    document.removeEventListener('click', swallow, true)
  }
  document.addEventListener('click', swallow, true)
  setTimeout(() => document.removeEventListener('click', swallow, true), 700)
}

const handleTouchStart = (e: TouchEvent) => {
  touchStartY.value = e.touches[0].clientY
  touchStartX.value = e.touches[0].clientX
  isTouchScrolling.value = false

  cancelLongPress()
  longPressTimer.value = window.setTimeout(() => {
    longPressTimer.value = null
    longPressPoint.value = { x: touchStartX.value, y: touchStartY.value }
    suppressNextClick.value = true
    armClickSuppression()
    showActions.value = true
    if ('vibrate' in navigator) navigator.vibrate(15)
  }, LONG_PRESS_MS)
}

const handleTouchMove = (e: TouchEvent) => {
  const deltaY = Math.abs(e.touches[0].clientY - touchStartY.value)
  const deltaX = Math.abs(e.touches[0].clientX - touchStartX.value)
  if (deltaY > SCROLL_THRESHOLD || deltaX > SCROLL_THRESHOLD) {
    isTouchScrolling.value = true
    cancelLongPress()
  }
}

const handleTouchEnd = () => {
  cancelLongPress()
}

// While the long-press menu is open (or just fired), swallow the native
// context menu some browsers raise for the same gesture
const handleContextMenu = (event: MouseEvent) => {
  if (showActions.value || suppressNextClick.value) {
    event.preventDefault()
  }
}

const toggleActions = () => {
  showActions.value = !showActions.value
}

const handleForceRecord = () => {
  showActions.value = false
  emit('force-record', props.streamer)  // CRITICAL FIX: Use kebab-case event name
}

const handleViewDetails = () => {
  showActions.value = false
  // Use nextTick to ensure dropdown is closed before navigation
  // This prevents the card click handler from interfering
  setTimeout(() => {
    router.push(`/streamers/${props.streamer.id}`)
  }, 50)
}

const handleDelete = () => {
  showActions.value = false
  emit('delete', props.streamer)
}

const handleWatchInternal = () => {
  showActions.value = false
  // Route to internal live player
  router.push(`/live/${props.streamer.username}`)
}

const handleWatchExternal = () => {
  // Open Twitch stream in new tab
  window.open(`https://twitch.tv/${props.streamer.username}`, '_blank', 'noopener,noreferrer')
}

// Close dropdown when clicking outside
const handleClickOutside = (event: MouseEvent) => {
  if (!showActions.value) return

  const dropdown = document.querySelector('.actions-dropdown')
  const target = event.target as Node

  if (moreButtonRef.value &&
      !moreButtonRef.value.contains(target) &&
      dropdown &&
      !dropdown.contains(target)) {
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
.streamer-card {
  overflow: visible;

  // Grid mode: fill the (row-stretched) wrapper so cards in a row are equal
  // height; clamped title/description absorb varying text lengths.
  &:not(.list-mode) {
    display: flex;
    flex-direction: column;
  }

  // Card-specific overrides
  :deep(.glass-card-content) {
    padding: var(--spacing-4);
    min-height: 240px;
    overflow: visible;
    display: flex;
    flex-direction: column;
    flex: 1;
  }

  // RECORDING indicator: pulsing ring on a pseudo-element animating only
  // opacity/transform (compositor-friendly). The previous box-shadow keyframe
  // animation forced a repaint every frame on every recording card.
  &.is-recording::after {
    content: '';
    position: absolute;
    inset: 0;
    border: 2px solid rgba(239, 68, 68, 0.7);
    border-radius: var(--radius-xl);
    pointer-events: none;
    animation: pulse-recording 2s ease-in-out infinite;
  }

  // When actions dropdown is open, increase z-index to appear above other cards
  &.actions-open {
    position: relative;
    z-index: 100;
  }
}

.streamer-card-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-2);
  flex: 1;
  min-height: 0;
  position: relative;
  cursor: pointer;
}

.streamer-card-body-link {
  position: absolute;
  inset: 0;
  z-index: 1;
  border-radius: var(--radius-xl);
  color: inherit;
  text-decoration: none;
  // Long-press opens our actions menu - suppress the native link preview /
  // text-selection callout the OS would show for the same gesture
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  user-select: none;

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 3px;
    box-shadow: var(--shadow-primary);
  }
}

/* Avatar Container - CENTERED */
.streamer-avatar-container {
  width: 100%;
  display: flex;
  justify-content: center;
  margin-bottom: var(--spacing-1);
}

.streamer-avatar {
  position: relative;
  width: 72px;
  height: 72px;
  flex-shrink: 0;
  border-radius: var(--radius-xl);
  overflow: hidden;
  border: 2px solid var(--border-color);
  transition: border-color v.$duration-200 v.$ease-out;

  &.is-live {
    border-color: var(--danger-color);
    box-shadow: 0 0 0 3px rgba(var(--danger-color-rgb), 0.2);
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  background: var(--background-darker);
  display: flex;
  align-items: center;
  justify-content: center;

  .icon-user {
    width: 32px;
    height: 32px;
    stroke: var(--text-secondary);
    fill: none;
  }
}

/* Streamer Name - FULL WIDTH, CENTERED, MAX 2 LINES */
.streamer-name-link {
  position: relative;
  z-index: 2;
  text-decoration: none;
  color: inherit;
  display: block;
  width: 100%;  /* Full width */
  text-align: center;  /* Centered */
  transition: all v.$duration-200 v.$ease-out;

  &:hover {
    color: var(--primary-color);

    .streamer-name {
      color: var(--primary-color);
    }
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }
}

.streamer-name {
  font-size: var(--text-lg);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.3;

  /* MAX 2 LINES with ellipsis */
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-word;
  max-height: 2.6em;  /* 2 * 1.3 line-height */

  transition: color v.$duration-200 v.$ease-out;
}

.status-row {
  position: relative;
  z-index: 2;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--spacing-2);
  flex-wrap: wrap;
  width: 100%;
  min-height: 28px;
}

/* Stream Info - CENTERED */
.stream-info-container {
  width: 100%;
  text-align: center;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  overflow: hidden;
  padding: var(--spacing-1) 0;
}

.streamer-description {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: v.$leading-snug;
  margin: 0;

  /* Limit to 2 lines */
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;

  &.no-description {
    font-style: italic;
    opacity: 0.6;
  }
}

.live-info {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  align-items: center;
  overflow: hidden;
  width: 100%;
}

.stream-title {
  font-size: var(--text-base);
  font-weight: v.$font-medium;
  color: var(--text-primary);
  line-height: 1.5;
  margin: 0;
  width: 100%;

  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  word-break: break-word;
  padding-bottom: 0.15em;

  &.no-title {
    font-style: italic;
    opacity: 0.6;
    font-size: var(--text-sm);
  }
}

/* Offline Last Stream Info - Grayed out to indicate past stream */
.offline-last-stream {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
  width: 100%;
  opacity: 0.6;  /* Grayed out to show it's not current */
}

.last-stream-title {
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  color: var(--text-secondary);
  line-height: 1.5;  /* FIX: bumped to give descenders (g, j, p, y) room */
  margin: 0;

  /* Max 2 lines for last stream title */
  /* FIX: descender-safe clamp (see .stream-title comment) */
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-word;
  padding-bottom: 0.2em;  /* descender safe-area */
  max-height: calc(1.5em * 2 + 0.2em);  /* 2 lines * line-height + descender pad */
}

.last-stream-category {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Stats - AT BOTTOM, CENTERED */
.streamer-stats {
  display: flex;
  gap: var(--spacing-2);
  justify-content: center;
  align-items: center;
  flex-wrap: wrap;
  margin-top: auto;
  padding-top: var(--spacing-2);
  width: 100%;
}

.stat {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  font-size: var(--text-sm);
  color: var(--text-secondary);

  .stat-icon {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
  }
}

/* LIVE stats - More prominent */
.stat-viewers {
  color: var(--danger-color);
  font-weight: v.$font-semibold;
}

.stat-category {
  color: var(--text-primary);
  font-weight: v.$font-medium;

  /* Truncate long category names */
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stat-vods {
  color: var(--primary-color);
}

.stat-time {
  color: var(--text-secondary);
  opacity: 0.8;
}

.stat-live {
  color: var(--danger-color);
  font-weight: v.$font-semibold;
}

.stat-recording {
  color: var(--danger-text-color);
  font-size: var(--text-xs);
  font-weight: v.$font-semibold;
}

/* Actions - TOP RIGHT CORNER (ABSOLUTE POSITIONING) */
.streamer-actions {
  position: absolute;
  top: var(--spacing-2);
  right: var(--spacing-2);
  z-index: 2;
}

.btn-action {
  width: 44px;
  height: 44px;
  padding: 0;

  background: transparent;
  border: none;
  border-radius: var(--radius-lg);

  display: flex;
  align-items: center;
  justify-content: center;

  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 20px;
    height: 20px;
    stroke: var(--text-secondary);
    fill: none;
    transition: stroke v.$duration-200 v.$ease-out;
  }

  &:hover {
    background: rgba(var(--primary-500-rgb), 0.1);

    .icon {
      stroke: var(--text-primary);
    }
  }

  &.active {
    background: rgba(var(--primary-500-rgb), 0.15);

    .icon {
      stroke: var(--primary-color);
    }
  }

  &:active {
    transform: translateY(0);
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

.actions-dropdown {
  position: fixed;

  // Solid background - a backdrop-filter on top of it had no visible effect.
  background: var(--glass-bg-solid);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  box-shadow: var(--glass-shadow-lg);

  min-width: 160px;
  max-width: 180px;
  padding: var(--spacing-1);
  overflow: hidden;
  z-index: 10000;

  /* Smooth appearance */
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
  min-height: 44px;
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

@include m.respond-below('sm') {  // < 640px
  .streamer-card {
    :deep(.glass-card-content) {
      min-height: 260px;
      max-height: 300px;
    }
  }

  .streamer-avatar {
    width: 80px;
    height: 80px;
  }
}

// ============================================================================
// LIST MODE STYLES
// Horizontal layout matching VideoCard list mode pattern
// ============================================================================

.streamer-card.list-mode {
  max-width: none;
  min-height: 0;

  :deep(.glass-card-content) {
    display: flex;
    flex-direction: row;
    align-items: center;
    min-height: auto;
    padding: 0;
    gap: 0;
  }

  .streamer-card-content {
    display: grid;
    grid-template-columns: auto 1fr auto auto;
    grid-template-rows: auto auto;
    align-items: center;
    gap: var(--spacing-1) var(--spacing-4);
    width: 100%;
    min-height: 80px;
    // Right padding must clear the absolutely-positioned ⋮ button:
    // 8px offset + 44px button + 12px breathing room
    padding: var(--spacing-3) 64px var(--spacing-3) var(--spacing-3);
  }

  .streamer-avatar-container {
    grid-row: 1 / 3;
    grid-column: 1;
    margin-bottom: 0;
    width: auto;
    padding: 0;
  }

  .streamer-avatar {
    width: 48px;
    height: 48px;
  }

  .streamer-name-link {
    grid-row: 1;
    grid-column: 2;
    align-self: end;
    text-align: left;
    width: auto;
    padding: 0;

    .streamer-name {
      font-size: var(--text-sm);
      font-weight: v.$font-semibold;
      -webkit-line-clamp: 1;
      line-clamp: 1;
      max-height: 1.3em;
    }
  }

  .status-row {
    grid-row: 2;
    grid-column: 2;
    align-self: start;
    justify-content: flex-start;
    min-height: 22px;
    align-content: flex-start;
  }

  .stream-info-container {
    grid-row: 1 / 3;
    grid-column: 3;
    justify-content: center;
    text-align: left;
    min-width: 0;
    padding: 0;
    max-width: 320px;

    .stream-title,
    .last-stream-title,
    .streamer-description,
    .last-stream-category {
      -webkit-line-clamp: 2;
      line-clamp: 2;
      font-size: var(--text-xs);
      text-align: left;
    }

    .no-description,
    .no-title {
      font-size: var(--text-xs);
    }
  }

  .streamer-stats {
    grid-row: 1 / 3;
    grid-column: 4;
    display: flex;
    flex-direction: column;
    flex-wrap: nowrap;
    gap: var(--spacing-1);
    margin-top: 0;
    padding: 0;
    align-items: flex-end;
    justify-content: center;
    width: auto;

    .stat {
      font-size: var(--text-xs);
      white-space: nowrap;
      color: var(--text-secondary);
    }

    .stat-icon {
      width: 12px;
      height: 12px;
    }
  }

  .streamer-actions {
    position: absolute;
    top: 50%;
    right: var(--spacing-2);
    transform: translateY(-50%);
    padding-right: 0;
    align-self: center;
  }
}

// Mobile: the 4-column desktop row squeezes name and title into unreadable
// slivers - stack instead: avatar + name/badges, then title, then a meta row.
@include m.respond-below('md') {
  .streamer-card.list-mode {
    .streamer-card-content {
      grid-template-columns: auto minmax(0, 1fr);
      grid-template-rows: auto;
      gap: var(--spacing-1) var(--spacing-3);
      padding: var(--spacing-3);
      // Room for the ⋮ button in the top-right corner (8px offset + 44px
      // button + breathing room), so long names never slide under it
      padding-right: 60px;
    }

    .streamer-avatar-container {
      grid-row: 1 / 3;
      grid-column: 1;
    }

    .streamer-name-link {
      grid-row: 1;
      grid-column: 2;
    }

    .status-row {
      grid-row: 2;
      grid-column: 2;
    }

    .stream-info-container {
      grid-row: 3;
      grid-column: 1 / -1;
      max-width: none;
      padding-top: var(--spacing-1);
    }

    .streamer-stats {
      grid-row: 4;
      grid-column: 1 / -1;
      flex-direction: row;
      flex-wrap: wrap;
      align-items: center;
      justify-content: flex-start;
      gap: var(--spacing-1) var(--spacing-3);
    }

    // Corner position instead of vertically centered - centered, the button
    // sat on top of the meta text
    .streamer-actions {
      top: var(--spacing-2);
      right: var(--spacing-2);
      transform: none;
    }
  }
}

@include m.respond-below('sm') {
  .streamer-card.list-mode {
    .streamer-avatar {
      width: 44px;
      height: 44px;
    }
  }
}

// Animations
@keyframes pulse-live {
  0%, 100% {
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
    opacity: 0.9;
    transform: scale(1);
  }
  50% {
    opacity: 0;
    transform: scale(1.025);
  }
  100% {
    opacity: 0;
    transform: scale(1);
  }
}
</style>
