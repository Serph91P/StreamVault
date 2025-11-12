<template>
  <GlassCard
    variant="medium"
    hoverable
    clickable
    @click="handleClick"
    class="streamer-card"
    :class="{ 'actions-open': showActions, 'is-live': isLive, 'is-recording': streamer.is_recording }"
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

        <!-- Category (only when live) -->
        <div v-if="isLive && streamer.category_name" class="stat stat-category">
          <svg class="stat-icon">
            <use href="#icon-gamepad" />
          </svg>
          <span>{{ streamer.category_name }}</span>
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
            <button @click="handleForceRecord" class="action-item">
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
}

const props = defineProps<Props>()
const emit = defineEmits<{
  watch: [streamer: Streamer]
  'force-record': [streamer: Streamer]  // CRITICAL FIX: kebab-case for Vue event naming
  delete: [streamer: Streamer]
}>()

const router = useRouter()
const showActions = ref(false)
const moreButtonRef = ref<HTMLButtonElement | null>(null)

const isLive = computed(() => props.streamer.is_live || false)

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

const truncateText = (text: string, maxLength: number) => {
  if (!text || text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

const handleClick = () => {
  router.push(`/streamers/${props.streamer.id}`)
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
    padding: var(--spacing-5);
    min-height: 280px;
    max-height: 320px;
    overflow: visible;
    display: flex;
    flex-direction: column;
  }
  
  // LIVE indicator: REMOVED - Red border now only on avatar (line 377)
  // Keeps card cleaner and less overwhelming
  
  // RECORDING indicator: Pulsing border animation
  &.is-recording {
    :deep(.glass-card-content) {
      animation: pulse-recording 2s ease-in-out infinite;
    }
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
  width: 100px;
  height: 100px;
  flex-shrink: 0;
  border-radius: var(--radius-xl);
  overflow: hidden;
  border: 2px solid var(--border-color);
  transition: border-color v.$duration-200 v.$ease-out;

  &.is-live {
    border-color: var(--danger-color);
    box-shadow: 0 0 0 4px rgba(var(--danger-color-rgb), 0.2);
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
    width: 40px;
    height: 40px;
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
  border-radius: var(--radius-sm);

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
  line-height: 1.4;
  margin: 0;
  width: 100%;
  
  /* CRITICAL: Max 3 lines for live title (more important than description) */
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;  /* 3 lines for live streams */
  line-clamp: 3;
  -webkit-box-orient: vertical;
  word-break: break-word;
  max-height: 4.2em;  /* 3 * 1.4 line-height */
  
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
  line-height: 1.4;
  margin: 0;
  
  /* Max 2 lines for last stream title */
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-word;
  max-height: 2.8em;  /* 2 * 1.4 line-height */
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

/* Actions - TOP RIGHT CORNER (ABSOLUTE POSITIONING) */
.streamer-actions {
  position: absolute;
  top: 0;
  right: 0;
  z-index: 10;
}

.btn-action {
  width: 40px;
  height: 40px;
  padding: 0;

  background: var(--background-card);
  border: 1px solid var(--border-color);
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
    background: var(--primary-color);
    border-color: var(--primary-color);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
    
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
  
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-xl);
  
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
  }
  50% {
    box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
  }
}
</style>
