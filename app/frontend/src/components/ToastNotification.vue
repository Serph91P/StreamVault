<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast" tag="div">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="['toast', `toast-${toast.type}`]"
          @click="removeToast(toast.id)"
        >
          <div class="toast-icon">
            <SvgIcon :name="getToastIcon(toast.type)" />
          </div>
          <div class="toast-content">
            <div class="toast-title">{{ toast.title }}</div>
            <div class="toast-message">{{ toast.message }}</div>
          </div>
          <button @click.stop="removeToast(toast.id)" class="toast-close">
            <SvgIcon name="x" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import SvgIcon from '@/components/icons/SvgIcon.vue'
import { ref, onMounted, onUnmounted } from 'vue'
import { useRealtimeStore } from '@/stores/realtime'
import type { RealtimeEvent } from '@/types/events'

interface Toast {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message: string
  duration: number
  timestamp: number
}

const toasts = ref<Toast[]>([])
const realtime = useRealtimeStore()
const realtimeUnsubs: Array<() => void> = []

// Maximum number of toasts to show at once
const MAX_TOASTS = 5

// Auto-remove timer refs
const timers = new Map<string, number>()

const getToastIcon = (type: string): string => {
  switch (type) {
    case 'success':
      return 'check-circle'
    case 'error':
      return 'alert-circle'
    case 'warning':
      return 'alert-triangle'
    case 'info':
      return 'info'
    default:
      return 'bell'
  }
}

const addToast = (toast: Omit<Toast, 'id' | 'timestamp'>): void => {
  const id = `toast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  const newToast: Toast = {
    ...toast,
    id,
    timestamp: Date.now()
  }

  // Add to the beginning of the array
  toasts.value.unshift(newToast)

  // Limit the number of toasts
  if (toasts.value.length > MAX_TOASTS) {
    const removedToast = toasts.value.pop()
    if (removedToast) {
      clearTimeout(timers.get(removedToast.id))
      timers.delete(removedToast.id)
    }
  }

  // Set auto-remove timer
  const timer = window.setTimeout(() => {
    removeToast(id)
  }, toast.duration)
  
  timers.set(id, timer)
}

const removeToast = (id: string): void => {
  const index = toasts.value.findIndex(t => t.id === id)
  if (index > -1) {
    toasts.value.splice(index, 1)
  }
  
  // Clear timer
  const timer = timers.get(id)
  if (timer) {
    clearTimeout(timer)
    timers.delete(id)
  }
}

const processToastMessage = (message: RealtimeEvent<string>): void => {
  if (message.data) {
    const { toast_type, title, message: msg, duration = 5000 } = message.data
    
    addToast({
      type: toast_type as Toast['type'],
      title,
      message: msg,
      duration
    })
  }
}

onMounted(() => {
  realtimeUnsubs.push(realtime.onEvent('toast_notification', processToastMessage))
})

onUnmounted(() => {
  realtimeUnsubs.forEach((fn) => fn())
  timers.forEach(timer => clearTimeout(timer))
  timers.clear()
})

// Expose addToast for manual usage
defineExpose({
  addToast,
  removeToast
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
/* Responsive - Use SCSS mixins for breakpoints */

.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  pointer-events: none;
  max-width: 400px;
  width: 100%;
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  margin-bottom: 12px;
  border-radius: var(--radius-lg);
  box-shadow: var(--glass-shadow-md);
  cursor: pointer;
  pointer-events: auto;
  backdrop-filter: blur(var(--glass-blur-md));
  -webkit-backdrop-filter: blur(var(--glass-blur-md));
  border: 1px solid transparent;
  transition: var(--transition-base);
  max-width: 100%;
  word-wrap: break-word;
}

.toast:hover {
  transform: translateX(-4px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
}

.toast-success {
  background: rgba(34, 197, 94, 0.95);
  color: white;
  border-color: rgba(34, 197, 94, 0.3);
}

.toast-error {
  background: rgba(239, 68, 68, 0.95);
  color: white;
  border-color: rgba(239, 68, 68, 0.3);
}

.toast-warning {
  background: rgba(245, 158, 11, 0.95);
  color: white;
  border-color: rgba(245, 158, 11, 0.3);
}

.toast-info {
  background: rgba(59, 130, 246, 0.95);
  color: white;
  border-color: rgba(59, 130, 246, 0.3);
}

.toast-icon {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  margin-top: 2px;
}

.toast-content {
  flex: 1;
  min-width: 0;
}

.toast-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
  line-height: 1.2;
}

.toast-message {
  font-size: 13px;
  opacity: 0.9;
  line-height: 1.4;
  word-break: break-word;
}

.toast-close {
  flex-shrink: 0;
  background: none;
  border: none;
  color: currentColor;
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  opacity: 0.7;
  transition: var(--transition-opacity);
  font-size: 12px;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.toast-close:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.1);
}

/* Toast animations */
.toast-enter-active {
  transition: all var(--duration-400) var(--ease-bounce);
}

.toast-leave-active {
  transition: var(--transition-base);
}

.toast-enter-from {
  transform: translateX(100%) scale(0.8);
  opacity: 0;
}

.toast-leave-to {
  transform: translateX(100%) scale(0.8);
  opacity: 0;
}

.toast-move {
  transition: var(--transition-transform);
}

/* Mobile responsive */
@include m.respond-below('md') {  // < 768px
  .toast-container {
    top: 10px;
    right: 10px;
    left: 10px;
    max-width: none;
  }
  
  .toast {
    padding: 14px;
    margin-bottom: 10px;
    font-size: 14px;
  }
  
  .toast-title {
    font-size: 13px;
  }
  
  .toast-message {
    font-size: 12px;
  }
  
  .toast-icon {
    width: 20px;
    height: 20px;
    font-size: 14px;
  }
  
  .toast-close {
    width: 20px;
    height: 20px;
    font-size: 10px;
  }
}

/* Small mobile screens */
@include m.respond-below('xs') {  // < 480px
  .toast-container {
    top: 8px;
    right: 8px;
    left: 8px;
  }
  
  .toast {
    padding: 12px;
    margin-bottom: 8px;
  }
}

/* Reduce motion for accessibility */
@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active,
  .toast-move {
    transition: none;
  }
  
  .toast:hover {
    transform: none;
  }
}
</style>
