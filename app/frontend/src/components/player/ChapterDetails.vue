<template>
  <span class="chapter-info chapter-details" :class="{ 'chapter-details--truncate': truncate }">
    <span class="chapter-title" :title="truncate ? title : undefined">{{ title }}</span>
    <span class="chapter-category">{{ categoryName || 'Category unavailable' }}</span>
    <span class="chapter-time">{{ formatTime(start) }} - {{ formatTime(end) }}</span>
    <span class="chapter-duration">Duration: {{ formatTime(Math.max(0, end - start)) }}</span>
  </span>
</template>

<script setup lang="ts">
import { formatTime } from '@/utils/playerClock'

defineProps<{
  title: string
  categoryName?: string | null
  start: number
  end: number
  truncate?: boolean
}>()
</script>

<style scoped lang="scss">
.chapter-details {
  display: grid;
  gap: var(--spacing-1);
  flex: 1;
  min-width: 0;
  text-align: left;
  color: var(--text-primary);
  overflow-wrap: anywhere;
  line-height: var(--leading-snug);
}

.chapter-title {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  white-space: normal;
  overflow-wrap: anywhere;
}

.chapter-category {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.chapter-time,
.chapter-duration {
  font-size: var(--text-sm);
  font-variant-numeric: tabular-nums;
}

.chapter-time {
  font-size: var(--text-base);
}

.chapter-details--truncate .chapter-title {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
</style>
