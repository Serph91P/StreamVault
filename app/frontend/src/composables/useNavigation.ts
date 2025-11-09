import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useBreakpoints } from '@vueuse/core'

export interface NavigationTab {
  route: string
  label: string
  icon: string
  badge?: number | null
  requiresAuth?: boolean
}

// Navigation configuration
export const navigationTabs: NavigationTab[] = [
  { route: '/', label: 'Home', icon: 'home', badge: null },
  { route: '/streamers', label: 'Streamers', icon: 'users', badge: null },
  { route: '/videos', label: 'Videos', icon: 'video', badge: null },
  { route: '/live', label: 'Live', icon: 'radio', badge: null },
  { route: '/settings', label: 'Settings', icon: 'settings', badge: null }
]

export function useNavigation() {
  const router = useRouter()
  const route = useRoute()
  
  // Responsive breakpoints
  const breakpoints = useBreakpoints({
    mobile: 0,
    tablet: 768,
    desktop: 1024
  })
  
  const isMobile = breakpoints.smaller('desktop')
  const isDesktop = breakpoints.greaterOrEqual('desktop')
  
  // Sidebar state (desktop only)
  const sidebarExpanded = ref(true)
  
  // Get badge count for live streams
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
    router.push(tabRoute)
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
  
  // Update live badge count
  const updateLiveBadgeCount = (count: number) => {
    liveBadgeCount.value = count > 0 ? count : null
    
    // Update navigation tabs
    const liveTab = navigationTabs.find(tab => tab.route === '/live')
    if (liveTab) {
      liveTab.badge = liveBadgeCount.value
    }
  }
  
  return {
    navigationTabs,
    isMobile,
    isDesktop,
    sidebarExpanded,
    currentTabIndex,
    isActiveRoute,
    navigateToTab,
    navigateNext,
    navigatePrevious,
    toggleSidebar,
    initializeSidebar,
    updateLiveBadgeCount
  }
}
