<template>
  <component
    :is="tag"
    class="glass-card"
    :class="[
      `glass-card-${variant}`,
      {
        'glass-hover-lift': hoverable && hoverEffect === 'lift',
        'glass-hover-scale': hoverable && hoverEffect === 'scale',
        'glass-card-elevated': elevated,
        'glass-card-clickable': clickable,
        'glass-card-disabled': isDisabled,
        'glass-card-loading': loading
      }
    ]"
    :role="computedRole"
    :tabindex="computedTabindex"
    :aria-labelledby="titleId"
    :aria-describedby="describedBy"
    :aria-disabled="isDisabled || undefined"
    :aria-busy="loading || undefined"
    @click="handleClick"
    @keydown.enter.prevent="handleKeyboardClick"
    @keydown.space.prevent="handleKeyboardClick"
    @touchstart.passive="onTouchStart"
    @touchmove.passive="onTouchMove"
  >
    <!-- Gradient Border (optional) -->
    <div v-if="gradient" class="gradient-border" :style="gradientStyle" />

    <header v-if="$slots.header || $slots.title || $slots.actions" class="glass-card-header">
      <div class="glass-card-heading">
        <slot name="header">
          <h2 v-if="$slots.title" :id="titleId" class="glass-card-title">
            <slot name="title" />
          </h2>
          <p v-if="$slots.description" class="glass-card-description">
            <slot name="description" />
          </p>
        </slot>
      </div>
      <div v-if="$slots.actions" class="glass-card-actions">
        <slot name="actions" />
      </div>
    </header>

    <div class="glass-card-content" :class="contentPaddingClasses">
      <slot />
    </div>

    <footer v-if="$slots.footer" class="glass-card-footer">
      <slot name="footer" />
    </footer>

    <div v-if="loading" class="glass-card-loader-overlay" aria-hidden="true">
      <slot name="loading">
        <span class="loader" />
      </slot>
    </div>
  </component>
</template>

<script setup lang="ts">
import { computed, useId, useSlots } from 'vue'
import { useTouchClick } from '@/composables/useTouchClick'

export type GlassVariant = 'subtle' | 'medium' | 'strong'
export type HoverEffect = 'lift' | 'scale' | 'none'
export type PaddingSize = 'sm' | 'md' | 'lg' | 'xl'

interface Props {
  /** Glass intensity variant */
  variant?: GlassVariant
  /** Enable hover effects */
  hoverable?: boolean
  /** Type of hover effect */
  hoverEffect?: HoverEffect
  /** Elevated shadow (higher z-index appearance) */
  elevated?: boolean
  /** Show gradient border at top */
  gradient?: boolean
  /** Gradient colors [start, end] */
  gradientColors?: [string, string]
  /** Apply default padding or specific size */
  padding?: boolean | PaddingSize
  /** Make card clickable (cursor pointer) */
  clickable?: boolean
  /** Disable click and keyboard activation */
  disabled?: boolean
  /** Show a loading overlay and disable activation */
  loading?: boolean
  /** Region label id. Generated from the title slot when omitted. */
  labelledBy?: string
  describedBy?: string
  /** ARIA role override. Clickable cards default to button. */
  role?: string
  /** Keyboard tab index override. Clickable cards default to 0. */
  tabindex?: number | string
  /** HTML tag to render as */
  tag?: string
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'medium',
  hoverable: false,
  hoverEffect: 'lift',
  elevated: false,
  gradient: false,
  gradientColors: () => ['var(--primary-color)', 'var(--accent-color)'],
  padding: true,
  clickable: false,
  disabled: false,
  loading: false,
  tag: 'div'
})

const emit = defineEmits<{
  click: [event: MouseEvent | KeyboardEvent]
}>()

const slots = useSlots()
const generatedTitleId = useId()
const titleId = computed(() => props.labelledBy || (slots.title ? generatedTitleId : undefined))
const isDisabled = computed(() => props.disabled || props.loading)
const computedRole = computed(() => props.role || (props.clickable ? 'button' : undefined))
const computedTabindex = computed(() => {
  if (props.tabindex !== undefined) return props.tabindex
  if (props.clickable && !isDisabled.value) return 0
  return undefined
})

const gradientStyle = computed(() => ({
  background: `linear-gradient(135deg, ${props.gradientColors[0]}, ${props.gradientColors[1]})`
}))

const contentPaddingClasses = computed(() => {
  if (props.padding === false) {
    return []
  }

  if (props.padding === true) {
    return ['with-padding']
  }

  if (typeof props.padding === 'string') {
    return [`padding-${props.padding}`]
  }

  return ['with-padding']
})

const { onClick: handleClick, onTouchStart, onTouchMove } = useTouchClick<MouseEvent>(
  (event) => {
    if (props.clickable && !isDisabled.value) {
      emit('click', event)
    }
  }
)

function handleKeyboardClick(event: KeyboardEvent) {
  if (props.clickable && !isDisabled.value) {
    emit('click', event)
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.glass-card {
  position: relative;
  overflow: hidden;
  min-width: 0;
  padding: 0;
  border-radius: var(--radius-xl);

  // Glass look via translucency + border highlight, WITHOUT backdrop-filter:
  // grids render dozens of these cards at once and per-card blur is the main
  // scroll-performance cost. Real blur is reserved for floating layers
  // (header, nav, popups, modals) where content actually passes underneath.
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  box-shadow: var(--glass-shadow-sm), var(--glass-glow);

  &.glass-card-subtle {
    background: var(--glass-bg-subtle);
  }

  &.glass-card-strong {
    background: var(--glass-bg-strong);
    box-shadow: var(--glass-shadow-md), var(--glass-glow);
  }

  &.glass-card-elevated {
    box-shadow: var(--glass-shadow-lg);
  }

  &.glass-card-clickable {
    cursor: pointer;
  }

  &.glass-card-disabled {
    cursor: not-allowed;
    opacity: 0.62;
  }

  &.glass-card-loading {
    cursor: progress;
  }

  &.glass-card-clickable:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 3px;
    box-shadow: var(--glass-shadow-lg), var(--shadow-primary);
  }

  // Hover effects
  &.glass-hover-lift {
    transition: transform v.$duration-200 v.$ease-out, box-shadow v.$duration-200 v.$ease-out;

    &:hover:not(.glass-card-disabled):not(.glass-card-loading) {
      transform: translateY(-4px);
      box-shadow: var(--glass-shadow-lg);
    }
  }

  &.glass-hover-scale {
    transition: transform v.$duration-200 v.$ease-out;

    &:hover:not(.glass-card-disabled):not(.glass-card-loading) {
      transform: scale(1.02);
    }
  }
}

.glass-card-header,
.glass-card-footer {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-4);
  padding: var(--spacing-5) var(--spacing-6) 0;
}

.glass-card-footer {
  padding-top: var(--spacing-4);
  padding-bottom: var(--spacing-5);
  border-top: 1px solid var(--glass-border);
}

.glass-card-heading,
.glass-card-content {
  min-width: 0;
}

.glass-card-title {
  margin: 0;
  color: var(--text-primary);
  font-size: v.$text-xl;
  font-weight: v.$font-semibold;
  line-height: v.$leading-tight;
}

.glass-card-description {
  margin: var(--spacing-1) 0 0;
  color: var(--text-secondary);
  font-size: v.$text-sm;
  line-height: v.$leading-relaxed;
}

.glass-card-actions {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--spacing-2);
}

.gradient-border {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
  z-index: 1;
}

.glass-card-content {
  position: relative;
  z-index: 2;

  &.with-padding {
    padding: var(--spacing-6);

    @include m.respond-below('md') {
      padding: var(--spacing-4);
    }
  }

  &.padding-sm {
    padding: var(--spacing-4);

    @include m.respond-below('md') {
      padding: var(--spacing-3);
    }
  }

  &.padding-md {
    padding: var(--spacing-5);

    @include m.respond-below('md') {
      padding: var(--spacing-4);
    }
  }

  &.padding-lg {
    padding: var(--spacing-6);

    @include m.respond-below('md') {
      padding: var(--spacing-4);
    }
  }

  &.padding-xl {
    padding: var(--spacing-8);

    @include m.respond-below('md') {
      padding: var(--spacing-6);
    }
  }
}

.glass-card-loader-overlay {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.24);
  backdrop-filter: blur(var(--glass-blur-sm));
  -webkit-backdrop-filter: blur(var(--glass-blur-sm));
  pointer-events: none;
}

@include m.respond-below('md') {
  .glass-card-header,
  .glass-card-footer {
    flex-direction: column;
    padding-inline: var(--spacing-4);
  }
}
</style>
