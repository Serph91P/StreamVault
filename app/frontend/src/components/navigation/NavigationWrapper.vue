<template>
  <div class="navigation-wrapper">
    <a class="skip-link" href="#main-content" @click.prevent="main?.focus()">Zum Inhalt</a>
    <!-- Desktop Sidebar -->
    <SidebarNav v-if="!plain" />

    <!-- Main Content Area -->
    <main
      id="main-content"
      ref="main"
      tabindex="-1"
      class="main-content"
      :class="plain ? 'without-navigation'
        : isMobile ? 'with-bottom-nav'
        : sidebarExpanded ? 'with-sidebar' : 'with-sidebar-collapsed'"
    >
      <slot />
    </main>

    <!-- Mobile Bottom Navigation -->
    <BottomNav v-if="!plain" />
  </div>
</template>

<script setup lang="ts">
import BottomNav from './BottomNav.vue'
import SidebarNav from './SidebarNav.vue'
import { useNavigation } from '@/composables/useNavigation'
import { ref } from 'vue'

const main = ref<HTMLElement | null>(null)
defineProps<{ plain?: boolean }>()

const { isMobile, sidebarExpanded } = useNavigation()
</script>

<style scoped lang="scss">
@use '../../styles/variables' as v;

.skip-link {
  position: fixed;
  top: 0;
  left: var(--spacing-3);
  z-index: 2000;
  padding: var(--spacing-3);
  background: var(--sv-sem-surface-panel);
  color: var(--sv-sem-text-primary);
  transform: translateY(-120%);
  &:focus { transform: none; }
}

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
  scroll-margin-top: var(--app-header-height, 56px);
  // Header and bottom-nav padding are accounted for via padding below.
  // Previously this had its own min-height: 100vh which stacked on top of
  // .navigation-wrapper's 100vh + the header padding-top, producing a page that
  // was always taller than the viewport.
  padding-top: calc(var(--app-header-height, 56px) + env(safe-area-inset-top, 0px));
  transition: margin v.$duration-300 v.$ease-in-out;
  width: 100%;
  box-sizing: border-box;

  &.without-navigation { padding: 0; min-height: 100dvh; }

  // Fill remaining viewport height minus header so empty pages don't collapse.
  min-height: calc(100vh - var(--app-header-height, 56px) - env(safe-area-inset-top, 0px));
  min-height: calc(100dvh - var(--app-header-height, 56px) - env(safe-area-inset-top, 0px));

  // Desktop with expanded sidebar
  &.with-sidebar {
    margin-left: var(--sv-fdn-size-sidebar, 224px);
    width: calc(100% - var(--sv-fdn-size-sidebar, 224px));
  }

  // Desktop with collapsed sidebar
  &.with-sidebar-collapsed {
    margin-left: var(--sv-fdn-size-sidebar-collapsed, 72px);
    width: calc(100% - var(--sv-fdn-size-sidebar-collapsed, 72px));
  }

  // Mobile with bottom navigation
  &.with-bottom-nav {
    // Reserve the nav plus its optional 44px connectivity pill and an 8px
    // content gap. Keeping this here gives every routed view one owner.
    padding-bottom: calc(128px + env(safe-area-inset-bottom, 0px));
    margin-left: 0;
    width: 100%;
    // Subtract bottom-nav height from min-height too so the page exactly
    // fills the visible area without forcing a scroll.
    min-height: calc(100vh - var(--app-header-height, 56px) - env(safe-area-inset-top, 0px) - 128px - env(safe-area-inset-bottom, 0px));
    min-height: calc(100dvh - var(--app-header-height, 56px) - env(safe-area-inset-top, 0px) - 128px - env(safe-area-inset-bottom, 0px));
  }
}

@media (prefers-reduced-motion: reduce) {
  .main-content { transition: none; }
}

// A visible Retry control makes the pill 62px tall (44px action plus pill
// padding and borders), rather than the ordinary 44px status height. Keep the
// routed content clearance coupled to that actual rendered state.
.navigation-wrapper:has(.mobile-connectivity-pill__action) .main-content.with-bottom-nav {
  padding-bottom: calc(146px + env(safe-area-inset-bottom, 0px));
  min-height: calc(100vh - var(--app-header-height, 56px) - env(safe-area-inset-top, 0px) - 146px - env(safe-area-inset-bottom, 0px));
  min-height: calc(100dvh - var(--app-header-height, 56px) - env(safe-area-inset-top, 0px) - 146px - env(safe-area-inset-bottom, 0px));
}
</style>
