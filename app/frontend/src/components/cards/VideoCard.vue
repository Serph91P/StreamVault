<template>
  <GlassCard
    variant="subtle"
    hoverable
    :padding="false"
    class="video-card"
    :class="{ 'list-mode': viewMode === 'list' }"
  >
    <div class="video-card-action">
      <router-link
        v-if="isInteractiveLink"
        class="video-card-link"
        :to="videoRoute"
        :aria-label="watchLabel"
      />
      <button
        v-else-if="disableNavigation"
        type="button"
        class="video-card-link"
        :aria-label="selectLabel"
        @click="handleSelect"
      />
      <span
        v-else
        class="video-card-link video-card-link-disabled"
        role="img"
        :aria-label="unavailableLabel"
      />
      <!-- Thumbnail -->
      <div class="video-thumbnail">
        <img
          v-if="hasThumbnail"
          :src="video.thumbnail_url"
          :alt="thumbnailAlt"
          loading="lazy"
          @error="handleThumbnailError"
        />
        <div v-else class="thumbnail-placeholder">
          <div class="placeholder-body">
            <svg class="icon-video">
              <use href="#icon-video" />
            </svg>
            <span class="placeholder-label">{{ thumbnailFallbackLabel }}</span>
            <span class="placeholder-cue">{{ thumbnailFallbackCue }}</span>
          </div>
        </div>

        <!-- Duration Badge -->
        <div v-if="formattedDuration" class="duration-badge">
          {{ formattedDuration }}
        </div>

        <!-- Status Badge -->
        <StatusBadge
          v-if="statusBadge"
          class="video-status-badge"
          :tone="statusBadge.tone"
          size="sm"
          :dot="statusBadge.dot"
          :pulse="statusBadge.pulse"
          :aria-label="`Video status: ${statusBadge.text}`"
        >
          {{ statusBadge.text }}
        </StatusBadge>

        <!-- Hover Overlay (grid mode only; hidden in select mode so the
             selection ring and checkmark stay readable) -->
        <div v-if="viewMode !== 'list' && !disableNavigation" class="hover-overlay" :class="{ 'is-disabled': !canPlay }">
          <button class="play-button" :disabled="!canPlay" @click.stop="handlePlay" :aria-label="playButtonLabel">
            <svg class="icon-play">
              <use href="#icon-video" />
            </svg>
            <span v-if="!canPlay" class="play-button-label">Unavailable</span>
          </button>
        </div>
      </div>

      <!-- Video Info -->
      <div class="video-info">
        <h2 class="video-title">{{ displayTitle }}</h2>

        <div class="video-meta">
          <span class="streamer-name">{{ streamerLabel }}</span>
          <span class="separator">•</span>
          <span class="upload-date">{{ formattedDate }}</span>
        </div>

        <div v-if="video.category_name" class="video-category">{{ video.category_name }}</div>
        <p v-if="mediaStateMessage" class="video-state-message">{{ mediaStateMessage }}</p>

        <div v-if="displayViewCount || displayFileSize" class="video-stats">
          <span v-if="displayViewCount" class="stat">
            <svg class="stat-icon">
              <use href="#icon-users" />
            </svg>
            {{ formatNumber(displayViewCount) }}
          </span>
          <span v-if="displayFileSize" class="stat">
            {{ displayFileSize }}
          </span>
        </div>
      </div>
    </div>
  </GlassCard>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import StatusBadge, { type StatusBadgeTone } from '@/components/base/StatusBadge.vue'
import GlassCard from './GlassCard.vue'

type VideoStatus = 'recording' | 'processing' | 'ready' | 'failed'

interface Video {
  id: number
  title?: string | null
  thumbnail_url?: string
  duration?: number
  file_size?: number
  view_count?: number
  viewer_count?: number
  created_at?: string
  recorded_at?: string
  stream_date?: string
  streamer_name?: string
  streamer_id?: number  // Required for navigation to video player
  category_name?: string
  file_path?: string
  status?: VideoStatus | string
  is_recording?: boolean
}

interface Props {
  video: Video
  viewMode?: 'grid' | 'list'
  disableNavigation?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  viewMode: 'grid',
  disableNavigation: false
})
const emit = defineEmits<{
  play: [video: Video]
  select: [video: Video]
}>()

// Thumbnail error handling
const thumbnailError = ref(false)

const handleThumbnailError = () => {
  thumbnailError.value = true
}

watch(() => props.video.thumbnail_url, () => {
  thumbnailError.value = false
})

const hasValidId = computed(() => Number.isFinite(props.video.id))
const hasStreamerId = computed(() => Number.isFinite(props.video.streamer_id))
const normalizedStatus = computed(() => {
  if (props.video.is_recording) return 'recording'
  return typeof props.video.status === 'string' ? props.video.status.toLowerCase() : ''
})
const isFailed = computed(() => normalizedStatus.value === 'failed')
const canPlay = computed(() => hasValidId.value && hasStreamerId.value && !isFailed.value)
const isInteractiveLink = computed(() => !props.disableNavigation && canPlay.value)
const displayTitle = computed(() => {
  const title = props.video.title?.trim()
  return title || `Untitled video ${hasValidId.value ? props.video.id : ''}`.trim()
})
const streamerLabel = computed(() => props.video.streamer_name?.trim() || 'Unknown streamer')
const watchLabel = computed(() => `Watch ${displayTitle.value}`)
const selectLabel = computed(() => `Select ${displayTitle.value}`)
const unavailableLabel = computed(() => `${displayTitle.value} is unavailable to play`)
const playButtonLabel = computed(() => canPlay.value ? `Play ${displayTitle.value}` : unavailableLabel.value)
const thumbnailAlt = computed(() => `${displayTitle.value} preview`)
const hasThumbnail = computed(() => Boolean(props.video.thumbnail_url && !thumbnailError.value))
const thumbnailFallbackLabel = computed(() => {
  if (isFailed.value) return 'Media unavailable'
  if (thumbnailError.value) return 'Preview failed to load'
  return 'Preview unavailable'
})
const thumbnailFallbackCue = computed(() => props.video.category_name?.trim() || streamerLabel.value)
const mediaStateMessage = computed(() => {
  if (isFailed.value) return 'Recording failed or media is unavailable.'
  if (!hasStreamerId.value || !hasValidId.value) return 'Playback details are missing.'
  if (!props.video.recorded_at && !props.video.created_at && !props.video.stream_date) return 'Recording date unavailable.'
  return ''
})

const formattedDuration = computed(() => {
  if (!props.video.duration || props.video.duration <= 0) return ''

  const hours = Math.floor(props.video.duration / 3600)
  const minutes = Math.floor((props.video.duration % 3600) / 60)
  const seconds = Math.floor(props.video.duration % 60)

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
  }
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
})

const displayViewCount = computed(() => {
  const count = props.video.view_count ?? props.video.viewer_count ?? 0
  return count > 0 ? count : 0
})

const displayFileSize = computed(() => {
  if (!props.video.file_size || props.video.file_size <= 0) return ''
  return formatFileSize(props.video.file_size)
})

const formattedDate = computed(() => {
  const dateStr = props.video.recorded_at || props.video.created_at || props.video.stream_date
  if (!dateStr) return 'Date unavailable'

  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) return 'Date unavailable'
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
  // Treat backend `is_recording=true` (Strategy 3 in /api/videos) as a live
  // recording, even if the persisted `status` is missing or still 'ready'.
  const effectiveStatus = normalizedStatus.value
  if (!effectiveStatus) return null

  const badges: Record<Exclude<VideoStatus, 'ready'>, {
    text: string
    tone: StatusBadgeTone
    dot: boolean
    pulse: boolean
  }> = {
    recording: { text: 'RECORDING', tone: 'recording', dot: true, pulse: true },
    processing: { text: 'PROCESSING', tone: 'processing', dot: true, pulse: false },
    failed: { text: 'FAILED', tone: 'danger', dot: false, pulse: false }
  }

  if (effectiveStatus === 'ready') return null
  return badges[effectiveStatus as Exclude<VideoStatus, 'ready'>] || null
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

const videoRoute = computed(() => ({
  name: 'VideoPlayer',
  params: {
    streamerId: props.video.streamer_id,
    streamId: props.video.id
  },
  query: {
    title: displayTitle.value,
    streamerName: props.video.streamer_name
  }
}))

const handleSelect = () => {
  emit('select', props.video)
}

const handlePlay = () => {
  if (!canPlay.value) return

  if (props.disableNavigation) {
    emit('select', props.video)
    return
  }

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

.video-card-action {
  position: relative;
  cursor: pointer;
}

.video-card-link {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: block;
  padding: 0;
  border: 0;
  border-radius: var(--radius-xl);
  background: transparent;
  color: inherit;
  text-decoration: none;
  cursor: pointer;

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 3px;
    box-shadow: var(--shadow-primary);
  }
}

.video-card-link-disabled {
  cursor: default;
  pointer-events: none;
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

  .placeholder-body {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-1);
    padding: var(--spacing-2);
    text-align: center;
    max-width: 100%;
  }

  .icon-video {
    width: 48px;
    height: 48px;
    stroke: var(--text-secondary);
    fill: none;
    opacity: 0.4;
  }

  .placeholder-label {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    font-weight: v.$font-medium;
    white-space: nowrap;
  }

  .placeholder-cue {
    font-size: 11px;
    color: var(--text-tertiary);
    opacity: 0.7;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
    padding: 0 var(--spacing-1);
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

.video-status-badge {
  position: absolute;
  top: 8px;
  left: 8px;
}

.hover-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;

  // Dark scrim only - a backdrop-filter here is composited for every card
  // in the grid even while invisible (opacity 0), which costs GPU time.
  background: rgba(0, 0, 0, 0.6);

  display: flex;
  align-items: center;
  justify-content: center;

  opacity: 0;
  transition: opacity v.$duration-200 v.$ease-out;

  &.is-disabled {
    background: rgba(0, 0, 0, 0.48);
  }
}

.play-button {
  position: relative;
  z-index: 2;
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

  &:disabled {
    width: auto;
    min-width: 96px;
    padding: 0 var(--spacing-3);
    border-radius: var(--radius-full);
    background: var(--background-card);
    color: var(--text-secondary);
    cursor: not-allowed;
    transform: none;
    box-shadow: none;

    .icon-play {
      width: 20px;
      height: 20px;
      margin-left: 0;
      stroke: currentColor;
    }
  }
}

.play-button-label {
  margin-left: var(--spacing-2);
  font-size: var(--text-xs);
  font-weight: v.$font-semibold;
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
  line-clamp: 2;  // Standard property for compatibility
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
  min-width: 0;
}

.streamer-name {
  font-weight: v.$font-medium;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.separator {
  opacity: 0.5;
}

.video-category {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-bottom: var(--spacing-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-state-message {
  margin: 0 0 var(--spacing-2) 0;
  color: var(--text-tertiary);
  font-size: var(--text-xs);
  line-height: v.$leading-snug;
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

  .video-status-badge {
    top: 10px;
    left: 10px;
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

/* ========================================
   LIST MODE STYLES
   Horizontal layout with thumbnail on left
   ======================================== */
.video-card.list-mode {
  :deep(.glass-card-content) {
    padding: 0;
  }

  // The row layout lives on .video-card-action: thumbnail and info are its
  // children (.glass-card-content only wraps this single element, so flexing
  // the content div had no effect and the info stacked under the thumbnail).
  .video-card-action {
    display: flex;
    flex-direction: row;
    align-items: stretch;
  }

  .video-thumbnail {
    flex-shrink: 0;
    align-self: center;
    width: 168px;
    aspect-ratio: 16 / 9;
    height: auto;
    padding-top: 0;
    margin: var(--spacing-2);
    border-radius: var(--radius-lg);
    overflow: hidden;

    img, .thumbnail-placeholder {
      position: absolute;
      top: 0;
      left: 0;
    }
  }

  .thumbnail-placeholder {
    .placeholder-body {
      gap: 2px;
      padding: var(--spacing-1);
    }

    .icon-video {
      width: 32px;
      height: 32px;
    }

    // The duration badge sits over this corner in the compact list thumb
    .placeholder-cue {
      display: none;
    }
  }

  .duration-badge {
    bottom: 4px;
    right: 4px;
    font-size: 11px;
    padding: 2px 4px;
  }

  .video-status-badge {
    top: 4px;
    left: 4px;
  }

  .video-info {
    flex: 1;
    min-width: 0;
    padding: var(--spacing-3) var(--spacing-4);
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: var(--spacing-1);
  }

  .video-title {
    font-size: var(--text-sm);
    margin: 0;
    -webkit-line-clamp: 1;
    line-clamp: 1;
  }

  .video-meta {
    font-size: var(--text-xs);
    margin: 0;
  }

  .video-category {
    display: none;
  }

  .video-stats {
    font-size: var(--text-xs);
  }

  // Hover effect for list mode
  &:hover {
    .video-thumbnail {
      &::after {
        content: '';
        position: absolute;
        inset: 0;
        background: rgba(0, 0, 0, 0.3);
        transition: opacity v.$duration-200 v.$ease-out;
      }
    }
  }
}

// Responsive list mode
@include m.respond-below('sm') {
  .video-card.list-mode {
    .video-thumbnail {
      width: 120px;
    }

    .video-info {
      padding: var(--spacing-2) var(--spacing-3);
    }

    .video-title {
      font-size: var(--text-xs);
    }

    .video-meta,
    .video-stats {
      font-size: 11px;
    }
  }
}
</style>
