<template>
  <GlassCard
    variant="medium"
    hoverable
    clickable
    :gradient="isLive"
    :gradient-colors="isLive ? ['#ef4444', '#dc2626'] : undefined"
    @click="handleClick"
    class="streamer-card"
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
        <div v-if="isLive" class="live-badge">
          <span class="live-indicator"></span>
          <span class="live-text">LIVE</span>
        </div>
      </div>

      <!-- Streamer Info -->
      <div class="streamer-info">
        <h3 class="streamer-name">{{ streamer.display_name || streamer.username }}</h3>
        <p v-if="streamer.description" class="streamer-description">
          {{ truncatedDescription }}
        </p>

        <!-- Stats -->
        <div class="streamer-stats">
          <div v-if="isLive && currentStream" class="stat">
            <svg class="stat-icon">
              <use href="#icon-users" />
            </svg>
            <span>{{ formatViewers(currentStream.viewer_count) }}</span>
          </div>

          <div v-if="streamer.recording_count" class="stat">
            <svg class="stat-icon">
              <use href="#icon-video" />
            </svg>
            <span>{{ streamer.recording_count }}</span>
          </div>

          <div v-if="lastStreamTime" class="stat stat-time">
            <svg class="stat-icon">
              <use href="#icon-radio" />
            </svg>
            <span>{{ lastStreamTime }}</span>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="streamer-actions">
        <button
          v-if="isLive"
          @click.stop="handleWatch"
          class="btn-action btn-watch"
          aria-label="Watch stream"
        >
          <svg class="icon">
            <use href="#icon-video" />
          </svg>
        </button>

        <button
          @click.stop="handleEdit"
          class="btn-action btn-edit"
          :aria-label="`Edit ${streamer.display_name || streamer.username}`"
        >
          <svg class="icon">
            <use href="#icon-settings" />
          </svg>
        </button>
      </div>
    </div>
  </GlassCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
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
  last_stream_time?: string
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
  edit: [streamer: Streamer]
  watch: [streamer: Streamer]
}>()

const router = useRouter()

const isLive = computed(() => props.streamer.is_live || false)

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

const handleClick = () => {
  router.push(`/streamers/${props.streamer.id}`)
}

const handleEdit = () => {
  emit('edit', props.streamer)
}

const handleWatch = () => {
  emit('watch', props.streamer)
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.streamer-card {
  // Card-specific overrides
  :deep(.glass-card-content) {
    padding: var(--spacing-4);
  }
}

.streamer-card-content {
  display: flex;
  gap: var(--spacing-4);
  align-items: flex-start;
}

.streamer-avatar {
  position: relative;
  width: 80px;
  height: 80px;
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
  min-width: 0;
}

.streamer-name {
  font-size: var(--text-lg);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-1) 0;

  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.streamer-description {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: v.$leading-snug;
  margin: 0 0 var(--spacing-3) 0;
}

.streamer-stats {
  display: flex;
  gap: var(--spacing-4);
  flex-wrap: wrap;
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

.stat-time {
  color: var(--text-secondary);
  opacity: 0.8;
}

.streamer-actions {
  display: flex;
  gap: var(--spacing-2);
  flex-shrink: 0;
}

.btn-action {
  width: 40px;
  height: 40px;
  padding: 0;

  background: rgba(var(--primary-500-rgb), 0.1);
  border: 1px solid rgba(var(--primary-500-rgb), 0.3);
  border-radius: var(--radius-lg);

  display: flex;
  align-items: center;
  justify-content: center;

  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 20px;
    height: 20px;
    stroke: var(--primary-color);
    fill: none;
  }

  &:hover {
    background: rgba(var(--primary-500-rgb), 0.2);
    border-color: var(--primary-color);
    transform: translateY(-2px);
  }

  &:active {
    transform: translateY(0);
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

.btn-watch {
  background: var(--danger-color);
  border-color: var(--danger-color);

  .icon {
    stroke: white;
  }

  &:hover {
    background: var(--danger-600);
    border-color: var(--danger-600);
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
</style>
