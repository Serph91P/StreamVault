<script setup lang="ts">
import { computed } from 'vue'

type Variant =
  | 'primary'
  | 'secondary'
  | 'accent'
  | 'success'
  | 'danger'
  | 'delete'
  | 'warning'
  | 'info'
  | 'outline'
  | 'outline-primary'
  | 'outline-danger'
  | 'ghost'
  | 'link'
  | 'text'

interface Props {
  /** Visual style maps to .btn-{variant} class on the design-system .btn base */
  variant?: Variant
  /** Size maps to .btn-sm / .btn-lg, default is medium */
  size?: 'sm' | 'md' | 'lg'
  /** Native button type. Defaults to 'button' to avoid accidental form submits. */
  type?: 'button' | 'submit' | 'reset'
  disabled?: boolean
  /** Show a spinner and disable interaction */
  loading?: boolean
  /** Accessible label while the loading spinner is shown */
  loadingLabel?: string
  /** Stretch to fill its container (width: 100%) */
  block?: boolean
  /** Optional ARIA label override (recommended for icon-only buttons) */
  ariaLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  type: 'button',
  disabled: false,
  loading: false,
  block: false,
})

const isDisabled = computed(() => props.disabled || props.loading)
const accessibleLabel = computed(() => (props.loading ? props.loadingLabel || props.ariaLabel : props.ariaLabel))
const classes = computed(() => [
  'btn',
  'base-button-target',
  props.variant === 'primary' ? 'base-button-target--primary' : 'base-button-target--ordinary',
  `btn-${props.variant}`,
  props.size === 'sm' && 'btn-sm',
  props.size === 'lg' && 'btn-lg',
  props.block && 'btn-block',
  props.loading && 'is-loading',
])
</script>

<template>
  <button
    :type="type"
    :class="classes"
    :disabled="isDisabled"
    :aria-busy="loading || undefined"
    :aria-label="accessibleLabel"
  >
    <span class="btn-content" :class="{ 'is-hidden': loading }">
      <slot />
    </span>
    <span v-if="loading" class="btn-loader-overlay" aria-hidden="true">
      <span class="loader" />
    </span>
  </button>
</template>

<style scoped lang="scss">
// All visual styles come from src/styles/_components.scss .btn
// Only layout helpers that don't exist there live here.
.base-button-target {
  min-height: var(--sv-cmp-button-height);
  min-inline-size: var(--sv-cmp-button-height);
  transition:
    color var(--transition-fast),
    background-color var(--transition-fast),
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    transform var(--transition-fast);

  &:focus-visible {
    outline: 2px solid var(--sv-cmp-button-focus);
    outline-offset: 2px;
  }
}

// Ordinary controls use the documented 44px target. Primary actions reserve 48px.
.base-button-target--ordinary {
  min-height: var(--sv-cmp-button-height);
  min-inline-size: var(--sv-cmp-button-height);
}

.base-button-target--primary {
  min-height: var(--sv-cmp-button-height-primary);
  min-inline-size: var(--sv-cmp-button-height-primary);
}

.base-button-target:disabled {
  color: var(--sv-cmp-button-disabled-foreground);
  background: var(--sv-cmp-button-disabled-background);
}

// Keep the outline affordance after the global button reset has been applied.
.btn-outline {
  border: 2px solid currentColor;
}

.btn-block {
  width: 100%;
}

// Loading-state without layout shift:
// - Keep slot content rendered (visibility: hidden) so the button keeps its width.
// - Overlay the spinner absolutely centered.
:deep(.btn).is-loading,
.btn.is-loading {
  position: relative;
}

.btn-content {
  display: inline-flex;
  align-items: center;
  gap: inherit;
  color: inherit;
  background: inherit;

  &.is-hidden {
    visibility: hidden;
  }
}

.btn-loader-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
</style>
