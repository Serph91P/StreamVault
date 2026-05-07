<script setup lang="ts">
import { computed } from 'vue'

type Variant =
  | 'primary'
  | 'secondary'
  | 'success'
  | 'danger'
  | 'warning'
  | 'info'
  | 'outline'
  | 'outline-primary'
  | 'outline-danger'

interface Props {
  /** Visual style — maps to .btn-{variant} class on the design-system .btn base */
  variant?: Variant
  /** Size — maps to .btn-sm / .btn-lg, default is medium */
  size?: 'sm' | 'md' | 'lg'
  /** Native button type. Defaults to 'button' to avoid accidental form submits. */
  type?: 'button' | 'submit' | 'reset'
  disabled?: boolean
  /** Show a spinner and disable interaction */
  loading?: boolean
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

const emit = defineEmits<{
  (e: 'click', ev: MouseEvent): void
}>()

const classes = computed(() => [
  'btn',
  `btn-${props.variant}`,
  props.size === 'sm' && 'btn-sm',
  props.size === 'lg' && 'btn-lg',
  props.block && 'btn-block',
  props.loading && 'is-loading',
])

const isDisabled = computed(() => props.disabled || props.loading)

function onClick(ev: MouseEvent) {
  if (isDisabled.value) {
    ev.preventDefault()
    ev.stopPropagation()
    return
  }
  emit('click', ev)
}
</script>

<template>
  <button
    :type="type"
    :class="classes"
    :disabled="isDisabled"
    :aria-busy="loading || undefined"
    :aria-label="ariaLabel"
    @click="onClick"
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
