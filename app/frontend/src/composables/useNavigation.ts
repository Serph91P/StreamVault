/**
 * Navigation Management Composable
 *
 * Provides responsive navigation state and controls for:
 * - Mobile: Bottom tab navigation
 * - Desktop: Collapsible sidebar navigation
 */

import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { appStorage } from '@/services/storage'
import { useLayoutQuery } from './useLayoutQuery'

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

  // The named shell query preserves the existing <1024px navigation boundary
  // while keeping the runtime consumer aligned with the generated Sass owner.
  const isMobile = useLayoutQuery('shell')
  const isDesktop = computed<boolean>(() => !isMobile.value)

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
