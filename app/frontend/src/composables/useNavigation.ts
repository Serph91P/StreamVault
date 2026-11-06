/**
 * Navigation Management Composable
 *
 * Provides responsive navigation state and controls for:
 * - Mobile: Bottom tab navigation
 * - Desktop: Collapsible sidebar navigation
 */

import { ref, computed, nextTick } from 'vue'
import { useRoute, type Router } from 'vue-router'
import { appStorage } from '@/services/storage'
import { useLayoutQuery } from './useLayoutQuery'

export interface NavigationTab {
  route: string
  label: string
  icon: string
}

// Shared navigation state. Multiple components call useNavigation(), so this
// must live at module scope rather than creating one ref per component.
const storedSidebar = appStorage.sidebarExpanded
const sidebarExpanded = ref(storedSidebar === null || storedSidebar === 'true')


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
export function takeVideoReturnExpansion(origin: string, retain = false): Record<number, boolean> {
  const state = { ...history.state }
  const snapshot = state.svre
  const expanded = snapshot?.expanded
  const valid = snapshot?.origin === origin && expanded && typeof expanded === 'object'
    && !Array.isArray(expanded) && Object.entries(expanded).every(([id, value]) =>
      Number.isSafeInteger(+id) && +id > 0 && typeof value === 'boolean')
  if (!retain || !valid) {
    delete state.svre
    history.replaceState(state, '')
  }
  return valid ? expanded : {}
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
  { route: '/streamers', label: 'Kanäle', icon: 'users' },
  { route: '/videos', label: 'Aufnahmen', icon: 'video' },
  { route: '/activity', label: 'Aktivität', icon: 'activity' },
]

export const utilityTabs = [
  { route: '/settings', label: 'Einstellungen' },
  { route: '/system', label: 'System' },

]

export function useNavigation() {
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


  // Toggle sidebar (desktop)
  const toggleSidebar = () => {
    sidebarExpanded.value = !sidebarExpanded.value
    appStorage.setSidebarExpanded(sidebarExpanded.value)
  }



  return {
    // State
    navigationTabs,
    isMobile,
    isDesktop,
    sidebarExpanded,


    // Methods
    isActiveRoute,

    toggleSidebar,

  }
}
