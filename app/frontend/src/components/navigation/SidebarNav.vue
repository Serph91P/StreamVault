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
        :aria-label="tab.label"
      >
        <!-- Icon -->
        <svg class="nav-icon">
          <use :href="`#icon-${tab.icon}`" />
        </svg>

        <!-- Text content (matches SettingsView sidebar) -->
        <div v-if="sidebarExpanded" class="nav-content">
          <span class="nav-label">{{ tab.label }}</span>
          <span v-if="tab.description" class="nav-description">{{ tab.description }}</span>
        </div>

        <!-- Meta (badges + indicator) -->
        <div v-if="sidebarExpanded" class="nav-meta">
          <span v-if="tab.badge" class="nav-badge">
            {{ tab.badge }}
          </span>
          <svg v-if="isActiveRoute(tab.route)" class="nav-indicator">
            <use href="#icon-chevron-right" />
          </svg>
        </div>

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
  top: var(--app-header-height, 64px);
  left: 0;
  bottom: 0;
  width: 260px;
  z-index: 1000;
  overflow-x: hidden;
  overflow-y: auto;
  
  // Glass effect
  background: var(--glass-bg-strong);
  backdrop-filter: blur(var(--glass-blur-lg));
  -webkit-backdrop-filter: blur(var(--glass-blur-lg));
  border-right: 1px solid var(--glass-border);
  box-shadow: var(--glass-shadow-md);
  
  transition: width v.$duration-300 v.$ease-in-out;
  
  @supports not (backdrop-filter: blur(1px)) {
    background: var(--glass-bg-solid);
  }

  &.collapsed {
    width: 84px;

    .sidebar-nav-list {
      padding: v.$spacing-6 v.$spacing-1;
    }

    .sidebar-nav-item {
      justify-content: center;
      padding: v.$spacing-3;
    }
  }
}

.sidebar-toggle {
  position: absolute;
  top: v.$spacing-4;
  right: 2px;
  z-index: 1100;
  width: 24px;
  height: 24px;
  padding: 0;
  
  background: var(--glass-bg-medium);
  border: 1px solid var(--glass-border);
  border-radius: v.$border-radius-full;
  
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  
  box-shadow: var(--glass-shadow-sm);
  transition: all v.$duration-200 v.$ease-in-out;
  
  .icon {
    width: 16px;
    height: 16px;
    stroke: var(--text-secondary);
    fill: none;
  }
  
  &:hover {
    background: var(--primary-color);
    border-color: var(--primary-color);
    box-shadow: var(--glass-shadow-md);
    
    .icon {
      stroke: white;
    }
  }
  
  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

.sidebar-nav-list {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-2;
  padding: v.$spacing-6 v.$spacing-3;
}

.sidebar-nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: v.$spacing-3;
  width: 100%;
  padding: v.$spacing-3;
  border-radius: var(--radius-lg);
  color: var(--text-secondary);
  text-decoration: none;
  background: transparent;
  cursor: pointer;
  transition: all v.$duration-200 v.$ease-out;
  overflow: hidden;
  
  &:hover:not(.active) {
    background: var(--glass-bg-subtle);
    color: var(--text-primary);
  }
  
  &.active {
    background: var(--primary-color);
    color: white;
    box-shadow: var(--glass-shadow-md);
    
    [data-theme="light"] & {
      background: var(--primary-color-dark);
    }
    
    .nav-description {
      color: rgba(255, 255, 255, 0.85);
    }
  }
  
  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

.nav-icon {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  stroke: currentColor;
  fill: none;
  transition: transform v.$duration-200 v.$ease-in-out, color v.$duration-200 v.$ease-in-out;
}

.nav-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.nav-label {
  font-size: var(--text-sm);
  font-weight: v.$font-semibold;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-description {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-meta {
  display: flex;
  align-items: center;
  gap: v.$spacing-2;
  margin-left: auto;
}

.nav-badge {
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

.nav-indicator {
  width: 16px;
  height: 16px;
  stroke: currentColor;
  fill: none;
  flex-shrink: 0;
}

.nav-tooltip {
  position: absolute;
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-left: v.$spacing-2;
  
  background: var(--glass-bg-solid);
  color: var(--text-primary);
  padding: v.$spacing-2 v.$spacing-3;
  border-radius: var(--radius-md);
  border: 1px solid var(--glass-border);
  
  font-size: v.$text-sm;
  font-weight: v.$font-medium;
  white-space: nowrap;
  
  box-shadow: var(--glass-shadow-lg);
  
  opacity: 0;
  pointer-events: none;
  transition: opacity v.$duration-200 v.$ease-in-out;
  
  &::before {
    content: '';
    position: absolute;
    right: 100%;
    top: 50%;
    transform: translateY(-50%);
    border: 6px solid transparent;
    border-right-color: var(--glass-bg-solid);
  }
  
  .sidebar-nav-item:hover & {
    opacity: 1;
  }
}
</style>
