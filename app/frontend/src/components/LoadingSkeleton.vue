<template>
  <div class="skeleton-wrapper" :class="`skeleton-${type}`">
    <!-- Card Skeleton -->
    <div v-if="type === 'card'" class="skeleton-card">
      <div class="skeleton skeleton-image" />
      <div class="skeleton-content">
        <div class="skeleton skeleton-title" />
        <div class="skeleton skeleton-subtitle" />
        <div class="skeleton skeleton-text" />
      </div>
    </div>

    <!-- List Item Skeleton -->
    <div v-else-if="type === 'list-item'" class="skeleton-list-item">
      <div class="skeleton skeleton-avatar" />
      <div class="skeleton-content">
        <div class="skeleton skeleton-title" />
        <div class="skeleton skeleton-text" />
      </div>
    </div>

    <!-- Streamer Card Skeleton -->
    <div v-else-if="type === 'streamer'" class="skeleton-streamer">
      <div class="skeleton skeleton-avatar-large" />
      <div class="skeleton-content">
        <div class="skeleton skeleton-title" />
        <div class="skeleton skeleton-subtitle" />
        <div class="skeleton-actions">
          <div class="skeleton skeleton-button" />
          <div class="skeleton skeleton-button" />
        </div>
      </div>
    </div>

    <!-- Video Card Skeleton -->
    <div v-else-if="type === 'video'" class="skeleton-video">
      <div class="skeleton skeleton-thumbnail" />
      <div class="skeleton-content">
        <div class="skeleton skeleton-title-multi" />
        <div class="skeleton skeleton-text" />
      </div>
    </div>

    <!-- Status Card Skeleton -->
    <div v-else-if="type === 'status'" class="skeleton-status">
      <div class="skeleton skeleton-icon" />
      <div class="skeleton-content">
        <div class="skeleton skeleton-value" />
        <div class="skeleton skeleton-label" />
      </div>
    </div>

    <!-- Text Skeleton (generic) -->
    <div v-else-if="type === 'text'" class="skeleton-text-wrapper">
      <div v-for="i in lines" :key="i" class="skeleton skeleton-text-line" :style="{ width: i === lines ? '70%' : '100%' }" />
    </div>

    <!-- Custom Skeleton -->
    <slot v-else />
  </div>
</template>

<script setup lang="ts">
export type SkeletonType = 'card' | 'list-item' | 'streamer' | 'video' | 'status' | 'text' | 'custom'

interface Props {
  /** Type of skeleton to display */
  type?: SkeletonType
  /** Number of text lines (for type="text") */
  lines?: number
}

withDefaults(defineProps<Props>(), {
  type: 'card',
  lines: 3
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.skeleton-wrapper {
  width: 100%;
}

// Skeleton Card
.skeleton-card {
  background: var(--background-card);
  border-radius: var(--radius-xl);
  padding: var(--spacing-4);
  border: 1px solid var(--border-color);
}

.skeleton-image {
  width: 100%;
  height: 200px;
  margin-bottom: var(--spacing-4);
}

.skeleton-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.skeleton-title {
  height: 24px;
  width: 70%;
}

.skeleton-subtitle {
  height: 18px;
  width: 50%;
}

.skeleton-text {
  height: 16px;
  width: 100%;
}

// List Item Skeleton
.skeleton-list-item {
  display: flex;
  gap: var(--spacing-4);
  padding: var(--spacing-4);
  background: var(--background-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

.skeleton-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  flex-shrink: 0;
}

// Streamer Card Skeleton
.skeleton-streamer {
  display: flex;
  gap: var(--spacing-4);
  padding: var(--spacing-4);
  background: var(--background-card);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-color);
}

.skeleton-avatar-large {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-xl);
  flex-shrink: 0;
}

.skeleton-actions {
  display: flex;
  gap: var(--spacing-2);
  margin-top: var(--spacing-2);
}

.skeleton-button {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-lg);
}

// Video Card Skeleton
.skeleton-video {
  background: var(--background-card);
  border-radius: var(--radius-xl);
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.skeleton-thumbnail {
  width: 100%;
  padding-top: 56.25%; // 16:9 aspect ratio
}

.skeleton-title-multi {
  height: 20px;
  width: 90%;
  margin-bottom: var(--spacing-1);
}

// Status Card Skeleton
.skeleton-status {
  display: flex;
  gap: var(--spacing-4);
  padding: var(--spacing-5);
  background: var(--background-card);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-color);
}

.skeleton-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-lg);
  flex-shrink: 0;
}

.skeleton-value {
  height: 32px;
  width: 80px;
  margin-bottom: var(--spacing-2);
}

.skeleton-label {
  height: 18px;
  width: 120px;
}

// Text Skeleton
.skeleton-text-wrapper {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.skeleton-text-line {
  height: 16px;
}

// Generic spacing
.skeleton-content {
  flex: 1;
  min-width: 0;
}

// Responsive
@media (max-width: 640px) {
  .skeleton-streamer,
  .skeleton-list-item {
    flex-direction: column;
  }

  .skeleton-avatar-large {
    width: 100%;
    height: 120px;
  }
}
</style>
