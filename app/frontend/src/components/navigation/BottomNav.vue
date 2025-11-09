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
@use '../../styles/variables' as v;

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
  
  // Fallback for browsers without backdrop-filter
  @supports not (backdrop-filter: blur(20px)) {
    background: var(--background-card);
  }
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
  stroke: currentColor;
  fill: none;
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
