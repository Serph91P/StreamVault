<script setup lang="ts">
import { ref, toRef, watch } from 'vue'
import { useModal } from '@/composables/useModal'

interface Props {
  modelValue: boolean
  title?: string
  ariaLabel?: string
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

const modal = useModal(sheetRef, {
  closeOnEscape: toRef(props, 'closeOnEsc'),
  onClose: () => {
    emit('update:modelValue', false)
    emit('close')
  },
})

function close() {
  modal.close()
}

function onBackdropClick(event: MouseEvent) {
  if (props.closeOnBackdrop && event.target === event.currentTarget) {
    close()
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) modal.open()
    else modal.close(false)
  },
  { immediate: true },
)
</script>

<template>
  <Teleport to="body">
    <Transition :name="`sheet-${side}`">
      <div
        v-if="modelValue"
        class="sheet-backdrop"
        role="presentation"
        @click="onBackdropClick"
      >
        <aside
          ref="sheetRef"
          class="base-sheet"
          :class="`base-sheet-${side}`"
          role="dialog"
          aria-modal="true"
          :aria-label="ariaLabel || title || undefined"
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
  max-height: calc(100dvh - env(safe-area-inset-top, 0px));
  background: var(--sv-cmp-overlay-background);
  border: 1px solid var(--sv-cmp-overlay-border);
  box-shadow: var(--sv-cmp-overlay-shadow);
  color: var(--sv-sem-text-primary);
  outline: none;
}

.base-sheet-bottom {
  width: 100%;
  margin-top: auto;
  border-radius: var(--radius-2xl) var(--radius-2xl) 0 0;
  padding-bottom: env(safe-area-inset-bottom, 0px);
}

.base-sheet-right,
.base-sheet-left {
  width: min(28rem, 100vw);
  height: 100%;
}

.base-sheet-right {
  margin-left: auto;
  padding-right: env(safe-area-inset-right, 0px);
}

.base-sheet-left {
  margin-right: auto;
  padding-left: env(safe-area-inset-left, 0px);
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
  border-bottom: 1px solid var(--sv-cmp-overlay-border);
}

.base-sheet-footer {
  border-top: 1px solid var(--sv-cmp-overlay-border);
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
  min-width: var(--sv-fdn-size-target);
  min-height: var(--sv-fdn-size-target);
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--sv-sem-text-secondary);

  &:focus-visible {
    outline: 2px solid var(--sv-sem-action-focus);
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
