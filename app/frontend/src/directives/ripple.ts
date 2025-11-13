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

function createRipple(event: MouseEvent, element: HTMLElement, options: RippleOptions) {
  // Create ripple element
  const ripple = document.createElement('span')
  const rect = element.getBoundingClientRect()
  
  // Calculate ripple size (largest dimension * 2)
  const size = Math.max(rect.width, rect.height) * 2
  
  // Calculate ripple position relative to click
  const x = event.clientX - rect.left - size / 2
  const y = event.clientY - rect.top - size / 2
  
  // Style the ripple
  ripple.style.position = 'absolute'
  ripple.style.width = `${size}px`
  ripple.style.height = `${size}px`
  ripple.style.left = `${x}px`
  ripple.style.top = `${y}px`
  ripple.style.borderRadius = '50%'

  // Ensure color is always a valid string
  const color = options.color ?? defaultOptions.color ?? 'rgba(255, 255, 255, 0.3)'
  ripple.style.background = color
  ripple.style.pointerEvents = 'none'
  ripple.style.transform = 'scale(0)'

  // Ensure opacity is always a valid number
  const opacity = options.opacity ?? defaultOptions.opacity ?? 0.3
  ripple.style.opacity = String(opacity)

  // Ensure duration is always a valid number
  const duration = options.duration ?? defaultOptions.duration ?? 600
  ripple.style.transition = `transform ${duration}ms ease-out, opacity ${duration}ms ease-out`
  ripple.classList.add('ripple-effect-element')
  
  // Add ripple to element
  element.appendChild(ripple)
  
  // Trigger animation
  requestAnimationFrame(() => {
    ripple.style.transform = 'scale(1)'
    ripple.style.opacity = '0'
  })
  
  // Remove ripple after animation
  setTimeout(() => {
    ripple.remove()
  }, duration)
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
    
    // Create handler
    const handler = (event: MouseEvent) => {
      createRipple(event, el, options)
      
      // Haptic feedback (if supported)
      if ('vibrate' in navigator && options.duration) {
        navigator.vibrate(10)
      }
    }
    
    // Add event listener
    el.addEventListener('click', handler)
    
    // Store cleanup function
    el._rippleCleanup = () => {
      el.removeEventListener('click', handler)
      // Remove any remaining ripples
      el.querySelectorAll('.ripple-effect-element').forEach(ripple => ripple.remove())
    }
  },
  
  unmounted(el: RippleElement) {
    if (el._rippleCleanup) {
      el._rippleCleanup()
    }
  }
}

export default rippleDirective
