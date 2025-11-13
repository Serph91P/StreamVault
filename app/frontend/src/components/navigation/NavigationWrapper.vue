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
  min-height: 100vh;
}

.main-content {
  position: relative;
  min-height: 100vh;
  padding-top: 64px; // Header height
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
