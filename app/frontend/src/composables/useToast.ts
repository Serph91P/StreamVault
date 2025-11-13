import { ref, readonly } from 'vue'
import { UI } from '@/config/constants'

/**
 * Toast Notification System
 * 
 * Provides user feedback for:
 * - Success: Settings saved, actions completed
 * - Error: API failures, validation errors
 * - Warning: Non-critical issues
 * - Info: Status updates, informational messages
 * 
 * Usage:
 * ```typescript
 * import { useToast } from '@/composables/useToast'
 * 
 * const toast = useToast()
 * 
 * toast.success('Settings saved successfully')
 * toast.error('Failed to save settings')
 * toast.warning('Connection unstable')
 * toast.info('Notification sent')
 * ```
 */

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  type: ToastType
  message: string
  duration: number
  createdAt: number
}

// Global toast state (singleton)
const toasts = ref<Toast[]>([])

export function useToast() {
  /**
   * Show a toast notification
   * 
   * @param message - Message to display
   * @param type - Toast type (success, error, warning, info)
   * @param duration - Duration in milliseconds (default from UI.TOAST_DURATION_MS)
   */
  function show(message: string, type: ToastType, duration: number = UI.TOAST_DURATION_MS) {
    const id = crypto.randomUUID()
    const createdAt = Date.now()
    
    toasts.value.push({
      id,
      type,
      message,
      duration,
      createdAt
    })
    
    // Auto-dismiss after duration
    setTimeout(() => {
      remove(id)
    }, duration)
  }
  
  /**
   * Remove a toast by ID
   */
  function remove(id: string) {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index !== -1) {
      toasts.value.splice(index, 1)
    }
  }
  
  /**
   * Clear all toasts
   */
  function clear() {
    toasts.value = []
  }
  
  /**
   * Show success toast (green)
   */
  function success(message: string, duration: number = UI.TOAST_DURATION_MS) {
    show(message, 'success', duration)
  }
  
  /**
   * Show error toast (red)
   */
  function error(message: string, duration: number = UI.TOAST_DURATION_MS) {
    show(message, 'error', duration)
  }
  
  /**
   * Show warning toast (yellow)
   */
  function warning(message: string, duration: number = UI.TOAST_DURATION_MS) {
    show(message, 'warning', duration)
  }
  
  /**
   * Show info toast (blue)
   */
  function info(message: string, duration: number = UI.TOAST_DURATION_MS) {
    show(message, 'info', duration)
  }
  
  return {
    toasts: readonly(toasts),
    show,
    remove,
    clear,
    success,
    error,
    warning,
    info
  }
}
