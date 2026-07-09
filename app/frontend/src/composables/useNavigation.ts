/**
 * Navigation Management Composable
 *
 * Provides responsive navigation state and controls for:
 * - Mobile: Bottom tab navigation
 * - Desktop: Collapsible sidebar navigation
 */

import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useBreakpoints, breakpointsTailwind } from '@vueuse/core'
import { appStorage } from '@/services/storage'

export interface NavigationTab {
  route: string
  label: string
  icon: string
  description?: string
  badge?: number | null
  requiresAuth?: boolean
}

// Shared navigation state. Multiple components call useNavigation(), so this
// must live at module scope rather than creating one ref per component.
const sidebarExpanded = ref(true)
const liveBadgeCount = ref<number | null>(null)

// Navigation configuration
export const navigationTabs: NavigationTab[] = [
  { route: '/', label: 'Dashboard', icon: 'home', description: 'Dashboard overview', badge: null },
  { route: '/streamers', label: 'Streamers', icon: 'users', description: 'Manage creators', badge: null },
  { route: '/videos', label: 'Library', icon: 'video', description: 'Video library', badge: null },
  { route: '/subscriptions', label: 'Subscriptions', icon: 'bell', description: 'Manage subscriptions', badge: null },
  { route: '/settings', label: 'Settings', icon: 'settings', description: 'App preferences', badge: null }
]

export function useNavigation() {
  const router = useRouter()
  const route = useRoute()

  // Responsive breakpoints (Tailwind defaults)
  const breakpoints = useBreakpoints(breakpointsTailwind)

  // Use computed wrappers so we can ensure a sensible value during the
  // first paint frame. `useBreakpoints` evaluates window.matchMedia lazily
  // and previously returned `false` for both flags on the very first tick
  // after a hard reload - that made BottomNav (gated by v-if="isMobile")
  // pop in/out and look "missing" right after page load.
  const lgQuery = breakpoints.smaller('lg')
  const lgUpQuery = breakpoints.greaterOrEqual('lg')

  const isMobile = computed<boolean>(() => {
    if (typeof window === 'undefined') return false
    // Trust matchMedia first - VueUse hydrates it synchronously, but on
    // some browsers the reactive ref needs a tick. Fall back to width check.
    if (lgQuery.value) return true
    return window.matchMedia('(max-width: 1023.98px)').matches
  })

  const isDesktop = computed<boolean>(() => {
    if (typeof window === 'undefined') return true
    if (lgUpQuery.value) return true
    return window.matchMedia('(min-width: 1024px)').matches
  })

  // Check if route is active
  const isActiveRoute = (tabRoute: string): boolean => {
    if (tabRoute === '/') {
      return route.path === '/'
    }
    return route.path.startsWith(tabRoute)
  }

  // Get current tab index
  const currentTabIndex = computed(() => {
    return navigationTabs.findIndex(tab => isActiveRoute(tab.route))
  })

  // Navigate to tab
  const navigateToTab = (tabRoute: string) => {
    if (route.path !== tabRoute) {
      router.push(tabRoute)
    }
  }

  // Navigate to next/previous tab (for swipe gestures)
  const navigateNext = () => {
    const nextIndex = (currentTabIndex.value + 1) % navigationTabs.length
    navigateToTab(navigationTabs[nextIndex].route)
  }

  const navigatePrevious = () => {
    const prevIndex = currentTabIndex.value === 0
      ? navigationTabs.length - 1
      : currentTabIndex.value - 1
    navigateToTab(navigationTabs[prevIndex].route)
  }

  // Toggle sidebar (desktop)
  const toggleSidebar = () => {
    sidebarExpanded.value = !sidebarExpanded.value
    appStorage.setSidebarExpanded(sidebarExpanded.value)
  }

  // Initialize sidebar state from localStorage
  const initializeSidebar = () => {
    const stored = appStorage.sidebarExpanded
    if (stored !== null) {
      sidebarExpanded.value = stored === 'true'
    }
  }

  // Update badge count for a specific tab
  const updateTabBadge = (tabRoute: string, count: number | null) => {
    const tab = navigationTabs.find(t => t.route === tabRoute)
    if (tab) {
      tab.badge = count && count > 0 ? count : null
    }
  }

  // Update live badge count (convenience method)
  const updateLiveBadgeCount = (count: number) => {
    liveBadgeCount.value = count > 0 ? count : null
    updateTabBadge('/streamers', liveBadgeCount.value)
  }

  return {
    // State
    navigationTabs,
    isMobile,
    isDesktop,
    sidebarExpanded,
    currentTabIndex,

    // Methods
    isActiveRoute,
    navigateToTab,
    navigateNext,
    navigatePrevious,
    toggleSidebar,
    initializeSidebar,
    updateTabBadge,
    updateLiveBadgeCount
  }
}
