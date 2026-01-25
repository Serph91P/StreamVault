<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="['toast', `toast-${toast.type}`]"
          @click="removeToast(toast.id)"
        >
          <div class="toast-icon">
            <span v-if="toast.type === 'success'">✓</span>
            <span v-else-if="toast.type === 'error'">✕</span>
            <span v-else-if="toast.type === 'warning'">⚠</span>
            <span v-else-if="toast.type === 'info'">ℹ</span>
          </div>
          <div class="toast-content">
            <p class="toast-message">{{ toast.message }}</p>
          </div>
          <button class="toast-close" @click.stop="removeToast(toast.id)" aria-label="Close">
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
  gap: v.$spacing-3;
  padding: v.$spacing-3 v.$spacing-4;
  min-width: 300px;
  max-width: 500px;
  background: var(--background-card);
  border-radius: v.$border-radius;
  border-left: 4px solid;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  pointer-events: auto;
  cursor: pointer;
  
  @include m.respond-below('md') {
    min-width: unset;
    max-width: unset;
  }
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
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
  color: var(--text-primary);
  font-size: var(--text-base);
  word-break: break-word;
}

.toast-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
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
}

/* Toast animations */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
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
  transition: transform 0.3s ease;
}
</style>
