<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

interface Props {
  modelValue: boolean
  /** Optional title rendered in the header (slot 'header' overrides) */
  title?: string
  /** Accessible label when the visible header is custom or omitted */
  ariaLabel?: string
  /** Modal width preset */
  size?: 'sm' | 'md' | 'lg' | 'xl'
  /** Full-screen on mobile (<= md). Defaults to true. */
  fullscreenMobile?: boolean
  /** Click on backdrop closes. Default true. */
  closeOnBackdrop?: boolean
  /** Esc key closes. Default true. */
  closeOnEsc?: boolean
  /** Hide the built-in close button in the header */
  hideClose?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
  fullscreenMobile: true,
  closeOnBackdrop: true,
  closeOnEsc: true,
  hideClose: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'close'): void
}>()

const dialogRef = ref<HTMLElement | null>(null)
const previouslyFocused = ref<HTMLElement | null>(null)

function close() {
  emit('update:modelValue', false)
  emit('close')
}

function onBackdropClick(ev: MouseEvent) {
  if (!props.closeOnBackdrop) return
  if (ev.target === ev.currentTarget) close()
}

function onKeydown(ev: KeyboardEvent) {
  if (ev.key === 'Escape' && props.closeOnEsc) {
    ev.stopPropagation()
    close()
    return
  }
  if (ev.key === 'Tab') {
    trapTabFocus(ev)
  }
}

function trapTabFocus(event: KeyboardEvent) {
  const panel = dialogRef.value
  if (!panel) return
  const focusable = getFocusableElements(panel)
  if (!focusable.length) {
    event.preventDefault()
    return
  }
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
  )
}

const modalClasses = computed(() => [
  'modal',
  props.size === 'lg' && 'modal-lg',
  props.size === 'xl' && 'modal-xl',
  props.fullscreenMobile && 'modal-fullscreen-mobile',
])

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      previouslyFocused.value = (document.activeElement as HTMLElement) || null
      document.body.style.overflow = 'hidden'
      await nextTick()
      dialogRef.value?.focus()
    } else {
      document.body.style.overflow = ''
      previouslyFocused.value?.focus?.()
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="modal-overlay"
        role="presentation"
        @click="onBackdropClick"
        @keydown="onKeydown"
      >
        <div
          ref="dialogRef"
          :class="modalClasses"
          role="dialog"
          aria-modal="true"
          :aria-label="ariaLabel || title || undefined"
          tabindex="-1"
        >
          <div v-if="$slots.header || title || !hideClose" class="modal-header">
            <slot name="header">
              <h2 v-if="title">{{ title }}</h2>
            </slot>
            <button
              v-if="!hideClose"
              type="button"
              class="close-btn"
              aria-label="Close"
              @click="close"
            >
              ×
            </button>
          </div>

          <div class="modal-body">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="modal-footer">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.modal-xl {
  max-width: 1200px;
}

.modal-fullscreen-mobile {
  @include m.respond-below('md') {
    padding-bottom: env(safe-area-inset-bottom, 0px);
    padding-top: env(safe-area-inset-top, 0px);
  }
}

// Vue transition hooks (timings come from tokens via _components.scss
// .modal-enter-active, but the BaseModal also wraps the overlay so we
// add a quick fade for the wrapper here using the design tokens)
.modal-enter-active,
.modal-leave-active {
  transition: opacity v.$duration-200 v.$vue-ease-out;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .modal-enter-active,
  .modal-leave-active {
    transition: none;
  }
}
</style>
