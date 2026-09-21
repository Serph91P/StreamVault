/**
 * useModal - uniform modal/dialog behaviour:
 *  - body scroll lock while open (preserves scrollY, restores on close)
 *  - ESC closes
 *  - basic focus trap (TAB / SHIFT+TAB cycle within container)
 *  - autofocus first focusable element when opened
 *
 * Multiple stacked modals are supported via a shared lock counter.
 *
 * Usage:
 *   const dialogRef = ref<HTMLElement | null>(null)
 *   const { open, close, isOpen } = useModal(dialogRef, { onClose: () => emit('close') })
 *
 *   <div ref="dialogRef" v-if="isOpen" role="dialog" aria-modal="true">...</div>
 */
import { ref, unref, watch, onBeforeUnmount, type Ref } from 'vue'

export interface UseModalOptions {
  /** Called when the modal should close (ESC, programmatic close, etc.) */
  onClose?: () => void
  /** Disable the ESC-to-close handler. */
  closeOnEscape?: boolean | Ref<boolean>
  /** Focus the first focusable element on open. */
  autoFocus?: boolean
}

let lockCount = 0
let savedScrollY = 0
let savedBodyStyles: { overflow: string; position: string; top: string; width: string } | null = null
interface ModalStackEntry {
  restoreTarget: HTMLElement | null
}

const modalStack: ModalStackEntry[] = []

function lockBody() {
  lockCount += 1
  if (lockCount > 1) return
  savedScrollY = window.scrollY
  savedBodyStyles = {
    overflow: document.body.style.overflow,
    position: document.body.style.position,
    top: document.body.style.top,
    width: document.body.style.width,
  }
  document.body.style.position = 'fixed'
  document.body.style.top = `-${savedScrollY}px`
  document.body.style.width = '100%'
  document.body.style.overflow = 'hidden'
}

function unlockBody() {
  lockCount = Math.max(0, lockCount - 1)
  if (lockCount > 0) return
  if (savedBodyStyles) {
    document.body.style.overflow = savedBodyStyles.overflow
    document.body.style.position = savedBodyStyles.position
    document.body.style.top = savedBodyStyles.top
    document.body.style.width = savedBodyStyles.width
    savedBodyStyles = null
  }
  window.scrollTo(0, savedScrollY)
}

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

function getFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
    .filter((el) => !el.hasAttribute('disabled') && el.offsetParent !== null)
}

export function useModal(
  containerRef: Ref<HTMLElement | null>,
  options: UseModalOptions = {}
) {
  const { onClose, closeOnEscape = true, autoFocus = true } = options
  const isOpen = ref(false)
  const stackEntry: ModalStackEntry = { restoreTarget: null }

  const isTopmost = () => modalStack[modalStack.length - 1] === stackEntry

  const handleKeydown = (event: KeyboardEvent) => {
    if (!isOpen.value || !isTopmost()) return

    if (event.key === 'Escape' && unref(closeOnEscape)) {
      event.preventDefault()
      close()
      return
    }

    if (event.key === 'Tab' && containerRef.value) {
      const focusable = getFocusable(containerRef.value)
      if (focusable.length === 0) {
        event.preventDefault()
        return
      }
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement as HTMLElement | null

      if (event.shiftKey) {
        if (active === first || !containerRef.value.contains(active)) {
          event.preventDefault()
          last.focus()
        }
      } else if (active === last) {
        event.preventDefault()
        first.focus()
      }
    }
  }

  const open = () => {
    if (isOpen.value) return
    isOpen.value = true
    stackEntry.restoreTarget = document.activeElement as HTMLElement | null
    modalStack.push(stackEntry)
    lockBody()
    document.addEventListener('keydown', handleKeydown)
  }

  const close = (notify = true) => {
    if (!isOpen.value) return
    isOpen.value = false
    document.removeEventListener('keydown', handleKeydown)
    const stackIndex = modalStack.lastIndexOf(stackEntry)
    const wasTopmost = stackIndex !== -1 && stackIndex === modalStack.length - 1
    const nextModal = stackIndex === -1 ? undefined : modalStack[stackIndex + 1]
    if (
      nextModal
      && nextModal.restoreTarget
      && containerRef.value?.contains(nextModal.restoreTarget)
    ) {
      nextModal.restoreTarget = stackEntry.restoreTarget
    }
    if (stackIndex !== -1) modalStack.splice(stackIndex, 1)
    unlockBody()
    if (wasTopmost && stackEntry.restoreTarget?.isConnected) {
      stackEntry.restoreTarget.focus()
    }
    stackEntry.restoreTarget = null
    if (notify) onClose?.()
  }

  if (autoFocus) {
    watch(
      () => [isOpen.value, containerRef.value] as const,
      ([open, el]) => {
        if (!open || !el) return
        // wait a tick so the v-if rendered children are in the DOM
        requestAnimationFrame(() => {
          const focusable = getFocusable(el)
          if (focusable.length > 0) focusable[0].focus()
          else el.focus?.()
        })
      },
      { flush: 'post' }
    )
  }

  onBeforeUnmount(() => {
    if (isOpen.value) {
      close(false)
    }
  })

  return { isOpen, open, close }
}
