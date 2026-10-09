<script setup lang="ts">
import { computed, useId, useSlots } from 'vue'

export type SurfaceVariant = 'subtle' | 'medium' | 'strong'
export type PaddingSize = 'sm' | 'md' | 'lg' | 'xl'

interface Props {
  tag?: string
  variant?: SurfaceVariant
  padding?: boolean | PaddingSize
  elevated?: boolean
  hoverable?: boolean
  clickable?: boolean
  disabled?: boolean
  loading?: boolean
  labelledBy?: string
  describedBy?: string
}

const props = withDefaults(defineProps<Props>(), {
  tag: 'section',
  variant: 'medium',
  padding: true,
  elevated: false,
  hoverable: false,
  clickable: false,
  disabled: false,
  loading: false,
})

const emit = defineEmits<{
  click: [event: MouseEvent | KeyboardEvent]
}>()

const slots = useSlots()
const generatedTitleId = useId()
const titleId = computed(() => props.labelledBy || (slots.title ? generatedTitleId : undefined))
const isDisabled = computed(() => props.disabled || props.loading)
const role = computed(() => props.clickable ? 'button' : undefined)
const tabindex = computed(() => props.clickable && !isDisabled.value ? 0 : undefined)
const paddingClass = computed(() => props.padding === false ? undefined : `surface-card-padding-${props.padding === true ? 'md' : props.padding}`)

function activate(event: MouseEvent | KeyboardEvent) {
  if (props.clickable && !isDisabled.value) emit('click', event)
}
</script>

<template>
  <component
    :is="tag"
    class="surface-card"
    :class="[
      `surface-card-${variant}`,
      paddingClass,
      {
        'surface-card-elevated': elevated,
        'surface-card-hoverable': hoverable,
        'surface-card-clickable': clickable,
        'surface-card-disabled': isDisabled,
        'surface-card-loading': loading,
      },
    ]"
    :role="role"
    :tabindex="tabindex"
    :aria-labelledby="titleId"
    :aria-describedby="describedBy"
    :aria-disabled="isDisabled || undefined"
    :aria-busy="loading || undefined"
    @click="activate"
    @keydown.enter.prevent="activate"
    @keydown.space.prevent="activate"
  >
    <header v-if="$slots.header || $slots.title || $slots.actions" class="surface-card-header">
      <div class="surface-card-heading">
        <slot name="header">
          <h2 v-if="$slots.title" :id="titleId" class="surface-card-title"><slot name="title" /></h2>
          <p v-if="$slots.description" class="surface-card-description"><slot name="description" /></p>
        </slot>
      </div>
      <div v-if="$slots.actions" class="surface-card-actions"><slot name="actions" /></div>
    </header>

    <div class="surface-card-body"><slot /></div>

    <footer v-if="$slots.footer" class="surface-card-footer"><slot name="footer" /></footer>

    <div v-if="loading" class="surface-card-loader-overlay" aria-hidden="true"><span class="loader" /></div>
  </component>
</template>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
@use '@/styles/variables' as v;

.surface-card {
  position: relative;
  min-width: 0;
  overflow: hidden;
  padding: 0;
  background: var(--sv-cmp-panel-background);
  border: 1px solid var(--sv-cmp-panel-border);
  border-radius: var(--radius-xl);
  box-shadow: none;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;

  &.surface-card-subtle { background: var(--sv-sem-surface-raised); }
  &.surface-card-strong { border-color: var(--sv-sem-border-strong); }
  &.surface-card-elevated { border-color: var(--sv-sem-border-strong); }
  &.surface-card-clickable { cursor: pointer; }
  &.surface-card-disabled { cursor: not-allowed; opacity: 0.62; }

  &.surface-card-hoverable {
    transition: border-color v.$duration-200 v.$ease-out, background-color v.$duration-200 v.$ease-out;

    &:hover:not(.surface-card-disabled):not(.surface-card-loading) {
      border-color: var(--sv-sem-border-strong);
      background: var(--sv-sem-surface-raised);
    }
  }

  &.surface-card-clickable:focus-visible {
    outline: 2px solid var(--sv-cmp-button-focus);
    outline-offset: 3px;
  }
}

.surface-card-header,
.surface-card-footer {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-4);
}

.surface-card-header { margin-bottom: var(--spacing-4); }
.surface-card-footer { margin-top: var(--spacing-4); padding-top: var(--spacing-4); border-top: 1px solid var(--sv-cmp-panel-border); }
.surface-card-heading,
.surface-card-body { min-width: 0; }
.surface-card-title { margin: 0; color: var(--text-primary); font-size: v.$text-xl; font-weight: v.$font-semibold; line-height: v.$leading-tight; }
.surface-card-description { margin: var(--spacing-1) 0 0; color: var(--text-secondary); font-size: v.$text-sm; line-height: v.$leading-relaxed; }
.surface-card-actions { display: inline-flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--spacing-2); }

.surface-card-padding-sm { padding: var(--spacing-4); }
.surface-card-padding-md { padding: var(--spacing-5); }
.surface-card-padding-lg { padding: var(--spacing-6); }
.surface-card-padding-xl { padding: var(--spacing-8); }
.surface-card-padding-sm .surface-card-header,
.surface-card-padding-md .surface-card-header,
.surface-card-padding-lg .surface-card-header,
.surface-card-padding-xl .surface-card-header { margin-top: 0; }

.surface-card-loader-overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--sv-cmp-panel-background) 86%, transparent);
  pointer-events: none;
}

@include m.respond-below('md') {
  .surface-card-padding-lg { padding: var(--spacing-4); }
  .surface-card-padding-xl { padding: var(--spacing-6); }
  .surface-card-header,
  .surface-card-footer { flex-direction: column; }
}

@media (prefers-reduced-motion: reduce) {
  .surface-card.surface-card-hoverable { transition: none; }
  .surface-card.surface-card-hoverable:hover { transform: none; }
}
</style>
