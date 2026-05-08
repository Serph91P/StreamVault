/**
 * useModal — uniform modal/dialog behaviour:
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
import { ref, watch, onBeforeUnmount, type Ref } from 'vue'

export interface UseModalOptions {
  /** Called when the modal should close (ESC, programmatic close, etc.) */
  onClose?: () => void
  /** Disable the ESC-to-close handler. */
  closeOnEscape?: boolean
  /** Focus the first focusable element on open. */
  autoFocus?: boolean
}

let lockCount = 0
let savedScrollY = 0
let savedBodyStyles: { overflow: string; position: string; top: string; width: string } | null = null

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
  let previouslyFocused: HTMLElement | null = null

  const handleKeydown = (event: KeyboardEvent) => {
    if (!isOpen.value) return

    if (event.key === 'Escape' && closeOnEscape) {
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
    previouslyFocused = document.activeElement as HTMLElement | null
    lockBody()
    document.addEventListener('keydown', handleKeydown)
  }

  const close = () => {
    if (!isOpen.value) return
    isOpen.value = false
    document.removeEventListener('keydown', handleKeydown)
    unlockBody()
    if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
      previouslyFocused.focus()
    }
    previouslyFocused = null
    onClose?.()
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
      document.removeEventListener('keydown', handleKeydown)
      unlockBody()
    }
  })

  return { isOpen, open, close }
}
