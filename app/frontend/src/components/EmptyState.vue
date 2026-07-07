<template>
  <div class="empty-state" :class="stateClasses" :role="computedRole" :aria-live="ariaLive">
    <div class="empty-state-content">
      <div class="empty-icon" aria-hidden="true">
        <svg v-if="displayIcon" class="icon">
          <use :href="`#icon-${displayIcon}`" />
        </svg>
        <div v-else class="icon-placeholder">?</div>
      </div>

      <h2 class="empty-title">{{ title }}</h2>
      <span v-if="toneLabel" class="sr-only">{{ toneLabel }}</span>

      <p v-if="description" class="empty-description">{{ description }}</p>

      <div v-if="actionLabel || retryLabel" class="empty-actions">
        <BaseButton
          v-if="actionLabel"
          class="empty-action"
          :variant="actionVariant"
          @click="handleAction"
        >
          <svg v-if="actionIcon" class="action-icon" aria-hidden="true">
            <use :href="`#icon-${actionIcon}`" />
          </svg>
          {{ actionLabel }}
        </BaseButton>
        <BaseButton
          v-if="retryLabel"
          class="empty-action"
          :variant="retryVariant"
          @click="handleRetry"
        >
          <svg v-if="retryIcon" class="action-icon" aria-hidden="true">
            <use :href="`#icon-${retryIcon}`" />
          </svg>
          {{ retryLabel }}
        </BaseButton>
      </div>

      <slot />
    </div>

    <div v-if="showDecoration" class="empty-decoration" aria-hidden="true">
      <div class="decoration-circle decoration-1"></div>
      <div class="decoration-circle decoration-2"></div>
      <div class="decoration-circle decoration-3"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'

export type EmptyStateVariant = 'default' | 'compact' | 'inline' | 'large'
export type EmptyStateTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'
export type ActionVariant = 'primary' | 'secondary' | 'success' | 'danger' | 'warning' | 'info' | 'outline' | 'outline-primary' | 'outline-danger'

interface Props {
  /** Title text */
  title: string
  /** Description text (optional) */
  description?: string
  /** Icon name from the StreamVault icon sprite */
  icon?: string
  /** Tone describes status with color, icon and assistive text */
  tone?: EmptyStateTone
  /** Optional screen reader status label for the tone */
  toneLabel?: string
  /** Action button label */
  actionLabel?: string
  /** Action button icon */
  actionIcon?: string
  /** Action button variant */
  actionVariant?: ActionVariant
  /** Retry button label for recoverable errors */
  retryLabel?: string
  /** Retry button icon */
  retryIcon?: string
  /** Retry button variant */
  retryVariant?: ActionVariant
  /** Size variant */
  variant?: EmptyStateVariant
  /** Show decorative background elements */
  showDecoration?: boolean
  /** Add a spinning affordance to the icon for loading states */
  loading?: boolean
  /** Override landmark role */
  role?: 'status' | 'alert' | 'presentation'
}

const props = withDefaults(defineProps<Props>(), {
  tone: 'neutral',
  actionVariant: 'primary',
  retryIcon: 'refresh-cw',
  retryVariant: 'outline',
  variant: 'default',
  showDecoration: false,
  loading: false,
})

const emit = defineEmits<{
  action: []
  retry: []
}>()

const toneIcons: Record<EmptyStateTone, string> = {
  neutral: 'info',
  info: 'info',
  success: 'check-circle',
  warning: 'alert-triangle',
  danger: 'alert-circle'
}

const displayIcon = computed(() => props.icon || toneIcons[props.tone])
const computedRole = computed(() => props.role || (props.tone === 'danger' ? 'alert' : 'status'))
const ariaLive = computed(() => (computedRole.value === 'alert' ? 'assertive' : 'polite'))
const stateClasses = computed(() => [
  `empty-state-${props.variant}`,
  `empty-state-tone-${props.tone}`,
  props.loading && 'empty-state-is-loading'
])

const handleAction = () => {
  emit('action')
}

const handleRetry = () => {
  emit('retry')
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.empty-state {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: var(--spacing-8);
  overflow: hidden;

  &.empty-state-compact {
    min-height: 250px;
    padding: var(--spacing-6);
  }

  &.empty-state-inline {
    min-height: 0;
    padding: var(--spacing-4);
  }

  &.empty-state-large {
    min-height: 500px;
    padding: var(--spacing-12);
  }
}

.empty-state-content {
  position: relative;
  z-index: 2;
  max-width: 400px;
  text-align: center;
  animation: fade-in v.$duration-500 v.$ease-out;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 120px;
  height: 120px;
  margin: 0 auto var(--spacing-6);
  border: 2px solid rgba(var(--primary-500-rgb), 0.2);
  border-radius: var(--radius-full);
  background: rgba(var(--primary-500-rgb), 0.1);
  color: var(--primary-color);
  animation: bounce-in v.$duration-500 v.$ease-bounce;

  .icon {
    width: 60px;
    height: 60px;
    stroke: currentColor;
    fill: none;
    opacity: 0.85;
  }
}

.empty-state-tone-success .empty-icon {
  border-color: rgba(var(--success-color-rgb), 0.25);
  background: rgba(var(--success-color-rgb), 0.1);
  color: var(--success-color);
}

.empty-state-tone-warning .empty-icon {
  border-color: rgba(var(--warning-color-rgb), 0.28);
  background: rgba(var(--warning-color-rgb), 0.12);
  color: var(--warning-color);
}

.empty-state-tone-danger .empty-icon {
  border-color: rgba(var(--danger-color-rgb), 0.28);
  background: rgba(var(--danger-color-rgb), 0.12);
  color: var(--danger-color);
}

.empty-state-tone-info .empty-icon {
  border-color: rgba(var(--info-500-rgb), 0.25);
  background: rgba(var(--info-500-rgb), 0.1);
  color: var(--info-color);
}

.empty-state-is-loading .empty-icon .icon {
  animation: spin var(--duration-500) linear infinite;
}

.icon-placeholder {
  color: currentColor;
  font-size: 60px;
  font-weight: v.$font-bold;
  opacity: 0.6;
}

.empty-title {
  margin: 0 0 var(--spacing-3) 0;
  color: var(--text-primary);
  font-size: var(--text-2xl);
  font-weight: v.$font-semibold;
  line-height: v.$leading-tight;
}

.empty-description {
  margin: 0 0 var(--spacing-6) 0;
  color: var(--text-secondary);
  font-size: var(--text-base);
  line-height: v.$leading-relaxed;
}

.empty-actions {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--spacing-2);
}

.empty-action {
  .action-icon {
    width: 20px;
    height: 20px;
    stroke: currentColor;
    fill: none;
  }
}

.empty-decoration {
  position: absolute;
  inset: 0;
  z-index: 1;
  overflow: hidden;
  pointer-events: none;
}

.decoration-circle {
  position: absolute;
  border-radius: var(--radius-full);
  opacity: 0.05;

  &.decoration-1 {
    top: -100px;
    right: -100px;
    width: 300px;
    height: 300px;
    background: var(--primary-color);
    animation: pulse-scale 8s v.$ease-in-out infinite;
  }

  &.decoration-2 {
    bottom: -50px;
    left: -50px;
    width: 200px;
    height: 200px;
    background: var(--accent-color);
    animation: pulse-scale 6s v.$ease-in-out infinite;
    animation-delay: 1s;
  }

  &.decoration-3 {
    top: 50%;
    left: 50%;
    width: 150px;
    height: 150px;
    background: var(--info-color);
    transform: translate(-50%, -50%);
    animation: pulse-scale 10s v.$ease-in-out infinite;
    animation-delay: 2s;
  }
}

.empty-state-compact {
  .empty-icon {
    width: 80px;
    height: 80px;

    .icon {
      width: 40px;
      height: 40px;
    }
  }

  .empty-title {
    font-size: var(--text-xl);
  }

  .empty-description {
    font-size: var(--text-sm);
  }
}

.empty-state-inline {
  justify-content: flex-start;
  border: 1px solid rgba(var(--danger-color-rgb), 0.24);
  border-radius: var(--radius-lg);
  background: rgba(var(--danger-color-rgb), 0.08);

  .empty-state-content {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    width: 100%;
    max-width: none;
    column-gap: var(--spacing-3);
    text-align: left;
  }

  .empty-icon {
    grid-row: span 2;
    width: 36px;
    height: 36px;
    margin: 0;

    .icon {
      width: 20px;
      height: 20px;
    }
  }

  .empty-title {
    margin-bottom: var(--spacing-1);
    font-size: var(--text-sm);
  }

  .empty-description {
    margin-bottom: 0;
    font-size: var(--text-sm);
  }

  .empty-actions {
    grid-column: 2;
    justify-content: flex-start;
    margin-top: var(--spacing-2);
  }
}

.empty-state-large {
  .empty-icon {
    width: 160px;
    height: 160px;

    .icon {
      width: 80px;
      height: 80px;
    }
  }

  .empty-title {
    font-size: var(--text-3xl);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@include m.respond-below('sm') {
  .empty-state {
    min-height: 300px;
    padding: var(--spacing-6);
  }

  .empty-icon {
    width: 100px;
    height: 100px;

    .icon {
      width: 50px;
      height: 50px;
    }
  }

  .empty-title {
    font-size: var(--text-xl);
  }

  .empty-description {
    font-size: var(--text-sm);
  }
}
</style>
