<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'

interface Props {
  /** Application route rendered by Vue Router as a native anchor. */
  to: RouteLocationRaw
  /** Target-size category: ordinary links are 44px; primary and icon links are 48px. */
  targetSize?: 'ordinary' | 'primary' | 'icon'
  /** Required when the visible content does not provide an accessible name. */
  ariaLabel?: string
}

withDefaults(defineProps<Props>(), {
  targetSize: 'ordinary',
})
</script>

<template>
  <RouterLink
    :to="to"
    class="base-link-target"
    :class="`base-link-target--${targetSize}`"
    :aria-label="ariaLabel"
  >
    <slot />
  </RouterLink>
</template>

<style scoped lang="scss">
.base-link-target {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-inline-size: var(--control-target-min);
  min-block-size: var(--control-target-min);

  &:focus-visible {
    outline: var(--focus-ring);
    outline-offset: 2px;
  }
}

.base-link-target--primary,
.base-link-target--icon {
  min-inline-size: var(--control-target-mobile);
  min-block-size: var(--control-target-mobile);
}
</style>
