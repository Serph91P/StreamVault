<template>
  <nav v-show="isMobile" class="bottom-nav" aria-label="Primary mobile navigation">
    <div
      v-if="showMobileConnectivityStatus"
      class="mobile-connectivity-pill"
      :class="`mobile-connectivity-pill--${mobileConnectivityTone}`"
      role="status"
      aria-live="polite"
    >
      <span class="mobile-connectivity-pill__dot" aria-hidden="true"></span>
      <span class="mobile-connectivity-pill__label">{{ mobileConnectivityLabel }}</span>
      <button
        v-if="canReconnectNow"
        class="mobile-connectivity-pill__action"
        type="button"
        @click.stop="reconnectNow"
      >
        Retry
      </button>
    </div>

    <button
      v-for="tab in navigationTabs"
      :key="tab.route"
      @click="handleTabClick(tab.route)"
      :class="{ active: isActiveRoute(tab.route) }"
      class="nav-tab focus-ring-primary"
      :aria-label="tab.label"
      :aria-current="isActiveRoute(tab.route) ? 'page' : undefined"
    >
      <!-- Icon -->
      <svg class="nav-icon">
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
import { computed } from 'vue'
import { useNavigation } from '@/composables/useNavigation'
import { useWebSocket } from '@/composables/useWebSocket'

const {
  navigationTabs,
  isMobile,
  isActiveRoute,
  navigateToTab
} = useNavigation()
const {
  connectionStatus,
  isBrowserOnline,
  reconnectNow
} = useWebSocket()

const showMobileConnectivityStatus = computed(() => {
  if (!isBrowserOnline.value) return true
  return connectionStatus.value === 'reconnecting' ||
    connectionStatus.value === 'failed' ||
    connectionStatus.value === 'error' ||
    connectionStatus.value === 'auth_failed'
})

const canReconnectNow = computed(() => {
  return isBrowserOnline.value && (
    connectionStatus.value === 'failed' ||
    connectionStatus.value === 'error' ||
    connectionStatus.value === 'disconnected'
  )
})

const mobileConnectivityTone = computed(() => {
  if (!isBrowserOnline.value || connectionStatus.value === 'auth_failed') return 'danger'
  if (connectionStatus.value === 'reconnecting') return 'warning'
  return 'info'
})

const mobileConnectivityLabel = computed(() => {
  if (!isBrowserOnline.value) return 'Offline mode'
  if (connectionStatus.value === 'reconnecting') return 'Reconnecting live updates'
  if (connectionStatus.value === 'auth_failed') return 'Sign in to sync'
  return 'Live updates paused'
})

const handleTabClick = (route: string) => {
  // Haptic feedback
  if ('vibrate' in navigator) {
    navigator.vibrate(10)
  }

  navigateToTab(route)
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: calc(68px + env(safe-area-inset-bottom, 0px));
  z-index: 1000;

  // Force own compositing layer. Without this, iOS Safari can drop the
  // fixed-positioning context when the page is scrolled and the URL bar
  // collapses, which is what was making the nav appear "to disappear"
  // mid-scroll.
  transform: translateZ(0);
  will-change: transform;
  backface-visibility: hidden;

  // Glass effect
  background: var(--glass-bg-strong);
  backdrop-filter: blur(var(--glass-blur-lg)) saturate(180%);
  -webkit-backdrop-filter: blur(var(--glass-blur-lg)) saturate(180%);
  border-top: 1px solid var(--glass-border);
  box-shadow: 0 -2px 10px var(--glass-shadow-color);

  display: flex;
  justify-content: space-around;
  align-items: center;

  // iOS safe area
  padding: 6px max(8px, env(safe-area-inset-left, 0px)) calc(6px + env(safe-area-inset-bottom, 0px)) max(8px, env(safe-area-inset-right, 0px));

  transition: transform v.$duration-300 v.$ease-in-out;

  @supports not (backdrop-filter: blur(1px)) {
    background: var(--glass-bg-solid);
  }
}

.mobile-connectivity-pill {
  position: absolute;
  left: max(8px, env(safe-area-inset-left, 0px));
  right: max(8px, env(safe-area-inset-right, 0px));
  bottom: calc(100% + 8px);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: v.$spacing-2;
  min-height: 40px;
  padding: v.$spacing-2 v.$spacing-3;
  border: 1px solid var(--glass-border-hover);
  border-radius: var(--radius-full);
  background: var(--glass-bg-strong);
  box-shadow: var(--glass-shadow-md);
  color: var(--text-primary);
  font-size: v.$text-xs;
  font-weight: v.$font-semibold;
  line-height: 1.2;
  backdrop-filter: blur(var(--glass-blur-lg));
  -webkit-backdrop-filter: blur(var(--glass-blur-lg));
  pointer-events: auto;
}

.mobile-connectivity-pill__dot {
  width: 8px;
  height: 8px;
  flex-shrink: 0;
  border-radius: v.$border-radius-full;
  background: var(--primary-color);
}

.mobile-connectivity-pill--danger {
  border-color: rgba(239, 68, 68, 0.38);

  .mobile-connectivity-pill__dot {
    background: var(--danger-color);
  }
}

.mobile-connectivity-pill--warning {
  border-color: rgba(245, 158, 11, 0.42);

  .mobile-connectivity-pill__dot {
    background: var(--warning-color);
  }
}

.mobile-connectivity-pill--info {
  border-color: rgba(59, 130, 246, 0.36);
}

.mobile-connectivity-pill__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-connectivity-pill__action {
  min-height: 32px;
  padding: 0 v.$spacing-2;
  border: 1px solid var(--glass-border-hover);
  border-radius: var(--radius-full);
  background: var(--glass-bg-subtle);
  color: var(--text-primary);
  font-size: v.$text-xs;
  font-weight: v.$font-semibold;
  cursor: pointer;
}

.nav-tab {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;

  min-width: 44px;
  min-height: 52px;
  padding: v.$spacing-1 v.$spacing-2;
  border-radius: var(--radius-lg);

  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all v.$duration-200 v.$ease-in-out;

  &:hover {
    background: var(--glass-bg-subtle);
    color: var(--text-primary);
  }

  &.active {
    color: var(--primary-color);

    [data-theme="light"] & {
      color: v.$primary-700;
    }

    .nav-icon {
      transform: scale(1.1);
    }

    .nav-label {
      font-weight: v.$font-semibold;
    }
  }
}

.nav-icon {
  width: 22px;
  height: 22px;
  transition: transform v.$duration-200 v.$ease-in-out;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
}

.nav-label {
  font-size: 11px;
  font-weight: v.$font-medium;
  line-height: 1;
  transition: font-weight v.$duration-200 v.$ease-in-out;
}

.nav-badge {
  position: absolute;
  top: 3px;
  right: calc(50% - 24px);
  display: inline-grid;
  place-items: center;
  background: var(--danger-color);
  color: white;
  min-width: 18px;
  height: 18px;
  padding: 0 v.$spacing-1;
  border-radius: v.$border-radius-full;
  font-size: 10px;
  font-weight: v.$font-bold;
  line-height: 1;
  text-align: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}
</style>
