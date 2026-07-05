<script setup lang="ts">
interface Props {
  title: string
  subtitle?: string
  icon?: string
  mobileTitle?: string
  mobileIcon?: string
}

withDefaults(defineProps<Props>(), {})
</script>

<template>
  <header class="page-header">
    <div class="page-header-content">
      <div class="page-header-title-group">
        <svg v-if="icon" class="page-header-icon" aria-hidden="true">
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

.page-header-icon {
  width: 1.5rem;
  height: 1.5rem;
  flex-shrink: 0;
  margin-top: 0.25rem;
  color: var(--primary-color);
}

.page-header-title-text {
  font-size: var(--text-2xl);
  font-weight: 700;
  line-height: 1.25;
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
