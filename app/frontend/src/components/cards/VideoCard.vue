<template>
  <GlassCard
    variant="medium"
    hoverable
    clickable
    :padding="false"
    @click="handleClick"
    class="video-card"
  >
    <!-- Thumbnail -->
    <div class="video-thumbnail">
      <img
        v-if="video.thumbnail_url"
        :src="video.thumbnail_url"
        :alt="video.title"
        loading="lazy"
      />
      <div v-else class="thumbnail-placeholder">
        <svg class="icon-video">
          <use href="#icon-video" />
        </svg>
      </div>

      <!-- Duration Badge -->
      <div v-if="video.duration" class="duration-badge">
        {{ formattedDuration }}
      </div>

      <!-- Status Badge -->
      <div v-if="statusBadge" class="status-badge" :class="`status-${statusBadge.type}`">
        {{ statusBadge.text }}
      </div>

      <!-- Hover Overlay -->
      <div class="hover-overlay">
        <button class="play-button" @click.stop="handlePlay" aria-label="Play video">
          <svg class="icon-play">
            <use href="#icon-video" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Video Info -->
    <div class="video-info">
      <h3 class="video-title">{{ video.title }}</h3>

      <div class="video-meta">
        <span class="streamer-name">{{ video.streamer_name || 'Unknown' }}</span>
        <span class="separator">•</span>
        <span class="upload-date">{{ formattedDate }}</span>
      </div>

      <div v-if="video.view_count || video.file_size" class="video-stats">
        <span v-if="video.view_count" class="stat">
          <svg class="stat-icon">
            <use href="#icon-users" />
          </svg>
          {{ formatNumber(video.view_count) }}
        </span>
        <span v-if="video.file_size" class="stat">
          {{ formatFileSize(video.file_size) }}
        </span>
      </div>
    </div>
  </GlassCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import GlassCard from './GlassCard.vue'

interface Video {
  id: number
  title: string
  thumbnail_url?: string
  duration?: number
  file_size?: number
  view_count?: number
  created_at?: string
  streamer_name?: string
  status?: 'recording' | 'processing' | 'ready' | 'failed'
}

interface Props {
  video: Video
}

const props = defineProps<Props>()
const emit = defineEmits<{
  play: [video: Video]
}>()

const router = useRouter()

const formattedDuration = computed(() => {
  if (!props.video.duration) return ''

  const hours = Math.floor(props.video.duration / 3600)
  const minutes = Math.floor((props.video.duration % 3600) / 60)
  const seconds = Math.floor(props.video.duration % 60)

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
  }
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
})

const formattedDate = computed(() => {
  if (!props.video.created_at) return ''

  const date = new Date(props.video.created_at)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`
  return `${Math.floor(diffDays / 365)} years ago`
})

const statusBadge = computed(() => {
  if (!props.video.status) return null

  const badges = {
    recording: { text: 'RECORDING', type: 'recording' },
    processing: { text: 'PROCESSING', type: 'processing' },
    failed: { text: 'FAILED', type: 'failed' },
    ready: null
  }

  return badges[props.video.status] || null
})

const formatNumber = (num: number) => {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toString()
}

const formatFileSize = (bytes: number) => {
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(0)} KB`
}

const handleClick = () => {
  router.push(`/videos/${props.video.id}`)
}

const handlePlay = () => {
  emit('play', props.video)
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;
.video-card {
  overflow: hidden;

  &:hover {
    .hover-overlay {
      opacity: 1;
    }

    .video-title {
      color: var(--primary-color);
    }
  }
}

.video-thumbnail {
  position: relative;
  width: 100%;
  padding-top: 56.25%; // 16:9 aspect ratio
  background: var(--background-darker);
  overflow: hidden;

  img {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.thumbnail-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--background-darker);

  .icon-video {
    width: 48px;
    height: 48px;
    stroke: var(--text-secondary);
    fill: none;
    opacity: 0.5;
  }
}

.duration-badge {
  position: absolute;
  bottom: 8px;
  right: 8px;

  background: rgba(0, 0, 0, 0.9);
  color: white;

  padding: 2px 6px;
  border-radius: var(--radius-sm);

  font-size: var(--text-xs);
  font-weight: v.$font-semibold;
  font-family: v.$font-mono;
}

.status-badge {
  position: absolute;
  top: 8px;
  left: 8px;

  padding: 4px 8px;
  border-radius: var(--radius-sm);

  font-size: var(--text-xs);
  font-weight: v.$font-bold;
  text-transform: uppercase;
  letter-spacing: 0.05em;

  &.status-recording {
    background: var(--primary-color);
    color: white;
  }

  &.status-processing {
    background: var(--warning-color);
    color: white;
  }

  &.status-failed {
    background: var(--danger-color);
    color: white;
  }
}

.hover-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;

  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);

  display: flex;
  align-items: center;
  justify-content: center;

  opacity: 0;
  transition: opacity v.$duration-200 v.$ease-out;
}

.play-button {
  width: 64px;
  height: 64px;
  padding: 0;

  background: var(--primary-color);
  border: 3px solid white;
  border-radius: 50%;

  display: flex;
  align-items: center;
  justify-content: center;

  cursor: pointer;
  transform: scale(0.9);
  transition: all v.$duration-200 v.$ease-out;

  .icon-play {
    width: 32px;
    height: 32px;
    stroke: white;
    fill: none;
    margin-left: 4px; // Visual centering
  }

  &:hover {
    transform: scale(1);
    box-shadow: 0 8px 24px rgba(var(--primary-500-rgb), 0.5);
  }

  &:active {
    transform: scale(0.95);
  }
}

.video-info {
  padding: var(--spacing-4);
}

.video-title {
  font-size: var(--text-base);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  line-height: v.$leading-snug;
  margin: 0 0 var(--spacing-2) 0;

  // Limit to 2 lines
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;

  transition: color v.$duration-200 v.$ease-out;
}

.video-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);

  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-2);
}

.streamer-name {
  font-weight: v.$font-medium;
}

.separator {
  opacity: 0.5;
}

.video-stats {
  display: flex;
  gap: var(--spacing-3);

  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.stat {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);

  .stat-icon {
    width: 14px;
    height: 14px;
    stroke: currentColor;
    fill: none;
  }
}

/* Mobile Optimizations - Use SCSS mixins for breakpoints */

@include m.respond-below('md') {  // < 768px
  .video-info {
    padding: var(--spacing-3);
  }

  .video-title {
    font-size: var(--text-base);
    // Keep 2-line clamp for consistency
  }

  .video-meta,
  .video-stats {
    font-size: var(--text-xs);
  }

  .play-button {
    width: 72px;  // Larger for touch
    height: 72px;

    .icon-play {
      width: 36px;
      height: 36px;
    }
  }

  .duration-badge {
    bottom: 10px;
    right: 10px;
    padding: 4px 8px;
    font-size: var(--text-xs);
  }

  .status-badge {
    top: 10px;
    left: 10px;
    padding: 6px 10px;
    font-size: var(--text-xs);
  }
}

/* Extra Small Screens */
@include m.respond-below('xs') {  // < 375px
  .video-info {
    padding: var(--spacing-2);
  }

  .video-title {
    font-size: var(--text-sm);
    margin-bottom: var(--spacing-1);
  }

  .video-meta {
    margin-bottom: var(--spacing-1);
    gap: var(--spacing-1);
  }

  .video-stats {
    gap: var(--spacing-2);
  }

  .play-button {
    width: 56px;  // Slightly smaller for very small screens
    height: 56px;

    .icon-play {
      width: 28px;
      height: 28px;
    }
  }
}
</style>
