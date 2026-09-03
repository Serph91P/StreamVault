/**
 * Ripple Effect Directive
 * 
 * Adds Material Design-style ripple effect to buttons and clickable elements.
 * 
 * Usage:
 * ```vue
 * <button v-ripple>Click Me</button>
 * <button v-ripple="{ color: '#fff', duration: 600 }">Custom Ripple</button>
 * ```
 */

import type { Directive, DirectiveBinding } from 'vue'

interface RippleOptions {
  color?: string
  duration?: number
  opacity?: number
}

interface RippleElement extends HTMLElement {
  _rippleCleanup?: () => void
}

const defaultOptions: RippleOptions = {
  color: 'rgba(255, 255, 255, 0.3)',
  duration: 600,
  opacity: 0.3
}

const rippleDirective: Directive<RippleElement, RippleOptions | undefined> = {
  mounted(el: RippleElement, binding: DirectiveBinding<RippleOptions | undefined>) {
    // Ensure element has position
    const position = window.getComputedStyle(el).position
    if (position === 'static') {
      el.style.position = 'relative'
    }
    
    // Ensure element clips overflow
    el.style.overflow = 'hidden'
    
    // Merge options
    const options: RippleOptions = {
      ...defaultOptions,
      ...(binding.value || {})
    }
    
    const ripples = new Set<HTMLElement>()
    const animationFrames = new Set<number>()
    const timers = new Set<number>()

    const handler = (event: MouseEvent) => {
      if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return

      const ripple = document.createElement('span')
      const rect = el.getBoundingClientRect()
      const size = Math.max(rect.width, rect.height) * 2
      const keyboardActivation = event.detail === 0
      const clientX = keyboardActivation ? rect.left + rect.width / 2 : event.clientX
      const clientY = keyboardActivation ? rect.top + rect.height / 2 : event.clientY
      const duration = options.duration ?? defaultOptions.duration ?? 600

      ripple.style.position = 'absolute'
      ripple.style.width = `${size}px`
      ripple.style.height = `${size}px`
      ripple.style.left = `${clientX - rect.left - size / 2}px`
      ripple.style.top = `${clientY - rect.top - size / 2}px`
      ripple.style.borderRadius = '50%'
      ripple.style.background = options.color ?? defaultOptions.color ?? 'rgba(255, 255, 255, 0.3)'
      ripple.style.pointerEvents = 'none'
      ripple.style.transform = 'scale(0)'
      ripple.style.opacity = String(options.opacity ?? defaultOptions.opacity ?? 0.3)
      ripple.style.transition = `transform ${duration}ms ease-out, opacity ${duration}ms ease-out`
      ripple.classList.add('ripple-effect-element')

      ripples.add(ripple)
      el.appendChild(ripple)

      let frameId: number | null = null
      frameId = requestAnimationFrame(() => {
        if (frameId !== null) animationFrames.delete(frameId)
        if (!ripples.has(ripple) || !el.isConnected || !ripple.isConnected) return
        ripple.style.transform = 'scale(1)'
        ripple.style.opacity = '0'
      })
      animationFrames.add(frameId)

      const timerId = window.setTimeout(() => {
        timers.delete(timerId)
        ripples.delete(ripple)
        ripple.remove()
      }, duration)
      timers.add(timerId)
    }
    
    // Add event listener
    el.addEventListener('click', handler)
    
    // Store cleanup function
    el._rippleCleanup = () => {
      el.removeEventListener('click', handler)
      animationFrames.forEach(frameId => cancelAnimationFrame(frameId))
      timers.forEach(timerId => clearTimeout(timerId))
      ripples.forEach(ripple => ripple.remove())
      animationFrames.clear()
      timers.clear()
      ripples.clear()
    }
  },
  
  unmounted(el: RippleElement) {
    if (el._rippleCleanup) {
      el._rippleCleanup()
    }
  }
}

export default rippleDirective
