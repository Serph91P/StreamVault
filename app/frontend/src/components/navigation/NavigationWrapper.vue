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
  // children can still escape that - clip is the modern, transform-safe answer.
  overflow-x: clip;
}

.main-content {
  position: relative;
  // Header and bottom-nav padding are accounted for via padding below.
  // Previously this had its own min-height: 100vh which stacked on top of
  // .navigation-wrapper's 100vh + the header padding-top, producing a page that
  // was always taller than the viewport.
  padding-top: calc(var(--app-header-height, 56px) + env(safe-area-inset-top, 0px));
  transition: margin v.$duration-300 v.$ease-in-out;
  width: 100%;
  box-sizing: border-box;

  // Fill remaining viewport height minus header so empty pages don't collapse.
  min-height: calc(100vh - var(--app-header-height, 56px) - env(safe-area-inset-top, 0px));
  min-height: calc(100dvh - var(--app-header-height, 56px) - env(safe-area-inset-top, 0px));

  // Desktop with expanded sidebar
  &.with-sidebar {
    margin-left: 244px; // 232px sidebar + 12px breathing room
    width: calc(100% - 244px);
  }

  // Desktop with collapsed sidebar
  &.with-sidebar-collapsed {
    margin-left: 84px; // 72px sidebar + 12px breathing room
    width: calc(100% - 84px);
  }

  // Mobile with bottom navigation
  &.with-bottom-nav {
    padding-bottom: calc(68px + env(safe-area-inset-bottom, 0px));
    margin-left: 0;
    width: 100%;
    // Subtract bottom-nav height from min-height too so the page exactly
    // fills the visible area without forcing a scroll.
    min-height: calc(100vh - var(--app-header-height, 56px) - env(safe-area-inset-top, 0px) - 68px - env(safe-area-inset-bottom, 0px));
    min-height: calc(100dvh - var(--app-header-height, 56px) - env(safe-area-inset-top, 0px) - 68px - env(safe-area-inset-bottom, 0px));
  }
}
</style>
