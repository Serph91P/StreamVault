# Phase 2: Bottom Navigation Implementation Guide

**Status**: 🚀 In Progress  
**Started**: 2025-11-09  
**Estimated Duration**: 15-20 hours  
**Goal**: Modern mobile-first navigation with app-native feel

---

## 🎯 Implementation Overview

We're building a **dual navigation system**:
- **Mobile (< 1024px)**: Bottom Tab Navigation (iOS/Android style)
- **Desktop (≥ 1024px)**: Collapsible Sidebar Navigation

**Key Features:**
- ✅ Bottom tabs with icons + labels
- ✅ Active state with color + scale animation
- ✅ Badge system for notifications
- ✅ Swipe gestures between tabs
- ✅ Collapsible desktop sidebar
- ✅ Smooth transitions (300ms)
- ✅ Touch-optimized (44px minimum)
- ✅ Haptic feedback on mobile

---

## 📁 File Structure

```
app/frontend/src/
├── components/
│   ├── navigation/
│   │   ├── BottomNav.vue          ← NEW (Mobile navigation)
│   │   ├── SidebarNav.vue         ← NEW (Desktop navigation)
│   │   └── NavigationWrapper.vue  ← NEW (Responsive wrapper)
│   └── layout/
│       └── Header.vue             ← UPDATE (Simplified header)
├── composables/
│   ├── useNavigation.ts           ← NEW (Navigation state)
│   └── useSwipeNavigation.ts      ← NEW (Swipe gestures)
├── styles/
│   └── _navigation.scss           ← NEW (Navigation styles)
└── App.vue                        ← UPDATE (Add navigation wrapper)
```

---

## 🔧 Step-by-Step Implementation

### Step 1: Install Dependencies (5 minutes)

```bash
cd app/frontend
npm install @vueuse/core @vueuse/gesture
```

**@vueuse/core**: Provides composables for swipe detection, breakpoints, etc.  
**@vueuse/gesture**: Advanced touch gesture support

---

### Step 2: Create Navigation Composable (30 minutes)

**File**: `app/frontend/src/composables/useNavigation.ts`

```typescript
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
  { route: '/live', label: 'Live', icon: 'radio', badge: null }, // Badge will show live count
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
```

**Key Features:**
- Responsive breakpoint detection
- Active route highlighting
- Badge system for notifications
- Sidebar state persistence
- Tab navigation helpers

---

### Step 3: Create Swipe Gesture Composable (20 minutes)

**File**: `app/frontend/src/composables/useSwipeNavigation.ts`

```typescript
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
```

**Features:**
- Detects horizontal swipes (>50px)
- Navigates between tabs
- Haptic feedback on navigation
- Only active on mobile

---

### Step 4: Create Bottom Navigation Component (2 hours)

**File**: `app/frontend/src/components/navigation/BottomNav.vue`

```vue
<template>
  <nav v-if="isMobile" class="bottom-nav">
    <button
      v-for="tab in navigationTabs"
      :key="tab.route"
      @click="handleTabClick(tab.route)"
      :class="{ active: isActiveRoute(tab.route) }"
      class="nav-tab"
      :aria-label="tab.label"
      :aria-current="isActiveRoute(tab.route) ? 'page' : undefined"
    >
      <!-- Icon -->
      <svg class="nav-icon" :class="`icon-${tab.icon}`">
        <use :href="`#icon-${tab.icon}`" />
      </svg>
      
      <!-- Label -->
      <span class="nav-label">{{ tab.label }}</span>
      
      <!-- Badge (notifications, live count, etc.) -->
      <span v-if="tab.badge" class="nav-badge">{{ tab.badge }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { useNavigation } from '@/composables/useNavigation'

const { 
  navigationTabs, 
  isMobile, 
  isActiveRoute, 
  navigateToTab 
} = useNavigation()

const handleTabClick = (route: string) => {
  // Haptic feedback
  if ('vibrate' in navigator) {
    navigator.vibrate(10)
  }
  
  navigateToTab(route)
}
</script>

<style scoped lang="scss">
@use '../styles/variables' as v;

.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 64px;
  z-index: 1000;
  
  // Glassmorphism effect
  background: rgba(var(--background-card-rgb), 0.8);
  backdrop-filter: blur(20px) saturate(180%);
  border-top: 1px solid var(--border-color);
  
  // Shadow for elevation
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
  
  // Flexbox layout
  display: flex;
  justify-content: space-around;
  align-items: center;
  
  // iOS safe area (notch, home indicator)
  padding-bottom: env(safe-area-inset-bottom);
  
  // Smooth transitions
  transition: transform v.$duration-300 v.$ease-in-out;
}

.nav-tab {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: v.$spacing-1; // 4px
  
  // Touch target (minimum 44x44px)
  min-width: 44px;
  min-height: 44px;
  padding: v.$spacing-2; // 8px
  
  // Reset button styles
  background: transparent;
  border: none;
  cursor: pointer;
  
  // Text color
  color: var(--text-secondary);
  
  // Smooth transitions
  transition: all v.$duration-200 v.$ease-in-out;
  
  // Hover state (desktop touch simulation)
  &:hover {
    color: var(--text-primary);
  }
  
  // Active state
  &.active {
    color: var(--primary-500);
    
    .nav-icon {
      transform: scale(1.1);
    }
    
    .nav-label {
      font-weight: v.$font-semibold;
    }
  }
  
  // Focus state (keyboard navigation)
  &:focus-visible {
    outline: 2px solid var(--primary-500);
    outline-offset: 2px;
    border-radius: v.$border-radius-md;
  }
}

.nav-icon {
  width: 24px;
  height: 24px;
  transition: transform v.$duration-200 v.$ease-in-out;
  fill: currentColor;
}

.nav-label {
  font-size: v.$text-xs; // 12px
  font-weight: v.$font-medium;
  line-height: 1;
  transition: font-weight v.$duration-200 v.$ease-in-out;
}

.nav-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  
  background: var(--danger-500);
  color: white;
  
  min-width: 18px;
  height: 18px;
  padding: 0 v.$spacing-1; // 4px horizontal
  
  border-radius: v.$border-radius-full;
  
  font-size: 10px;
  font-weight: v.$font-bold;
  line-height: 18px;
  text-align: center;
  
  // Shadow for visibility
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

// Hide on scroll down (optional enhancement)
.bottom-nav.hidden {
  transform: translateY(100%);
}
</style>
```

**Features:**
- ✅ Glassmorphism background with blur
- ✅ 5 tabs with icons + labels
- ✅ Active state with color + scale
- ✅ Badge system for notifications
- ✅ iOS safe-area support
- ✅ Haptic feedback on tap
- ✅ Accessibility (ARIA labels, keyboard nav)

---

### Step 5: Create Sidebar Navigation Component (2 hours)

**File**: `app/frontend/src/components/navigation/SidebarNav.vue`

```vue
<template>
  <aside 
    v-if="isDesktop" 
    class="sidebar-nav"
    :class="{ expanded: sidebarExpanded, collapsed: !sidebarExpanded }"
  >
    <!-- Toggle Button -->
    <button 
      @click="toggleSidebar"
      class="sidebar-toggle"
      :aria-label="sidebarExpanded ? 'Collapse sidebar' : 'Expand sidebar'"
    >
      <svg class="icon">
        <use :href="sidebarExpanded ? '#icon-chevron-left' : '#icon-chevron-right'" />
      </svg>
    </button>
    
    <!-- Navigation Items -->
    <nav class="sidebar-nav-list">
      <router-link
        v-for="tab in navigationTabs"
        :key="tab.route"
        :to="tab.route"
        class="sidebar-nav-item"
        :class="{ active: isActiveRoute(tab.route) }"
        active-class="active"
      >
        <!-- Icon -->
        <svg class="nav-icon">
          <use :href="`#icon-${tab.icon}`" />
        </svg>
        
        <!-- Label (only visible when expanded) -->
        <span v-if="sidebarExpanded" class="nav-label">{{ tab.label }}</span>
        
        <!-- Badge -->
        <span v-if="tab.badge && sidebarExpanded" class="nav-badge">
          {{ tab.badge }}
        </span>
        
        <!-- Tooltip (only visible when collapsed) -->
        <span v-if="!sidebarExpanded" class="nav-tooltip">{{ tab.label }}</span>
      </router-link>
    </nav>
  </aside>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useNavigation } from '@/composables/useNavigation'

const { 
  navigationTabs, 
  isDesktop, 
  sidebarExpanded,
  isActiveRoute,
  toggleSidebar,
  initializeSidebar
} = useNavigation()

onMounted(() => {
  initializeSidebar()
})
</script>

<style scoped lang="scss">
@use '../styles/variables' as v;

.sidebar-nav {
  position: fixed;
  left: 0;
  top: 64px; // Below header
  bottom: 0;
  z-index: 900;
  
  // Glassmorphism
  background: rgba(var(--background-card-rgb), 0.8);
  backdrop-filter: blur(20px) saturate(180%);
  border-right: 1px solid var(--border-color);
  
  // Shadow
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
  
  // Smooth width transition
  transition: width v.$duration-300 v.$ease-in-out;
  
  // Expanded state (240px)
  &.expanded {
    width: 240px;
  }
  
  // Collapsed state (64px - icons only)
  &.collapsed {
    width: 64px;
  }
}

.sidebar-toggle {
  position: absolute;
  top: v.$spacing-4; // 16px
  right: -12px; // Half outside sidebar
  
  width: 24px;
  height: 24px;
  padding: 0;
  
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: v.$border-radius-full;
  
  display: flex;
  align-items: center;
  justify-content: center;
  
  cursor: pointer;
  
  box-shadow: v.$shadow-sm;
  transition: all v.$duration-200 v.$ease-in-out;
  
  .icon {
    width: 16px;
    height: 16px;
    fill: var(--text-secondary);
  }
  
  &:hover {
    background: var(--primary-500);
    border-color: var(--primary-500);
    box-shadow: v.$shadow-md;
    
    .icon {
      fill: white;
    }
  }
}

.sidebar-nav-list {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-2; // 8px
  padding: v.$spacing-6 v.$spacing-3; // 24px vertical, 12px horizontal
}

.sidebar-nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: v.$spacing-3; // 12px
  
  padding: v.$spacing-3; // 12px
  border-radius: v.$border-radius-lg;
  
  color: var(--text-secondary);
  text-decoration: none;
  
  transition: all v.$duration-200 v.$ease-in-out;
  
  // Hover state
  &:hover {
    background: rgba(var(--primary-500-rgb), 0.1);
    color: var(--primary-500);
  }
  
  // Active state
  &.active {
    background: var(--primary-500);
    color: white;
    box-shadow: v.$shadow-md;
    
    .nav-icon {
      transform: scale(1.1);
    }
  }
  
  // Focus state
  &:focus-visible {
    outline: 2px solid var(--primary-500);
    outline-offset: 2px;
  }
}

.nav-icon {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  fill: currentColor;
  transition: transform v.$duration-200 v.$ease-in-out;
}

.nav-label {
  font-size: v.$text-sm; // 14px
  font-weight: v.$font-medium;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-badge {
  margin-left: auto;
  background: var(--danger-500);
  color: white;
  min-width: 20px;
  height: 20px;
  padding: 0 v.$spacing-1;
  border-radius: v.$border-radius-full;
  font-size: 11px;
  font-weight: v.$font-bold;
  line-height: 20px;
  text-align: center;
}

.nav-tooltip {
  position: absolute;
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-left: v.$spacing-2; // 8px
  
  background: var(--background-darker);
  color: var(--text-primary);
  
  padding: v.$spacing-2 v.$spacing-3;
  border-radius: v.$border-radius-md;
  
  font-size: v.$text-sm;
  font-weight: v.$font-medium;
  white-space: nowrap;
  
  box-shadow: v.$shadow-lg;
  
  opacity: 0;
  pointer-events: none;
  transition: opacity v.$duration-200 v.$ease-in-out;
  
  // Arrow
  &::before {
    content: '';
    position: absolute;
    right: 100%;
    top: 50%;
    transform: translateY(-50%);
    border: 6px solid transparent;
    border-right-color: var(--background-darker);
  }
  
  .sidebar-nav-item:hover & {
    opacity: 1;
  }
}
</style>
```

**Features:**
- ✅ Collapsible (240px ↔ 64px)
- ✅ Glassmorphism with blur
- ✅ Active state highlighting
- ✅ Tooltips in collapsed mode
- ✅ Badge system
- ✅ Smooth transitions
- ✅ localStorage persistence

---

### Step 6: Create Navigation Wrapper (30 minutes)

**File**: `app/frontend/src/components/navigation/NavigationWrapper.vue`

```vue
<template>
  <div class="navigation-wrapper">
    <!-- Desktop Sidebar -->
    <SidebarNav />
    
    <!-- Main Content Area -->
    <main 
      class="main-content"
      :class="{ 
        'with-sidebar': isDesktop && sidebarExpanded,
        'with-sidebar-collapsed': isDesktop && !sidebarExpanded,
        'with-bottom-nav': isMobile
      }"
    >
      <slot />
    </main>
    
    <!-- Mobile Bottom Navigation -->
    <BottomNav />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import BottomNav from './BottomNav.vue'
import SidebarNav from './SidebarNav.vue'
import { useNavigation } from '@/composables/useNavigation'
import { useSwipeNavigation } from '@/composables/useSwipeNavigation'

const { isMobile, isDesktop, sidebarExpanded } = useNavigation()
const { initSwipe } = useSwipeNavigation()

onMounted(() => {
  initSwipe()
})
</script>

<style scoped lang="scss">
@use '../styles/variables' as v;

.navigation-wrapper {
  position: relative;
  min-height: 100vh;
}

.main-content {
  position: relative;
  min-height: 100vh;
  transition: margin v.$duration-300 v.$ease-in-out;
  
  // Desktop with expanded sidebar
  &.with-sidebar {
    margin-left: 240px;
  }
  
  // Desktop with collapsed sidebar
  &.with-sidebar-collapsed {
    margin-left: 64px;
  }
  
  // Mobile with bottom navigation
  &.with-bottom-nav {
    padding-bottom: calc(64px + env(safe-area-inset-bottom));
  }
}
</style>
```

**Features:**
- ✅ Responsive wrapper for both navigation types
- ✅ Adjusts main content margin based on sidebar state
- ✅ Initializes swipe gestures
- ✅ Smooth transitions

---

### Step 7: Create SVG Icon Sprite (1 hour)

**File**: `app/frontend/public/icons.svg`

```svg
<svg xmlns="http://www.w3.org/2000/svg" style="display: none;">
  <!-- Home Icon -->
  <symbol id="icon-home" viewBox="0 0 24 24">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
    <polyline points="9 22 9 12 15 12 15 22"/>
  </symbol>
  
  <!-- Users Icon -->
  <symbol id="icon-users" viewBox="0 0 24 24">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </symbol>
  
  <!-- Video Icon -->
  <symbol id="icon-video" viewBox="0 0 24 24">
    <polygon points="23 7 16 12 23 17 23 7"/>
    <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
  </symbol>
  
  <!-- Radio Icon (Live) -->
  <symbol id="icon-radio" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="2"/>
    <path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"/>
  </symbol>
  
  <!-- Settings Icon -->
  <symbol id="icon-settings" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="3"/>
    <path d="M12 1v6m0 6v6m-8-8h6m6 0h6"/>
  </symbol>
  
  <!-- Chevron Icons -->
  <symbol id="icon-chevron-left" viewBox="0 0 24 24">
    <polyline points="15 18 9 12 15 6"/>
  </symbol>
  
  <symbol id="icon-chevron-right" viewBox="0 0 24 24">
    <polyline points="9 18 15 12 9 6"/>
  </symbol>
</svg>
```

**Load in `index.html`:**
```html
<body>
  <div id="app"></div>
  <!-- Load icon sprite -->
  <script>
    fetch('/icons.svg')
      .then(res => res.text())
      .then(svg => {
        const div = document.createElement('div')
        div.innerHTML = svg
        div.style.display = 'none'
        document.body.insertBefore(div, document.body.firstChild)
      })
  </script>
  <script type="module" src="/src/main.ts"></script>
</body>
```

---

### Step 8: Update App.vue (15 minutes)

**File**: `app/frontend/src/App.vue`

```vue
<template>
  <NavigationWrapper>
    <router-view />
  </NavigationWrapper>
</template>

<script setup lang="ts">
import NavigationWrapper from '@/components/navigation/NavigationWrapper.vue'
import { useTheme } from '@/composables/useTheme'

const { initializeTheme } = useTheme()

// Initialize theme on app mount
initializeTheme()
</script>
```

**Changes:**
- Wrap everything in `NavigationWrapper`
- Navigation automatically shows based on breakpoint
- Clean, minimal App.vue

---

### Step 9: Update Header Component (30 minutes)

**File**: `app/frontend/src/components/layout/Header.vue`

**Simplify header - remove navigation items that moved to bottom/sidebar:**

```vue
<template>
  <header class="app-header">
    <div class="header-content">
      <!-- Logo -->
      <router-link to="/" class="logo">
        StreamVault
      </router-link>
      
      <!-- Right side actions -->
      <div class="header-actions">
        <!-- Jobs Button -->
        <button class="jobs-btn" @click="$router.push('/admin/jobs')">
          <svg class="icon">
            <use href="#icon-briefcase" />
          </svg>
          <span>Jobs</span>
          <span v-if="jobsCount > 0" class="badge">{{ jobsCount }}</span>
        </button>
        
        <!-- Notifications -->
        <button class="icon-btn" @click="toggleNotifications">
          <svg class="icon">
            <use href="#icon-bell" />
          </svg>
          <span v-if="notificationCount > 0" class="badge">{{ notificationCount }}</span>
        </button>
        
        <!-- Theme Toggle -->
        <ThemeToggle />
        
        <!-- Logout -->
        <button class="btn-logout" @click="handleLogout">
          Logout
        </button>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ThemeToggle from '@/components/ThemeToggle.vue'

const jobsCount = ref(0)
const notificationCount = ref(0)

const toggleNotifications = () => {
  // TODO: Implement notifications panel
}

const handleLogout = () => {
  // TODO: Implement logout
}
</script>

<style scoped lang="scss">
@use '../styles/variables' as v;

.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 64px;
  z-index: 1100;
  
  background: rgba(var(--background-card-rgb), 0.8);
  backdrop-filter: blur(20px) saturate(180%);
  border-bottom: 1px solid var(--border-color);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 v.$spacing-6;
  max-width: 100%;
}

.logo {
  font-size: v.$text-xl;
  font-weight: v.$font-bold;
  color: var(--primary-500);
  text-decoration: none;
  transition: color v.$duration-200 v.$ease-in-out;
  
  &:hover {
    color: var(--accent-500);
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: v.$spacing-3; // 12px
}

.jobs-btn {
  display: flex;
  align-items: center;
  gap: v.$spacing-2;
  padding: v.$spacing-2 v.$spacing-4;
  
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: v.$border-radius-lg;
  
  color: var(--text-primary);
  font-size: v.$text-sm;
  font-weight: v.$font-medium;
  
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-in-out;
  
  &:hover {
    background: var(--primary-500);
    border-color: var(--primary-500);
    color: white;
  }
}

.icon-btn {
  position: relative;
  width: 44px;
  height: 44px;
  padding: v.$spacing-2;
  
  background: transparent;
  border: none;
  border-radius: v.$border-radius-lg;
  
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-in-out;
  
  .icon {
    width: 24px;
    height: 24px;
    fill: var(--text-secondary);
  }
  
  &:hover {
    background: rgba(var(--primary-500-rgb), 0.1);
    
    .icon {
      fill: var(--primary-500);
    }
  }
}

.badge {
  position: absolute;
  top: 4px;
  right: 4px;
  
  min-width: 18px;
  height: 18px;
  padding: 0 v.$spacing-1;
  
  background: var(--danger-500);
  color: white;
  border-radius: v.$border-radius-full;
  
  font-size: 10px;
  font-weight: v.$font-bold;
  line-height: 18px;
  text-align: center;
  
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.btn-logout {
  padding: v.$spacing-2 v.$spacing-4;
  background: var(--danger-500);
  border: none;
  border-radius: v.$border-radius-lg;
  color: white;
  font-size: v.$text-sm;
  font-weight: v.$font-medium;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-in-out;
  
  &:hover {
    background: var(--danger-600);
    box-shadow: v.$shadow-md;
  }
}
</style>
```

---

### Step 10: Add CSS Custom Properties for RGB Values (15 minutes)

**File**: `app/frontend/src/styles/_variables.scss`

Add RGB variants for rgba() usage:

```scss
// Add after existing color definitions
:root {
  // Existing vars...
  
  // RGB variants for rgba() usage
  --background-card-rgb: 30, 41, 59; // slate-800
  --primary-500-rgb: 20, 184, 166;   // teal-500
  --accent-500-rgb: 139, 92, 246;    // purple-500
}

[data-theme="light"] {
  --background-card-rgb: 248, 250, 252; // slate-50 in light mode
}
```

---

## ✅ Testing Checklist

### Functional Testing
- [ ] Bottom nav shows on mobile (< 1024px)
- [ ] Sidebar shows on desktop (≥ 1024px)
- [ ] Active tab highlighted correctly
- [ ] Navigation works (clicking tabs changes route)
- [ ] Swipe gestures work on mobile
- [ ] Sidebar toggle works on desktop
- [ ] Sidebar state persists in localStorage
- [ ] Badges show correct counts
- [ ] Haptic feedback works on mobile devices

### Visual Testing
- [ ] Icons display correctly (all 5 tabs)
- [ ] Glassmorphism effect visible
- [ ] Active state animation smooth (scale + color)
- [ ] Transitions smooth (300ms)
- [ ] Tooltips show in collapsed sidebar
- [ ] Responsive at 375px, 768px, 1024px, 1920px
- [ ] Safe area insets work on iPhone (notch)
- [ ] Dark/light theme works

### Accessibility Testing
- [ ] Keyboard navigation works (Tab, Enter)
- [ ] Focus visible states clear
- [ ] ARIA labels present
- [ ] Screen reader announces navigation changes
- [ ] Touch targets ≥ 44x44px
- [ ] Color contrast ≥ 4.5:1

### Performance Testing
- [ ] No layout shift when navigation loads
- [ ] Smooth 60fps animations
- [ ] No janky transitions
- [ ] Bundle size impact < 10KB gzipped

---

## 🐛 Common Issues & Solutions

### Issue 1: Icons not showing
**Solution**: Ensure `icons.svg` is loaded in `index.html` before app mounts

### Issue 2: Backdrop-filter not working
**Solution**: Check browser support, add fallback:
```scss
@supports not (backdrop-filter: blur(20px)) {
  background: var(--background-card); // Solid fallback
}
```

### Issue 3: Swipe interfering with scrolling
**Solution**: Increase threshold to 80px or disable swipe when scrolling vertically

### Issue 4: Bottom nav covering content
**Solution**: Ensure `padding-bottom` is set on main content area

### Issue 5: Sidebar state not persisting
**Solution**: Check localStorage permissions, use fallback to default expanded

---

## 📊 Success Metrics

- [ ] **Mobile Navigation**: Bottom nav functional on all mobile devices
- [ ] **Desktop Navigation**: Sidebar works with expand/collapse
- [ ] **Performance**: < 5KB additional bundle size
- [ ] **Animations**: Smooth 60fps transitions
- [ ] **Accessibility**: WCAG AA compliant
- [ ] **Browser Support**: Chrome, Firefox, Safari, Edge latest 2 versions

---

## 🚀 Next Phase

After Phase 2 completion:
→ **Phase 3: Glassmorphism Card System**
→ Redesign all cards with glass effect
→ Add gradient status borders
→ Implement overlay system

---

**Implementation Start**: 2025-11-09  
**Estimated Completion**: 2025-11-16 (1 week)
