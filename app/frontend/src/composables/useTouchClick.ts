/**
 * useTouchClick — prevents accidental clicks on touch devices when the user
 * is actually scrolling/swiping over a clickable element.
 *
 * Pattern extracted from StreamerCard.vue. Use on any clickable element that
 * lives inside a scrollable list/container so a vertical/horizontal pan does
 * not get interpreted as a tap.
 *
 * Usage:
 *   const { onClick, touchHandlers } = useTouchClick(() => router.push(...))
 *
 *   <div :="touchHandlers" @click="onClick">...</div>
 *
 * The exposed touchHandlers map exists so a template can spread it via
 * v-bind. Most templates will just wire each handler explicitly:
 *
 *   <div
 *     @click="onClick"
 *     @touchstart.passive="onTouchStart"
 *     @touchmove.passive="onTouchMove"
 *   />
 */
import { ref } from 'vue'

export interface UseTouchClickOptions {
  /** Pixels of pointer movement before a touch is treated as a scroll. */
  threshold?: number
}

export function useTouchClick<E extends Event = MouseEvent>(
  callback: (event: E) => void,
  options: UseTouchClickOptions = {}
) {
  const threshold = options.threshold ?? 10

  const isTouchScrolling = ref(false)
  const startX = ref(0)
  const startY = ref(0)

  const onTouchStart = (event: TouchEvent) => {
    const t = event.touches[0]
    if (!t) return
    startX.value = t.clientX
    startY.value = t.clientY
    isTouchScrolling.value = false
  }

  const onTouchMove = (event: TouchEvent) => {
    const t = event.touches[0]
    if (!t) return
    const dx = Math.abs(t.clientX - startX.value)
    const dy = Math.abs(t.clientY - startY.value)
    if (dx > threshold || dy > threshold) {
      isTouchScrolling.value = true
    }
  }

  const onClick = (event: E) => {
    if (isTouchScrolling.value) {
      isTouchScrolling.value = false
      return
    }
    callback(event)
  }

  return {
    isTouchScrolling,
    onTouchStart,
    onTouchMove,
    onClick,
    /** Spread on the element for convenience. */
    touchHandlers: {
      onTouchstartPassive: onTouchStart,
      onTouchmovePassive: onTouchMove,
    },
  }
}
