<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="['toast', `toast-${toast.type}`]"
          :role="toast.type === 'error' ? 'alert' : 'status'"
          :aria-live="toast.type === 'error' ? 'assertive' : 'polite'"
          aria-atomic="true"
          @click="removeToast(toast.id)"
        >
          <div class="toast-icon" aria-hidden="true">
            <span v-if="toast.type === 'success'">✓</span>
            <span v-else-if="toast.type === 'error'">✕</span>
            <span v-else-if="toast.type === 'warning'">⚠</span>
            <span v-else-if="toast.type === 'info'">ℹ</span>
          </div>
          <div class="toast-content">
            <p class="toast-message">{{ toast.message }}</p>
          </div>
          <button type="button" class="toast-close" @click.stop="removeToast(toast.id)" aria-label="Meldung schließen">
            ×
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts, remove } = useToast()

function removeToast(id: string) {
  remove(id)
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
@use '@/styles/variables' as v;

.toast-container {
  position: fixed;
  top: v.$spacing-4;
  right: v.$spacing-4;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: v.$spacing-3;
  pointer-events: none;
  
  @include m.respond-below('md') {
    // Mobile: Position at bottom like background jobs panel
    top: auto;
    bottom: v.$spacing-3;
    right: v.$spacing-3;
    left: v.$spacing-3;
  }
}

.toast {
  display: flex;
  align-items: center;
  gap: var(--sv-cmp-feedback-gap);
  padding: var(--sv-cmp-feedback-gap) var(--sv-cmp-feedback-padding);
  min-width: 300px;
  max-width: 500px;
  background: var(--sv-cmp-feedback-background);
  border-radius: v.$border-radius;
  border: 1px solid var(--sv-cmp-feedback-border);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  pointer-events: auto;
  cursor: pointer;
  
  @include m.respond-below('md') {
    min-width: unset;
    max-width: unset;
  }
  

}

.toast-success {
  border-left-color: var(--success-color);
  
  .toast-icon {
    color: var(--success-color);
  }
}

.toast-error {
  border-left-color: var(--danger-color);
  
  .toast-icon {
    color: var(--danger-color);
  }
}

.toast-warning {
  border-left-color: var(--warning-color);
  
  .toast-icon {
    color: var(--warning-color);
  }
}

.toast-info {
  border-left-color: var(--info-color);
  
  .toast-icon {
    color: var(--info-color);
  }
}

.toast-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  font-size: 18px;
  font-weight: bold;
  flex-shrink: 0;
}

.toast-content {
  flex: 1;
  min-width: 0;
}

.toast-message {
  margin: 0;
  color: var(--sv-cmp-feedback-foreground);
  font-size: var(--text-base);
  word-break: break-word;
}

.toast-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--sv-fdn-size-target);
  height: var(--sv-fdn-size-target);
  padding: 0;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  flex-shrink: 0;
  
  &:hover {
    color: var(--text-primary);
  }
  &:focus-visible { outline: 2px solid var(--sv-sem-action-focus); outline-offset: 2px; }
}

/* Toast animations */
.toast-enter-active,
.toast-leave-active {
  transition: var(--transition-base);
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%) scale(0.9);
}

.toast-move {
  transition: var(--transition-transform);
}

@media (prefers-reduced-motion: reduce) {
  .toast-enter-active, .toast-leave-active, .toast-move { transition: none; }
}
</style>
