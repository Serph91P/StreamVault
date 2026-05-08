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
@use '../../styles/variables' as v;

.navigation-wrapper {
  position: relative;
  // Use dvh so chrome address-bar resizing on mobile doesn't push fixed
  // bottom-nav off-screen. Fallback to vh for older browsers.
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  // Prevent rogue 100vw children (modals, decorations) from creating a
  // horizontal scroll on mobile. body has overflow-x: hidden but flex/position
  // children can still escape that — clip is the modern, transform-safe answer.
  overflow-x: clip;
}

.main-content {
  position: relative;
  // Header (64px) + bottom-nav padding are accounted for via padding below.
  // Previously this had its own min-height: 100vh which stacked on top of
  // .navigation-wrapper's 100vh + the 64px padding-top, producing a page that
  // was always taller than the viewport.
  padding-top: 64px; // Header height
  transition: margin v.$duration-300 v.$ease-in-out;
  width: 100%;
  box-sizing: border-box;

  // Fill remaining viewport height minus header so empty pages don't collapse.
  min-height: calc(100vh - 64px);
  min-height: calc(100dvh - 64px);

  // Desktop with expanded sidebar
  &.with-sidebar {
    margin-left: 272px; // 260px sidebar + 12px toggle overhang
    width: calc(100% - 272px);
  }
  
  // Desktop with collapsed sidebar
  &.with-sidebar-collapsed {
    margin-left: 96px; // 84px sidebar + 12px toggle overhang
    width: calc(100% - 96px);
  }
  
  // Mobile with bottom navigation
  &.with-bottom-nav {
    padding-bottom: calc(64px + env(safe-area-inset-bottom));
    margin-left: 0;
    width: 100%;
    // Subtract bottom-nav height from min-height too so the page exactly
    // fills the visible area without forcing a scroll.
    min-height: calc(100vh - 64px - 64px - env(safe-area-inset-bottom));
    min-height: calc(100dvh - 64px - 64px - env(safe-area-inset-bottom));
  }
}
</style>
