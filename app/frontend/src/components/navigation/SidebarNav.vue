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
@use '../../styles/variables' as v;

.sidebar-nav {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 240px;
  
  background: rgba(var(--background-card-rgb), 0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  
  border-right: 1px solid var(--border-color);
  box-shadow: 2px 0 16px rgba(0, 0, 0, 0.2);  /* Darker shadow for better visibility */
  
  z-index: 1000;
  
  overflow-x: hidden;
  overflow-y: auto;
  
  transition: transform v.$duration-300 v.$ease-in-out;
  
  // Fallback for browsers without backdrop-filter
  @supports not (backdrop-filter: blur(20px)) {
    background: var(--background-card);
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
    stroke: var(--text-secondary);
    fill: none;
  }
  
  &:hover {
    background: var(--primary-500);
    border-color: var(--primary-500);
    box-shadow: v.$shadow-md;
    
    .icon {
      stroke: white;
    }
  }
  
  &:focus-visible {
    outline: 2px solid var(--primary-500);
    outline-offset: 2px;
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
    
    // CRITICAL: Ensure text is visible in light mode
    [data-theme="light"] & {
      background: var(--primary-600);
      color: white;  // White text on colored background is always visible
    }
    
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
  stroke: currentColor;
  fill: none;
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
