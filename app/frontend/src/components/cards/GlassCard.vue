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
  >
    <!-- Gradient Border (optional) -->
    <div v-if="gradient" class="gradient-border" :style="gradientStyle" />
    
    <!-- Card Content -->
    <div class="glass-card-content" :class="{ 'with-padding': padding }">
      <slot />
    </div>
  </component>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export type GlassVariant = 'subtle' | 'medium' | 'strong'
export type HoverEffect = 'lift' | 'scale' | 'none'

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
  /** Apply default padding to content */
  padding?: boolean
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

const handleClick = (event: MouseEvent) => {
  if (props.clickable) {
    emit('click', event)
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/glass' as g;

.glass-card {
  position: relative;
  overflow: hidden;
  
  // Apply glass variants
  &.glass-card-subtle {
    @include g.glass-card(10px, 0.5, 0.05);
  }
  
  &.glass-card-medium {
    @include g.glass-card(20px, 0.7, 0.1);
  }
  
  &.glass-card-strong {
    @include g.glass-card(40px, 0.9, 0.15);
  }
  
  // Clickable cursor
  &.glass-card-clickable {
    cursor: pointer;
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
    padding: var(--spacing-6); // 24px
  }
}

// Hover effects are applied via utility classes from _glass.scss
// .glass-hover-lift and .glass-hover-scale
</style>
