<template>
  <GlassCard
    :variant="variant"
    :elevated="elevated"
    :gradient="showGradient"
    :gradient-colors="gradientColors"
    class="status-card"
  >
    <div class="status-card-content">
      <!-- Icon -->
      <div class="status-icon" :class="`status-${type}`">
        <svg class="icon">
          <use :href="`#icon-${icon}`" />
        </svg>
      </div>

      <!-- Content -->
      <div class="status-info">
        <div class="status-value">
          {{ formattedValue }}
          <span v-if="trend" class="trend" :class="trendClass">
            {{ trendText }}
          </span>
        </div>
        <div class="status-label">{{ label }}</div>
        <div v-if="subtitle" class="status-subtitle">{{ subtitle }}</div>
      </div>

      <!-- Action Button (optional) -->
      <button
        v-if="actionLabel"
        @click.stop="handleAction"
        class="status-action"
        :aria-label="actionLabel"
      >
        <svg class="action-icon">
          <use href="#icon-chevron-right" />
        </svg>
      </button>
    </div>

    <!-- Progress Bar (optional) -->
    <div v-if="showProgress && progress !== undefined" class="progress-container">
      <div class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: `${progress}%` }"
          :class="`progress-${type}`"
        ></div>
      </div>
      <div class="progress-text">{{ progress }}%</div>
    </div>
  </GlassCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import GlassCard from './GlassCard.vue'

export type StatusType = 'primary' | 'success' | 'danger' | 'warning' | 'info'

interface Props {
  /** Card value to display */
  value: number | string
  /** Label text */
  label: string
  /** Subtitle text (optional) */
  subtitle?: string
  /** Icon name (from icons.svg) */
  icon: string
  /** Status type (determines colors) */
  type?: StatusType
  /** Trend indicator (+5%, -10%, etc.) */
  trend?: string
  /** Trend direction (up/down) */
  trendDirection?: 'up' | 'down'
  /** Show gradient border */
  showGradient?: boolean
  /** Glass variant */
  variant?: 'subtle' | 'medium' | 'strong'
  /** Elevated shadow */
  elevated?: boolean
  /** Progress percentage (0-100) */
  progress?: number
  /** Show progress bar */
  showProgress?: boolean
  /** Action button label */
  actionLabel?: string
  /** Format value as number */
  formatAsNumber?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  type: 'primary',
  variant: 'medium',
  elevated: false,
  showGradient: true,
  showProgress: false,
  formatAsNumber: true
})

const emit = defineEmits<{
  action: []
}>()

const formattedValue = computed(() => {
  if (!props.formatAsNumber || typeof props.value !== 'number') {
    return props.value
  }

  const num = props.value
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toLocaleString()
})

const trendClass = computed(() => {
  if (!props.trendDirection) return ''
  return props.trendDirection === 'up' ? 'trend-up' : 'trend-down'
})

const trendText = computed(() => {
  if (!props.trend) return ''
  const sign = props.trendDirection === 'up' ? '↑' : '↓'
  return `${sign} ${props.trend}`
})

const gradientColors = computed((): [string, string] => {
  const colors = {
    primary: ['var(--primary-color)', 'var(--accent-color)'],
    success: ['#10b981', '#059669'],
    danger: ['#ef4444', '#dc2626'],
    warning: ['#f59e0b', '#d97706'],
    info: ['#3b82f6', '#2563eb']
  }
  return colors[props.type] as [string, string]
})

const handleAction = () => {
  emit('action')
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */


.status-card {
  // Card specific overrides
  :deep(.glass-card-content) {
    padding: var(--spacing-5); // 20px
  }
}

.status-card-content {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-4);
}

.status-icon {
  width: 48px;
  height: 48px;
  flex-shrink: 0;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: var(--radius-lg);
  transition: all v.$duration-200 v.$ease-out;

  .icon {
    width: 24px;
    height: 24px;
    stroke: currentColor;
    fill: none;
  }

  &.status-primary {
    background: rgba(var(--primary-500-rgb), 0.2);
    color: var(--primary-color);
  }

  &.status-success {
    background: rgba(16, 185, 129, 0.2);
    color: var(--success-color);
  }

  &.status-danger {
    background: rgba(239, 68, 68, 0.2);
    color: var(--danger-color);
  }

  &.status-warning {
    background: rgba(245, 158, 11, 0.2);
    color: var(--warning-color);
  }

  &.status-info {
    background: rgba(59, 130, 246, 0.2);
    color: var(--info-color);
  }
}

.status-info {
  flex: 1;
  min-width: 0;
}

.status-value {
  font-size: var(--text-3xl);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  line-height: 1;
  margin-bottom: var(--spacing-1);

  display: flex;
  align-items: baseline;
  gap: var(--spacing-2);
}

.trend {
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;

  &.trend-up {
    color: var(--success-color);
  }

  &.trend-down {
    color: var(--danger-color);
  }
}

.status-label {
  font-size: var(--text-base);
  font-weight: v.$font-medium;
  color: var(--text-primary);
  margin-bottom: var(--spacing-1);
}

.status-subtitle {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.status-action {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  padding: 0;

  background: rgba(var(--primary-500-rgb), 0.1);
  border: 1px solid rgba(var(--primary-500-rgb), 0.3);
  border-radius: var(--radius-lg);

  display: flex;
  align-items: center;
  justify-content: center;

  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  .action-icon {
    width: 16px;
    height: 16px;
    stroke: var(--primary-color);
    fill: none;
  }

  &:hover {
    background: rgba(var(--primary-500-rgb), 0.2);
    border-color: var(--primary-color);
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

.progress-container {
  margin-top: var(--spacing-4);
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: var(--background-darker);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width v.$duration-300 v.$ease-out;

  &.progress-primary {
    background: var(--primary-color);
  }

  &.progress-success {
    background: var(--success-color);
  }

  &.progress-danger {
    background: var(--danger-color);
  }

  &.progress-warning {
    background: var(--warning-color);
  }

  &.progress-info {
    background: var(--info-color);
  }
}

.progress-text {
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  color: var(--text-secondary);
  min-width: 40px;
  text-align: right;
}

// Responsive
@include m.respond-below('sm') {  // < 640px
  .status-value {
    font-size: var(--text-2xl);
  }

  .status-icon {
    width: 40px;
    height: 40px;

    .icon {
      width: 20px;
      height: 20px;
    }
  }
}
</style>
