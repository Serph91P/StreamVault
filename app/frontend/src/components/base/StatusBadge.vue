<script setup lang="ts">
import { computed } from 'vue'

export type StatusBadgeTone =
  | 'neutral'
  | 'primary'
  | 'success'
  | 'danger'
  | 'warning'
  | 'info'
  | 'live'
  | 'recording'
  | 'offline'
  | 'processing'
  | 'completed'

interface Props {
  tone?: StatusBadgeTone
  size?: 'sm' | 'md' | 'lg'
  dot?: boolean
  pulse?: boolean
  uppercase?: boolean
  ariaLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  tone: 'neutral',
  size: 'md',
  dot: false,
  pulse: false,
  uppercase: true,
})

const classes = computed(() => [
  'status-badge',
  `status-badge-${props.tone}`,
  props.size !== 'md' && `status-badge-${props.size}`,
  props.dot && 'status-badge-dot',
  props.pulse && 'status-badge-pulse',
  !props.uppercase && 'status-badge-normal-case',
])
</script>

<template>
  <span :class="classes" :aria-label="ariaLabel">
    <span v-if="dot" class="status-badge-dot-mark" aria-hidden="true" />
    <slot />
  </span>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  min-height: 1.5rem;
  padding: var(--spacing-1) var(--spacing-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  background: var(--background-darker);
  color: var(--text-secondary);
  font-size: v.$text-xs;
  font-weight: v.$font-semibold;
  line-height: 1;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  white-space: nowrap;
}

.status-badge-sm {
  min-height: 1.25rem;
  padding: 2px var(--spacing-2);
  font-size: 0.625rem;
}

.status-badge-lg {
  min-height: 2rem;
  padding: var(--spacing-2) var(--spacing-4);
  font-size: v.$text-sm;
}

.status-badge-normal-case {
  letter-spacing: normal;
  text-transform: none;
}

.status-badge-dot-mark {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 999px;
  background: currentColor;
  flex: 0 0 auto;
}

.status-badge-pulse .status-badge-dot-mark,
.status-badge-recording .status-badge-dot-mark,
.status-badge-live .status-badge-dot-mark {
  animation: pulse 2s ease-in-out infinite;
}

.status-badge-primary {
  background: rgba(var(--primary-color-rgb), 0.15);
  color: var(--primary-color);
  border-color: rgba(var(--primary-color-rgb), 0.3);

  [data-theme="light"] & {
    color: var(--primary-color-dark);
  }
}

.status-badge-success,
.status-badge-completed {
  background: rgba(var(--success-500-rgb), 0.15);
  color: var(--success-text-color);
  border-color: rgba(var(--success-500-rgb), 0.3);
}

.status-badge-danger,
.status-badge-live,
.status-badge-recording {
  background: rgba(var(--danger-color-rgb), 0.15);
  color: var(--danger-text-color);
  border-color: rgba(var(--danger-color-rgb), 0.3);
}

.status-badge-recording {
  border-color: var(--danger-color);
}

.status-badge-warning,
.status-badge-processing {
  background: rgba(var(--warning-color-rgb), 0.15);
  color: var(--text-primary);
  border-color: rgba(var(--warning-color-rgb), 0.3);
}

.status-badge-info {
  background: rgba(var(--info-500-rgb), 0.15);
  color: var(--info-text-color);
  border-color: rgba(var(--info-500-rgb), 0.3);
}

.status-badge-neutral,
.status-badge-offline {
  background: var(--background-darker);
  color: var(--text-secondary);
  border-color: var(--border-color);
}
</style>
