<template>
  <div class="empty-state" :class="`empty-state-${variant}`">
    <div class="empty-state-content">
      <!-- Icon -->
      <div class="empty-icon">
        <svg v-if="icon" class="icon">
          <use :href="`#icon-${icon}`" />
        </svg>
        <div v-else class="icon-placeholder">?</div>
      </div>

      <!-- Title -->
      <h3 class="empty-title">{{ title }}</h3>

      <!-- Description -->
      <p v-if="description" class="empty-description">{{ description }}</p>

      <!-- Action Button -->
      <button
        v-if="actionLabel"
        @click="handleAction"
        class="empty-action"
        :class="`btn-${actionVariant}`"
      >
        <svg v-if="actionIcon" class="action-icon">
          <use :href="`#icon-${actionIcon}`" />
        </svg>
        {{ actionLabel }}
      </button>

      <!-- Custom slot for additional content -->
      <slot />
    </div>

    <!-- Decorative elements (optional) -->
    <div v-if="showDecoration" class="empty-decoration">
      <div class="decoration-circle decoration-1"></div>
      <div class="decoration-circle decoration-2"></div>
      <div class="decoration-circle decoration-3"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
export type EmptyStateVariant = 'default' | 'compact' | 'large'
export type ActionVariant = 'primary' | 'secondary' | 'outline'

interface Props {
  /** Title text */
  title: string
  /** Description text (optional) */
  description?: string
  /** Icon name (from icons.svg) */
  icon?: string
  /** Action button label */
  actionLabel?: string
  /** Action button icon */
  actionIcon?: string
  /** Action button variant */
  actionVariant?: ActionVariant
  /** Size variant */
  variant?: EmptyStateVariant
  /** Show decorative background elements */
  showDecoration?: boolean
}

withDefaults(defineProps<Props>(), {
  actionVariant: 'primary',
  variant: 'default',
  showDecoration: true
})

const emit = defineEmits<{
  action: []
}>()

const handleAction = () => {
  emit('action')
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */


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

  &.empty-state-large {
    min-height: 500px;
    padding: var(--spacing-12);
  }
}

.empty-state-content {
  position: relative;
  z-index: 2;
  text-align: center;
  max-width: 400px;

  animation: fade-in v.$duration-500 v.$ease-out;
}

.empty-icon {
  width: 120px;
  height: 120px;
  margin: 0 auto var(--spacing-6);

  display: flex;
  align-items: center;
  justify-content: center;

  background: rgba(var(--primary-500-rgb), 0.1);
  border: 2px solid rgba(var(--primary-500-rgb), 0.2);
  border-radius: 50%;

  animation: bounce-in v.$duration-500 v.$ease-bounce;

  .icon {
    width: 60px;
    height: 60px;
    stroke: var(--primary-color);
    fill: none;
    opacity: 0.8;
  }
}

.icon-placeholder {
  font-size: 60px;
  color: var(--primary-color);
  opacity: 0.6;
  font-weight: v.$font-bold;
}

.empty-title {
  font-size: var(--text-2xl);
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-3) 0;
  line-height: v.$leading-tight;
}

.empty-description {
  font-size: var(--text-base);
  color: var(--text-secondary);
  line-height: v.$leading-relaxed;
  margin: 0 0 var(--spacing-6) 0;
}

.empty-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);

  padding: var(--spacing-3) var(--spacing-6);
  border-radius: var(--radius-lg);

  font-size: var(--text-base);
  font-weight: v.$font-medium;

  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;

  &.btn-primary {
    background: var(--primary-color);
    color: white;
    border: none;

    &:hover {
      background: var(--primary-600);
      transform: translateY(-2px);
      box-shadow: var(--shadow-md);
    }
  }

  &.btn-secondary {
    background: var(--accent-color);
    color: white;
    border: none;

    &:hover {
      background: var(--accent-600);
      transform: translateY(-2px);
      box-shadow: var(--shadow-md);
    }
  }

  &.btn-outline {
    background: transparent;
    color: var(--primary-color);
    border: 2px solid var(--primary-color);

    &:hover {
      background: rgba(var(--primary-500-rgb), 0.1);
      transform: translateY(-2px);
    }
  }

  &:active {
    transform: translateY(0);
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }

  .action-icon {
    width: 20px;
    height: 20px;
    stroke: currentColor;
    fill: none;
  }
}

// Decorative background elements
.empty-decoration {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1;
  pointer-events: none;
  overflow: hidden;
}

.decoration-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.05;

  &.decoration-1 {
    width: 300px;
    height: 300px;
    top: -100px;
    right: -100px;
    background: var(--primary-color);
    animation: pulse-scale 8s v.$ease-in-out infinite;
  }

  &.decoration-2 {
    width: 200px;
    height: 200px;
    bottom: -50px;
    left: -50px;
    background: var(--accent-color);
    animation: pulse-scale 6s v.$ease-in-out infinite;
    animation-delay: 1s;
  }

  &.decoration-3 {
    width: 150px;
    height: 150px;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: var(--info-color);
    animation: pulse-scale 10s v.$ease-in-out infinite;
    animation-delay: 2s;
  }
}

// Compact variant adjustments
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

// Large variant adjustments
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

// Responsive
@include m.respond-below('sm') {  // < 640px
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
