/**
 * Navigation Management Composable
 *
 * Provides responsive navigation state and controls for:
 * - Mobile: Bottom tab navigation
 * - Desktop: Collapsible sidebar navigation
 */

import { ref, computed, nextTick } from 'vue'
import { useRouter, useRoute, type Router } from 'vue-router'
import { appStorage } from '@/services/storage'
import { useLayoutQuery } from './useLayoutQuery'

export interface NavigationTab {
  route: string
  label: string
  mobileLabel?: string
  icon: string
  description?: string
  badge?: number | null
  requiresAuth?: boolean
}

// Shared navigation state. Multiple components call useNavigation(), so this
// must live at module scope rather than creating one ref per component.
const sidebarExpanded = ref(true)
const liveBadgeCount = ref<number | null>(null)

const safePath = (path: unknown): path is string =>
  typeof path === 'string' && path[0] === '/' && path[1] !== '/'

export function prepareVideoReturn(origin: string, expanded?: Record<number, boolean>) {
  if (!safePath(origin)) return
  history.replaceState(
    { ...history.state, svrs: Math.max(0, scrollY), svre: { origin, expanded: { ...expanded } } },
    '',
    origin
  )
}

// Consume only this source entry's row state. Router-owned fields stay intact.
export function takeVideoReturnExpansion(origin: string): Record<number, boolean> {
  const state = { ...history.state }
  const snapshot = state.svre
  delete state.svre
  history.replaceState(state, '')
  const expanded = snapshot?.expanded
  return snapshot?.origin === origin && expanded && typeof expanded === 'object'
    && !Array.isArray(expanded) && Object.entries(expanded).every(([id, value]) =>
      Number.isSafeInteger(+id) && +id > 0 && typeof value === 'boolean')
    ? expanded : {}
}

export async function returnFromVideo(router: Router) {
  const origin = history.state?.back
  if (safePath(origin)) return router.back()
  await router.push('/videos')
  scrollTo(0, 0)
}

export function restoreVideoReturnScroll() {
  return nextTick(() => {
    const state = history.state
    const scroll = state?.svrs
    if (typeof scroll !== 'number' || scroll < 0) return
    delete state.svrs
    history.replaceState(state, '')
    scrollTo(0, scroll)
  })
}

// Navigation configuration
export const navigationTabs: NavigationTab[] = [
  { route: '/streamers', label: 'Kanäle', icon: 'users', description: 'Live-Status und Aufnahmen', badge: null },
  { route: '/videos', label: 'Aufzeichnungen', mobileLabel: 'Aufnahmen', icon: 'video', description: 'Mediathek durchsuchen', badge: null },
  { route: '/activity', label: 'Aktivität', icon: 'activity', description: 'Aufnahmen, Jobs und Verlauf', badge: null },
  { route: '/settings', label: 'Einstellungen', mobileLabel: 'Optionen', icon: 'settings', description: 'Globale Vorgaben und Zugänge', badge: null },
  { route: '/system', label: 'System', icon: 'server', description: 'Diagnose und Verwaltung', badge: null },
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
    if (tabRoute === '/streamers' && (route.path === '/' || route.path.startsWith('/add-streamer') || route.path.startsWith('/live/'))) return true
    if (tabRoute === '/activity' && route.path === '/overview') return true
    if (tabRoute === '/system' && (route.path === '/admin' || route.path === '/subscriptions')) return true
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
