<script setup lang="ts">
import { computed, useId, useSlots } from 'vue'

interface Props {
  tag?: string
  tone?: 'plain' | 'glass' | 'strong'
  padded?: boolean
  padding?: 'sm' | 'md' | 'lg'
  labelledBy?: string
  describedBy?: string
}

const props = withDefaults(defineProps<Props>(), {
  tag: 'section',
  tone: 'glass',
  padded: true,
  padding: 'md',
})

const slots = useSlots()
const generatedTitleId = useId()
const titleId = computed(() => props.labelledBy || (slots.title ? generatedTitleId : undefined))
const paddingClass = computed(() => (props.padded ? `base-panel-padding-${props.padding}` : 'base-panel-padding-none'))
</script>

<template>
  <component
    :is="tag"
    class="base-panel"
    :class="[
      `base-panel-${tone}`,
      paddingClass,
    ]"
    :aria-labelledby="titleId"
    :aria-describedby="describedBy"
  >
    <header v-if="$slots.header || $slots.title || $slots.actions" class="base-panel-header">
      <div class="base-panel-heading">
        <slot name="header">
          <h2 v-if="$slots.title" :id="titleId" class="base-panel-title">
            <slot name="title" />
          </h2>
          <p v-if="$slots.description" class="base-panel-description">
            <slot name="description" />
          </p>
        </slot>
      </div>
      <div v-if="$slots.actions" class="base-panel-actions">
        <slot name="actions" />
      </div>
    </header>

    <div class="base-panel-body">
      <slot />
    </div>

    <footer v-if="$slots.footer" class="base-panel-footer">
      <slot name="footer" />
    </footer>
  </component>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.base-panel {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: transparent;
}

.base-panel-glass {
  background: var(--glass-bg-subtle, var(--background-card));
  border-color: var(--glass-border, var(--border-color));
  backdrop-filter: blur(var(--glass-blur-sm, 8px));
}

.base-panel-strong {
  background: var(--glass-bg, var(--background-card));
  border-color: var(--glass-border, var(--border-color));
  box-shadow: var(--glass-shadow-sm, 0 4px 16px rgba(0, 0, 0, 0.18));
}

.base-panel-padding-none {
  padding: 0;
}

.base-panel-padding-sm {
  padding: var(--spacing-4);
}

.base-panel-padding-md {
  padding: var(--spacing-5);
}

.base-panel-padding-lg {
  padding: var(--spacing-6);
}

.base-panel-header,
.base-panel-footer {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-4);
}

.base-panel-header {
  margin-bottom: var(--spacing-4);
}

.base-panel-footer {
  margin-top: var(--spacing-4);
  padding-top: var(--spacing-4);
  border-top: 1px solid var(--border-color);
}

.base-panel-title {
  margin: 0;
  color: var(--text-primary);
  font-size: v.$text-lg;
  font-weight: v.$font-semibold;
}

.base-panel-description {
  margin: var(--spacing-1) 0 0;
  color: var(--text-secondary);
  font-size: v.$text-sm;
  line-height: v.$leading-relaxed;
}

.base-panel-actions {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--spacing-2);
}

.base-panel-body,
.base-panel-heading {
  min-width: 0;
}

@media (max-width: 767px) {
  .base-panel-padding-sm,
  .base-panel-padding-md,
  .base-panel-padding-lg {
    padding: var(--spacing-4);
  }

  .base-panel-header,
  .base-panel-footer {
    flex-direction: column;
  }
}
</style>
