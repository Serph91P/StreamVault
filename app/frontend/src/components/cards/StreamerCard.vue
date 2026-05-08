<template>
  <GlassCard
    variant="subtle"
    hoverable
    clickable
    @click="handleClick"
    @touchstart.passive="handleTouchStart"
    @touchmove.passive="handleTouchMove"
    class="streamer-card"
    :class="{ 'actions-open': showActions, 'is-live': isLive, 'is-recording': streamer.is_recording, 'list-mode': viewMode === 'list' }"
  >
    <div class="streamer-card-content">
      <!-- Avatar/Thumbnail - CENTERED -->
      <div class="streamer-avatar-container">
        <div class="streamer-avatar" :class="{ 'is-live': isLive }">
          <img
            v-if="streamer.profile_image_url || streamer.avatar"
            :src="streamer.profile_image_url || streamer.avatar"
            :alt="streamer.display_name || streamer.username"
            loading="lazy"
          />
          <div v-else class="avatar-placeholder">
            <svg class="icon-user">
              <use href="#icon-users" />
            </svg>
          </div>

          <!-- Live Badge ON Avatar -->
          <div v-if="isLive" class="live-badge" :class="{ 'is-recording': streamer.is_recording }">
            <span class="live-indicator"></span>
            <span class="live-text">LIVE</span>
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
        <h3 class="streamer-name">
          {{ streamer.display_name || streamer.username }}
        </h3>
      </a>
      
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
        <div v-else-if="streamer.last_stream_title" class="offline-last-stream">
          <p class="last-stream-title" :title="streamer.last_stream_title">
            {{ streamer.last_stream_title }}
          </p>
          <p v-if="streamer.last_stream_category_name" class="last-stream-category">
            {{ streamer.last_stream_category_name }}
          </p>
        </div>
        
        <!-- OFFLINE: Fallback to description if no last stream info -->
        <p v-else-if="streamer.description" class="streamer-description">
          {{ truncatedDescription }}
        </p>
        <p v-else class="streamer-description no-description">
          No description available
        </p>
      </div>

      <!-- Stats - AT BOTTOM -->
      <div class="streamer-stats">
        <!-- Viewers (only when live) -->
        <div v-if="isLive && currentStream" class="stat stat-viewers">
          <svg class="stat-icon">
            <use href="#icon-users" />
          </svg>
          <span>{{ formatViewers(currentStream.viewer_count) }}</span>
        </div>

        <!-- Category (live or last stream) -->
        <div v-if="displayCategory" class="stat stat-category">
          <svg class="stat-icon">
            <use href="#icon-gamepad" />
          </svg>
          <span>{{ displayCategory }}</span>
        </div>

        <!-- VOD Count (always visible if has recordings) -->
        <div v-if="streamer.recording_count" class="stat stat-vods">
          <svg class="stat-icon">
            <use href="#icon-video" />
          </svg>
          <span>{{ streamer.recording_count }} VODs</span>
        </div>

        <!-- Last stream time (only when offline) -->
        <div v-if="!isLive && lastStreamTime" class="stat stat-time">
          <svg class="stat-icon">
            <use href="#icon-clock" />
          </svg>
          <span>{{ lastStreamTime }}</span>
        </div>

        <!-- Recording indicator -->
        <div v-if="streamer.is_recording" class="stat stat-recording">
          <span class="recording-dot"></span>
          <span>REC</span>
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
            <button v-if="isLive" @click="handleWatch" class="action-item">
              <svg class="icon">
                <use href="#icon-play" />
              </svg>
              Watch Live
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
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import GlassCard from './GlassCard.vue'

interface Streamer {
  id: number
  username: string
  display_name?: string
  profile_image_url?: string
  avatar?: string
  description?: string
  recording_count?: number
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
const moreButtonRef = ref<HTMLButtonElement | null>(null)

const isLive = computed(() => props.streamer.is_live || false)

// Show category from live stream or last known stream
const displayCategory = computed(() => {
  if (isLive.value && props.streamer.category_name) return props.streamer.category_name
  if (!isLive.value && props.streamer.last_stream_category_name) return props.streamer.last_stream_category_name
  return null
})

// Calculate dropdown position relative to trigger button
const dropdownStyle = computed(() => {
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
    left: `${rect.left - 140}px`,  // Align to right edge (180px width - 40px button)
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

const _truncateText = (text: string, maxLength: number) => {
  if (!text || text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

const handleClick = () => {
  // Prevent navigation if user was scrolling (touch devices)
  if (isTouchScrolling.value) {
    isTouchScrolling.value = false
    return
  }
  router.push(`/streamers/${props.streamer.id}`)
}

// Touch scroll detection to prevent accidental clicks when swiping
const isTouchScrolling = ref(false)
const touchStartY = ref(0)
const touchStartX = ref(0)
const SCROLL_THRESHOLD = 10 // pixels of movement before considering it a scroll

const handleTouchStart = (e: TouchEvent) => {
  touchStartY.value = e.touches[0].clientY
  touchStartX.value = e.touches[0].clientX
  isTouchScrolling.value = false
}

const handleTouchMove = (e: TouchEvent) => {
  const deltaY = Math.abs(e.touches[0].clientY - touchStartY.value)
  const deltaX = Math.abs(e.touches[0].clientX - touchStartX.value)
  if (deltaY > SCROLL_THRESHOLD || deltaX > SCROLL_THRESHOLD) {
    isTouchScrolling.value = true
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

const handleWatch = () => {
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
  // Card-specific overrides
  :deep(.glass-card-content) {
    padding: var(--spacing-4);
    min-height: 220px;
    max-height: 300px;  /* FIX: bumped from 260 so 3-line titles fit without clipping */
    overflow: visible;
    display: flex;
    flex-direction: column;
  }
  
  // LIVE indicator: REMOVED - Red border now only on avatar (line 377)
  // Keeps card cleaner and less overwhelming
  
  // RECORDING indicator: Pulsing border animation on the card itself
  &.is-recording {
    animation: pulse-recording 2s ease-in-out infinite;
    border-radius: var(--radius-xl);  /* Ensure rounded during animation */
  }
  
  // When actions dropdown is open, increase z-index to appear above other cards
  &.actions-open {
    position: relative;
    z-index: 100;
  }
}

.streamer-card-content {
  /* VERTICAL LAYOUT: Stack everything vertically */
  display: flex;
  flex-direction: column;
  align-items: center;  /* Center horizontally */
  gap: var(--spacing-3);
  flex: 1;
  min-height: 0;
  position: relative;  /* For absolute positioning of actions button */
}

/* Avatar Container - CENTERED */
.streamer-avatar-container {
  width: 100%;
  display: flex;
  justify-content: center;
  margin-bottom: var(--spacing-2);
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

.live-badge {
  position: absolute;
  bottom: 4px;
  left: 4px;
  right: 4px;

  background: var(--danger-color);
  color: white;

  padding: 2px 8px;
  border-radius: var(--radius-full);  /* More rounded pill shape */

  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;

  font-size: var(--text-xs);
  font-weight: v.$font-bold;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  
  /* Pulsing effect when recording */
  &.is-recording {
    animation: pulse-recording 2s ease-in-out infinite;
    border-radius: var(--radius-full);  /* Pill shape for recording indicator */
  }
}

.live-indicator {
  width: 6px;
  height: 6px;
  background: white;
  border-radius: 50%;
  animation: pulse-live 2s ease-in-out infinite;
}

/* Streamer Name - FULL WIDTH, CENTERED, MAX 2 LINES */
.streamer-name-link {
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

/* Stream Info - CENTERED */
.stream-info-container {
  width: 100%;
  text-align: center;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  overflow: hidden;
  padding: var(--spacing-2) 0;  /* Add vertical spacing */
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
  font-size: var(--text-base);  /* INCREASED: Better readability */
  font-weight: v.$font-medium;
  color: var(--text-primary);
  line-height: 1.5;  /* FIX: bumped from 1.4 to give descenders (g, j, p, y) room */
  margin: 0;
  width: 100%;

  /* CRITICAL: Max 3 lines for live title (more important than description) */
  /* FIX: -webkit-line-clamp + overflow:hidden clips descenders on the last line.
     Use padding-bottom + matching max-height so descenders are not cut off, and
     keep ellipsis behaviour. */
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;  /* 3 lines for live streams */
  line-clamp: 3;
  -webkit-box-orient: vertical;
  word-break: break-word;
  padding-bottom: 0.2em;  /* descender safe-area */
  max-height: calc(1.5em * 3 + 0.2em);  /* 3 lines * line-height + descender pad */

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
  gap: var(--spacing-3);  /* REDUCED: Smaller gap for better fit */
  justify-content: center;
  align-items: center;
  flex-wrap: wrap;
  margin-top: auto;
  padding-top: var(--spacing-3);
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

/* Actions - TOP RIGHT CORNER (ABSOLUTE POSITIONING) */.stat {
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

.stat-live {
  color: var(--danger-color);
  font-weight: v.$font-semibold;
}

.stat-time {
  color: var(--text-secondary);
  opacity: 0.8;
}

.stat-recording {
  color: var(--danger-color);
  font-weight: v.$font-semibold;
  font-size: var(--text-xs);
  
  .recording-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--danger-color);
    animation: pulse-live 1.5s ease-in-out infinite;
  }
}

/* Actions - TOP RIGHT CORNER (ABSOLUTE POSITIONING) */
.streamer-actions {
  position: absolute;
  top: var(--spacing-2);
  right: var(--spacing-2);
  z-index: 10;
}

.btn-action {
  width: 36px;
  height: 36px;
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
  
  background: var(--glass-bg-solid);
  backdrop-filter: blur(var(--glass-blur-md));
  -webkit-backdrop-filter: blur(var(--glass-blur-md));
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
  :deep(.glass-card-content) {
    display: flex;
    flex-direction: row;
    align-items: center;
    min-height: auto;
    max-height: none;
    padding: 0;
    gap: 0;
  }

  .streamer-card-content {
    display: grid;
    grid-template-columns: auto 1fr auto auto;
    grid-template-rows: auto auto auto;
    align-items: center;
    gap: 0;
    width: 100%;
  }

  .streamer-avatar-container {
    grid-row: 1 / 4;
    grid-column: 1;
    margin-bottom: 0;
    width: auto;
    padding: var(--spacing-3);
  }

  .streamer-avatar {
    width: 56px;
    height: 56px;
  }

  .live-badge {
    font-size: 8px;
    padding: 1px 4px;
    gap: 2px;
    
    .live-indicator {
      width: 4px;
      height: 4px;
    }
  }

  .streamer-name-link {
    grid-row: 1;
    grid-column: 2 / -1;
    text-align: left;
    width: auto;
    padding-top: var(--spacing-2);
    padding-right: var(--spacing-3);
    
    .streamer-name {
      font-size: var(--text-sm);
      font-weight: v.$font-semibold;
      -webkit-line-clamp: 1;
      line-clamp: 1;
      max-height: 1.3em;
    }
  }

  .stream-info-container {
    grid-row: 2;
    grid-column: 2 / -1;
    text-align: left;
    min-width: 0;
    padding: 0 var(--spacing-3) 0 0;

    .stream-title,
    .last-stream-title,
    .streamer-description,
    .last-stream-category {
      -webkit-line-clamp: 1;
      line-clamp: 1;
      font-size: var(--text-xs);
      text-align: left;
    }
    
    .no-description,
    .no-title {
      font-size: var(--text-xs);
    }
  }

  .streamer-stats {
    grid-row: 3;
    grid-column: 2;
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: var(--spacing-2) var(--spacing-3);
    padding: 0 0 var(--spacing-2) 0;
    align-items: center;
    
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
    grid-row: 3;
    grid-column: 4;
    position: relative;
    top: auto;
    right: auto;
    padding-right: var(--spacing-3);
    align-self: center;
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
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
    border-radius: var(--radius-xl);  /* Rounded during animation */
  }
  50% {
    box-shadow: 0 0 0 8px rgba(239, 68, 68, 0);
    border-radius: var(--radius-xl);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
    border-radius: var(--radius-xl);
  }
}
</style>
