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
        'glass-card-clickable': clickable
      }
    ]"
    @click="handleClick"
    @touchstart.passive="onTouchStart"
    @touchmove.passive="onTouchMove"
  >
    <!-- Gradient Border (optional) -->
    <div v-if="gradient" class="gradient-border" :style="gradientStyle" />
    
    <!-- Card Content -->
    <div class="glass-card-content" :class="contentPaddingClasses">
      <slot />
    </div>
  </component>
</template>

<script setup lang="ts">
import { computed } from 'vue'
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
  tag: 'div'
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

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
    if (props.clickable) {
      emit('click', event)
    }
  }
)
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.glass-card {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-xl);
  
  // Default: medium glass
  background: var(--glass-bg-medium);
  backdrop-filter: blur(var(--glass-blur-md));
  -webkit-backdrop-filter: blur(var(--glass-blur-md));
  border: 1px solid var(--glass-border);
  box-shadow: var(--glass-shadow-sm);
  
  @supports not (backdrop-filter: blur(1px)) {
    background: var(--glass-bg-solid);
  }
  
  &.glass-card-subtle {
    background: var(--glass-bg-subtle);
    backdrop-filter: blur(var(--glass-blur-sm));
    -webkit-backdrop-filter: blur(var(--glass-blur-sm));
  }
  
  &.glass-card-strong {
    background: var(--glass-bg-strong);
    backdrop-filter: blur(var(--glass-blur-lg));
    -webkit-backdrop-filter: blur(var(--glass-blur-lg));
    box-shadow: var(--glass-shadow-md);
  }
  
  &.glass-card-elevated {
    box-shadow: var(--glass-shadow-lg);
  }
  
  &.glass-card-clickable {
    cursor: pointer;
  }
  
  // Hover effects
  &.glass-hover-lift {
    transition: transform v.$duration-200 v.$ease-out, box-shadow v.$duration-200 v.$ease-out;
    
    &:hover {
      transform: translateY(-4px);
      box-shadow: var(--glass-shadow-lg);
    }
  }
  
  &.glass-hover-scale {
    transition: transform v.$duration-200 v.$ease-out;
    
    &:hover {
      transform: scale(1.02);
    }
  }
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
      padding: var(--spacing-3);
    }
  }

  &.padding-sm {
    padding: var(--spacing-4);
    
    @include m.respond-below('md') {
      padding: var(--spacing-2);
    }
  }

  &.padding-md {
    padding: var(--spacing-5);
    
    @include m.respond-below('md') {
      padding: var(--spacing-3);
    }
  }

  &.padding-lg {
    padding: var(--spacing-7);
    
    @include m.respond-below('md') {
      padding: var(--spacing-2);
    }
  }

  &.padding-xl {
    padding: var(--spacing-8);
    
    @include m.respond-below('md') {
      padding: var(--spacing-2);
    }
  }
}
</style>
