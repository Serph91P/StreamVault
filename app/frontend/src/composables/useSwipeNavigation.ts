import { onMounted, onUnmounted } from 'vue'
import { useSwipe } from '@vueuse/core'
import { useNavigation } from './useNavigation'

export function useSwipeNavigation() {
  const { navigateNext, navigatePrevious, isMobile } = useNavigation()
  
  let swipeTarget: HTMLElement | null = null
  
  const initSwipe = () => {
    if (!isMobile.value) return
    
    // Target the main content area (not the bottom nav itself)
    swipeTarget = document.querySelector('main') || document.body
    
    const { direction, lengthX } = useSwipe(swipeTarget, {
      threshold: 50, // Minimum swipe distance in pixels
      onSwipeEnd(e: TouchEvent, direction: string) {
        // Only trigger on horizontal swipes
        if (Math.abs(lengthX.value) < 50) return
        
        // Add haptic feedback
        if ('vibrate' in navigator) {
          navigator.vibrate(10)
        }
        
        if (direction === 'left') {
          navigateNext()
        } else if (direction === 'right') {
          navigatePrevious()
        }
      }
    })
  }
  
  onMounted(() => {
    // Delay initialization to ensure DOM is ready
    setTimeout(initSwipe, 100)
  })
  
  onUnmounted(() => {
    // Cleanup is handled by useSwipe
  })
  
  return {
    initSwipe
  }
}
