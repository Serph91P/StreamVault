/**
 * Swipe Navigation Composable
 *
 * Provides Instagram-like swipe gestures for tab navigation on mobile.
 */

import { onMounted, onUnmounted } from 'vue'
import { useSwipe } from '@vueuse/core'
import { useNavigation } from './useNavigation'

export function useSwipeNavigation() {
  const { navigateNext, navigatePrevious, isMobile } = useNavigation()

  let swipeTarget: HTMLElement | null = null

  const initSwipe = () => {
    // Only enable on mobile
    if (!isMobile.value) {
      return
    }

    // Target the main content area
    swipeTarget = document.querySelector('main') || document.querySelector('.main-content') || document.body

    if (!swipeTarget) {
      return
    }

    const { lengthX } = useSwipe(swipeTarget, {
      threshold: 50,
      passive: true,

      onSwipeEnd(e: TouchEvent, swipeDirection: string) {
        // Only trigger on horizontal swipes
        if (Math.abs(lengthX.value) < 50) return

        // Haptic feedback
        if ('vibrate' in navigator) {
          navigator.vibrate(10)
        }

        // Navigate based on direction
        if (swipeDirection === 'left') {
          navigateNext()
        } else if (swipeDirection === 'right') {
          navigatePrevious()
        }
      }
    })
  }

  onMounted(() => {
    setTimeout(initSwipe, 100)
  })

  return {
    initSwipe
  }
}
