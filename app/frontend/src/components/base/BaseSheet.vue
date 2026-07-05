<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

interface Props {
  modelValue: boolean
  title?: string
  side?: 'bottom' | 'right' | 'left'
  closeOnBackdrop?: boolean
  closeOnEsc?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  side: 'bottom',
  closeOnBackdrop: true,
  closeOnEsc: true,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'close'): void
}>()

const sheetRef = ref<HTMLElement | null>(null)
const previouslyFocused = ref<HTMLElement | null>(null)

function close() {
  emit('update:modelValue', false)
  emit('close')
}

function onBackdropClick(event: MouseEvent) {
  if (props.closeOnBackdrop && event.target === event.currentTarget) {
    close()
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.closeOnEsc) {
    event.stopPropagation()
    close()
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      previouslyFocused.value = (document.activeElement as HTMLElement) || null
      document.body.style.overflow = 'hidden'
      await nextTick()
      sheetRef.value?.focus()
    } else {
      document.body.style.overflow = ''
      previouslyFocused.value?.focus?.()
    }
  },
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition :name="`sheet-${side}`">
      <div
        v-if="modelValue"
        class="sheet-backdrop"
        role="presentation"
        @click="onBackdropClick"
        @keydown="onKeydown"
      >
        <aside
          ref="sheetRef"
          class="base-sheet"
          :class="`base-sheet-${side}`"
          role="dialog"
          aria-modal="true"
          :aria-label="title || undefined"
          tabindex="-1"
        >
          <header v-if="$slots.header || title || $slots.actions" class="base-sheet-header">
            <slot name="header">
              <h2 v-if="title" class="base-sheet-title">{{ title }}</h2>
            </slot>
            <div class="base-sheet-actions">
              <slot name="actions" />
              <button type="button" class="base-sheet-close" aria-label="Close" @click="close">
                ×
              </button>
            </div>
          </header>

          <div class="base-sheet-body">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="base-sheet-footer">
            <slot name="footer" />
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.sheet-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  background: rgba(0, 0, 0, 0.48);
}

.base-sheet {
  display: flex;
  flex-direction: column;
  max-height: calc(100dvh - var(--safe-area-inset-top, 0px));
  background: var(--glass-bg-strong, var(--background-card));
  border: 1px solid var(--glass-border, var(--border-color));
  box-shadow: var(--glass-shadow-lg, 0 16px 48px rgba(0, 0, 0, 0.3));
  color: var(--text-primary);
  outline: none;
}

.base-sheet-bottom {
  width: 100%;
  margin-top: auto;
  border-radius: var(--radius-2xl) var(--radius-2xl) 0 0;
  padding-bottom: var(--safe-area-inset-bottom, 0px);
}

.base-sheet-right,
.base-sheet-left {
  width: min(28rem, 100vw);
  height: 100%;
}

.base-sheet-right {
  margin-left: auto;
}

.base-sheet-left {
  margin-right: auto;
}

.base-sheet-header,
.base-sheet-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-3);
  padding: var(--spacing-4) var(--spacing-5);
}

.base-sheet-header {
  border-bottom: 1px solid var(--border-color);
}

.base-sheet-footer {
  border-top: 1px solid var(--border-color);
}

.base-sheet-title {
  margin: 0;
  font-size: v.$text-lg;
  font-weight: v.$font-semibold;
}

.base-sheet-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
}

.base-sheet-close {
  min-width: 44px;
  min-height: 44px;
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--text-secondary);

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

.base-sheet-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: var(--spacing-5);
}

.sheet-bottom-enter-active,
.sheet-bottom-leave-active,
.sheet-right-enter-active,
.sheet-right-leave-active,
.sheet-left-enter-active,
.sheet-left-leave-active {
  transition: opacity v.$duration-200 v.$ease-out;
}

.sheet-bottom-enter-active .base-sheet,
.sheet-bottom-leave-active .base-sheet,
.sheet-right-enter-active .base-sheet,
.sheet-right-leave-active .base-sheet,
.sheet-left-enter-active .base-sheet,
.sheet-left-leave-active .base-sheet {
  transition: transform v.$duration-200 v.$ease-out;
}

.sheet-bottom-enter-from,
.sheet-bottom-leave-to,
.sheet-right-enter-from,
.sheet-right-leave-to,
.sheet-left-enter-from,
.sheet-left-leave-to {
  opacity: 0;
}

.sheet-bottom-enter-from .base-sheet,
.sheet-bottom-leave-to .base-sheet {
  transform: translateY(100%);
}

.sheet-right-enter-from .base-sheet,
.sheet-right-leave-to .base-sheet {
  transform: translateX(100%);
}

.sheet-left-enter-from .base-sheet,
.sheet-left-leave-to .base-sheet {
  transform: translateX(-100%);
}

@media (prefers-reduced-motion: reduce) {
  .sheet-bottom-enter-active,
  .sheet-bottom-leave-active,
  .sheet-right-enter-active,
  .sheet-right-leave-active,
  .sheet-left-enter-active,
  .sheet-left-leave-active,
  .sheet-bottom-enter-active .base-sheet,
  .sheet-bottom-leave-active .base-sheet,
  .sheet-right-enter-active .base-sheet,
  .sheet-right-leave-active .base-sheet,
  .sheet-left-enter-active .base-sheet,
  .sheet-left-leave-active .base-sheet {
    transition: none;
  }
}
</style>
