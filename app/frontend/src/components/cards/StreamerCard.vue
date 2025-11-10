<template>
  <GlassCard
    variant="medium"
    hoverable
    clickable
    :gradient="isLive"
    :gradient-colors="isLive ? ['#ef4444', '#dc2626'] : undefined"
    @click="handleClick"
    class="streamer-card"
    :class="{ 'actions-open': showActions }"
  >
    <div class="streamer-card-content">
      <!-- Avatar/Thumbnail -->
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

        <!-- Live Badge -->
        <div v-if="isLive" class="live-badge" :class="{ 'is-recording': streamer.is_recording }">
          <span class="live-indicator"></span>
          <span class="live-text">LIVE</span>
        </div>
      </div>

      <!-- Streamer Info -->
      <div class="streamer-info">
        <!-- Streamer Name - ALWAYS visible, links to Twitch -->
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
        
        <!-- Live Stream Info -->
        <div v-if="isLive && streamer.title" class="live-info">
          <p class="stream-title" :title="streamer.title">{{ truncateText(streamer.title, 60) }}</p>
          <p v-if="streamer.category_name" class="stream-category">
            <svg class="category-icon">
              <use href="#icon-gamepad" />
            </svg>
            {{ streamer.category_name }}
          </p>
        </div>
        
        <!-- Offline Description -->
        <p v-else-if="streamer.description" class="streamer-description">
          {{ truncatedDescription }}
        </p>

        <!-- Stats -->
        <div class="streamer-stats">
          <div v-if="isLive && currentStream" class="stat stat-live">
            <svg class="stat-icon">
              <use href="#icon-users" />
            </svg>
            <span>{{ formatViewers(currentStream.viewer_count) }}</span>
          </div>

          <div v-if="streamer.recording_count" class="stat">
            <svg class="stat-icon">
              <use href="#icon-video" />
            </svg>
            <span>{{ streamer.recording_count }} VODs</span>
          </div>

          <div v-if="lastStreamTime" class="stat stat-time">
            <svg class="stat-icon">
              <use href="#icon-clock" />
            </svg>
            <span>{{ lastStreamTime }}</span>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="streamer-actions">
        <!-- Actions dropdown trigger -->
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
  forceRecord: [streamer: Streamer]
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
  if (!props.streamer.last_stream_time) return null

  const date = new Date(props.streamer.last_stream_time)
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
  emit('forceRecord', props.streamer)
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

.streamer-card {
  // Card-specific overrides
  :deep(.glass-card-content) {
    padding: var(--spacing-5);
    min-height: 240px;  /* INCREASED: Consistent card height for grid */
    max-height: 280px;  /* NEW: Prevent cards from growing too tall */
    overflow: visible;  /* CRITICAL: Allow dropdown to overflow */
    display: flex;
    flex-direction: column;
  }
  
  // When actions dropdown is open, increase z-index to appear above other cards
  &.actions-open {
    position: relative;
    z-index: 100;
  }
}

.streamer-card-content {
  display: flex;
  gap: var(--spacing-4);
  align-items: flex-start;
  flex: 1;  /* NEW: Take full height */
  min-height: 0;  /* NEW: Allow flexbox shrinking */
}

.streamer-avatar {
  position: relative;
  width: 100px;  /* Größer: war 80px */
  height: 100px;  /* Größer: war 80px */
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

.streamer-info {
  flex: 1;
  min-width: 0;  /* Allow text truncation */
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);  /* NEW: Consistent spacing */
  overflow: hidden;  /* NEW: Prevent content overflow */
}

.streamer-name-link {
  text-decoration: none;
  color: inherit;
  display: block;
  width: fit-content;
  transition: all v.$duration-200 v.$ease-out;
  margin-bottom: var(--spacing-2);
  
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

  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  
  transition: color v.$duration-200 v.$ease-out;
}

.streamer-description {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: v.$leading-snug;
  margin: 0 0 var(--spacing-3) 0;
}

.live-info {
  margin: 0;  /* REMOVED bottom margin */
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);  /* NEW: Consistent spacing */
  overflow: hidden;  /* NEW: Prevent overflow */
}

.stream-title {
  font-size: var(--text-sm);
  font-weight: v.$font-medium;
  color: var(--text-primary);
  line-height: 1.4;  /* FIXED: Consistent line-height for accurate clamping */
  margin: 0 0 var(--spacing-2) 0;
  
  /* CRITICAL: Prevent long titles from breaking layout - LIMITED TO 2 LINES */
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;  /* REDUCED from 3 to 2 for grid consistency */
  line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-word;
  max-height: 2.8em;  /* 2 lines * 1.4 line-height = 2.8em */
}

.stream-category {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin: 0;
  
  /* Prevent long category names from breaking layout */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.category-icon {
  width: 14px;
  height: 14px;
  stroke: currentColor;
  fill: none;
}

.streamer-stats {
  display: flex;
  gap: var(--spacing-4);
  flex-wrap: wrap;
  margin-top: auto;  /* NEW: Push to bottom of card */
  padding-top: var(--spacing-2);  /* NEW: Add some space above */
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

.stat-live {
  color: var(--danger-color);
  font-weight: v.$font-semibold;
}

.stat-time {
  color: var(--text-secondary);
  opacity: 0.8;
}

.streamer-actions {
  display: flex;
  gap: var(--spacing-2);
  flex-shrink: 0;
  position: relative;
  z-index: 10;  /* Ensure actions are above other content */
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
  position: fixed;  /* Fixed positioning for Teleport */
  
  background: var(--background-darker);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);  /* Slightly smaller radius */
  box-shadow: var(--shadow-xl);
  
  min-width: 160px;  /* REDUCED from 180px */
  max-width: 180px;
  padding: var(--spacing-1);  /* REDUCED from spacing-0 */
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
  padding: var(--spacing-2) var(--spacing-3);  /* REDUCED from spacing-3 spacing-4 */
  
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);  /* Add border radius */
  
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  
  font-size: var(--text-sm);  /* REDUCED from text-base */
  font-weight: v.$font-medium;
  color: var(--text-primary);
  text-align: left;
  
  cursor: pointer;
  transition: background v.$duration-150 v.$ease-out;  /* Faster transition */
  
  .icon {
    width: 16px;  /* REDUCED from 18px */
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

@media (max-width: 640px) {
  .streamer-card-content {
    flex-direction: column;
  }

  .streamer-avatar {
    width: 100%;
    height: 120px;
  }

  .streamer-actions {
    width: 100%;
    justify-content: flex-end;
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
