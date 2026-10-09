<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'
import BaseLink from './BaseLink.vue'

interface Props {
  title: string
  subtitle?: string
  icon?: string
  mobileTitle?: string
  mobileIcon?: string
  /** Stable in-app destination for returning from a nested page. */
  backTo?: RouteLocationRaw
  backLabel?: string
}

withDefaults(defineProps<Props>(), {
  backLabel: 'Back',
})
</script>

<template>
  <header class="page-header">
    <div class="page-header-content">
      <div class="page-header-title-group">
        <BaseLink v-if="backTo" :to="backTo" :aria-label="backLabel" class="page-header-back-link">
          <svg aria-hidden="true"><use href="#icon-arrow-left" /></svg>
          <span>{{ backLabel }}</span>
        </BaseLink>
        <!-- Hidden on mobile when the mobile title brings its own icon -->
        <svg v-if="icon" class="page-header-icon" :class="{ 'm-hide': !!mobileIcon }" aria-hidden="true">
          <use :href="`#icon-${icon}`" />
        </svg>
        <div>
          <h1 class="page-header-title-text desktop-title" :class="{ 'm-hide': !!mobileTitle }">{{ title }}</h1>
          <h1 v-if="mobileTitle" class="page-header-title-text mobile-title">
            <svg v-if="mobileIcon" class="page-header-icon" aria-hidden="true">
              <use :href="`#icon-${mobileIcon}`" />
            </svg>
            {{ mobileTitle }}
          </h1>
          <p v-if="subtitle" class="page-header-subtitle">{{ subtitle }}</p>
        </div>
      </div>
      <div v-if="$slots.status || $slots.actions" class="page-header-end">
        <slot name="status" />
        <slot name="actions" />
      </div>
    </div>
  </header>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.page-header {
  margin-bottom: var(--spacing-6);
}

.page-header-content {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-4);
}

.page-header-title-group {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-3);
  min-width: 0;
}

.page-header-back-link {
  flex-shrink: 0;
  gap: var(--spacing-2);
  padding: 0 var(--spacing-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: 600;
  text-decoration: none;

  svg {
    width: 1rem;
    height: 1rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
  }

  &:hover {
    border-color: var(--primary-color);
    color: var(--primary-color);
  }
}

.page-header-icon {
  width: 1.5rem;
  height: 1.5rem;
  flex-shrink: 0;
  margin-top: 0.25rem;
  color: var(--primary-color);

  &.m-hide {
    @include m.respond-below('md') {
      display: none;
    }
  }
}

.page-header-title-text {
  font-size: var(--text-2xl);
  font-weight: 700;
  line-height: 1.25;
  // Page headers globally use a decorative gradient; this semantic title must remain solid for contrast checks.
  background-image: none;
  color: var(--text-primary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--spacing-2);

  .page-header-icon {
    margin-top: 0;
  }
}

.desktop-title {
  display: flex;

  &.m-hide {
    @include m.respond-below('md') {
      display: none;
    }
  }
}

.mobile-title {
  display: none;

  @include m.respond-below('md') {
    display: flex;
  }
}

.page-header-subtitle {
  margin: var(--spacing-1) 0 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}

.page-header-end {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  flex-shrink: 0;
  flex-wrap: wrap;
}
</style>
