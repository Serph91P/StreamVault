<template>
  <aside
    v-if="isDesktop"
    class="sidebar-nav"
    aria-label="Anwendungsnavigation"
    :class="{ expanded: sidebarExpanded, collapsed: !sidebarExpanded }"
  >
    <!-- Navigation Items -->
    <nav class="sidebar-nav-list" aria-label="Hauptnavigation">
      <router-link
        v-for="tab in navigationTabs"
        :key="tab.route"
        :to="tab.route"
        class="sidebar-nav-item"
        :class="{ active: isActiveRoute(tab.route) }"
        active-class="active"
        :aria-label="tab.label"
        :title="!sidebarExpanded ? tab.label : undefined"
        :aria-current="isActiveRoute(tab.route) ? 'page' : undefined"
      >
        <!-- Icon -->
        <svg class="nav-icon" aria-hidden="true">
          <use :href="`#icon-${tab.icon}`" />
        </svg>

        <div v-if="sidebarExpanded" class="nav-content">
          <span class="nav-label">{{ tab.label }}</span>
        </div>

        <!-- Meta (badges + indicator) -->
        <div v-if="sidebarExpanded" class="nav-meta">
          <span v-if="tab.badge" class="nav-badge">
            {{ tab.badge }}
          </span>
        </div>
      </router-link>
    </nav>

    <!-- Footer with collapse/expand toggle -->
    <div class="sidebar-footer">
      <button
        @click="toggleSidebar"
        class="sidebar-toggle"
        :aria-label="sidebarExpanded ? 'Navigation einklappen' : 'Navigation ausklappen'"
      >
        <svg class="toggle-icon">
          <use :href="sidebarExpanded ? '#icon-chevron-left' : '#icon-chevron-right'" />
        </svg>
        <span v-if="sidebarExpanded" class="toggle-label">Einklappen</span>
      </button>
    </div>
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
  top: calc(var(--app-header-height, 56px) + env(safe-area-inset-top, 0px));
  left: 0;
  bottom: 0;
  width: var(--sv-fdn-size-sidebar, 224px);
  z-index: 1000;
  overflow: hidden;

  display: flex;
  flex-direction: column;

  // Opaque tokenized shell surface: navigation does not use glass or blur.
  background: var(--sv-sem-surface-panel);
  border-right: 1px solid var(--sv-sem-border-default);
  box-shadow: none;

  transition: width v.$duration-300 v.$ease-in-out;

  &.collapsed {
    width: var(--sv-fdn-size-sidebar-collapsed, 72px);

    .sidebar-nav-list {
      padding: v.$spacing-4 v.$spacing-1;
    }

    .sidebar-nav-item {
      justify-content: center;
      padding: v.$spacing-2;
    }

    .sidebar-toggle {
      justify-content: center;
      padding: v.$spacing-2;
    }
  }
}

.sidebar-footer {
  padding: v.$spacing-2;
  border-top: 1px solid var(--sv-sem-border-default);
  background: transparent;
  flex-shrink: 0;
}

.sidebar-toggle {
  width: 100%;
  min-height: 44px;
  padding: v.$spacing-2 v.$spacing-3;

  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  color: var(--sv-sem-text-secondary);

  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: v.$spacing-2;
  cursor: pointer;

  transition: background v.$duration-200 v.$ease-in-out,
              color v.$duration-200 v.$ease-in-out,
              border-color v.$duration-200 v.$ease-in-out;

  .toggle-icon {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    fill: none;
    flex-shrink: 0;
  }

  .toggle-label {
    font-size: v.$text-sm;
    font-weight: v.$font-medium;
    line-height: 1;
  }

  &:hover {
    background: var(--sv-sem-surface-raised);
    color: var(--sv-sem-text-primary);
  }

  &:focus-visible {
    outline: 2px solid var(--sv-sem-action-focus);
    outline-offset: 2px;
  }
}

.sidebar-nav-list {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-1;
  padding: v.$spacing-5 v.$spacing-3;
  flex: 1 1 auto;
  overflow-x: hidden;
  overflow-y: auto;
}

.sidebar-nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: v.$spacing-3;
  width: 100%;
  min-height: 44px;
  padding: v.$spacing-2 v.$spacing-3;
  border: 1px solid transparent;
  border-radius: var(--sv-fdn-radius-md);
  color: var(--sv-sem-text-secondary);
  text-decoration: none;
  background: transparent;
  cursor: pointer;
  // Do not tween foreground/background when route activity changes: the
  // intermediate pair can be unreadable even though both endpoints pass.
  overflow: hidden;

  &:hover:not(.active) {
    background: var(--sv-sem-surface-raised);
    color: var(--sv-sem-text-primary);
  }

  &.active {
    background: var(--sv-sem-surface-raised);
    color: var(--sv-sem-text-primary);
    border-color: var(--sv-sem-border-default);

    .nav-icon { color: var(--sv-sem-action-focus); }
  }

  &:focus-visible {
    outline: 2px solid var(--sv-sem-action-focus);
    outline-offset: 2px;
  }
}

.nav-icon {
  width: 20px;
  height: 20px;
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
  font-weight: v.$font-medium;
  line-height: 1.4;
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
  background: var(--sv-sem-surface-selected);
  color: var(--sv-sem-text-primary);
  min-width: 20px;
  height: 20px;
  padding: 0 v.$spacing-1;
  border-radius: v.$border-radius-full;
  font-size: 11px;
  font-weight: v.$font-bold;
  line-height: 20px;
  text-align: center;
}

@media (prefers-reduced-motion: reduce) {
  .sidebar-nav,
  .sidebar-toggle,
  .nav-icon {
    transition: none;
  }
}
</style>
