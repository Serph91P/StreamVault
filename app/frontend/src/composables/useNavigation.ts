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

export interface NavigationTab {
  route: string
  label: string
  icon: string
  description?: string
  badge?: number | null
  requiresAuth?: boolean
}

// Navigation configuration
export const navigationTabs: NavigationTab[] = [
  { route: '/', label: 'Home', icon: 'home', description: 'Dashboard overview', badge: null },
  { route: '/streamers', label: 'Streamers', icon: 'users', description: 'Manage creators', badge: null },
  { route: '/videos', label: 'Videos', icon: 'video', description: 'Recorded sessions', badge: null },
  { route: '/subscriptions', label: 'Subs', icon: 'bell', description: 'Alerts & favorites', badge: null },
  { route: '/settings', label: 'Settings', icon: 'settings', description: 'App preferences', badge: null }
]

export function useNavigation() {
  const router = useRouter()
  const route = useRoute()

  // Responsive breakpoints (Tailwind defaults)
  const breakpoints = useBreakpoints(breakpointsTailwind)

  const isMobile = breakpoints.smaller('lg')  // < 1024px
  const isDesktop = breakpoints.greaterOrEqual('lg')  // >= 1024px

  // Sidebar state (desktop only)
  const sidebarExpanded = ref(true)

  // Badge counts
  const liveBadgeCount = ref<number | null>(null)

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
    localStorage.setItem('sidebar-expanded', String(sidebarExpanded.value))
  }

  // Initialize sidebar state from localStorage
  const initializeSidebar = () => {
    const stored = localStorage.getItem('sidebar-expanded')
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
    updateTabBadge('/subscriptions', liveBadgeCount.value)
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
