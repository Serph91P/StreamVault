<template>
  <button 
    @click="toggleTheme" 
    class="theme-toggle"
    :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
    :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
  >
    <!-- Moon Icon (Dark Mode Active) -->
    <svg v-if="isDark" class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path 
        stroke-linecap="round" 
        stroke-linejoin="round" 
        stroke-width="2" 
        d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"
      />
    </svg>
    
    <!-- Sun Icon (Light Mode Active) -->
    <svg v-else class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <circle cx="12" cy="12" r="5" stroke-width="2"/>
      <line x1="12" y1="1" x2="12" y2="3" stroke-width="2" stroke-linecap="round"/>
      <line x1="12" y1="21" x2="12" y2="23" stroke-width="2" stroke-linecap="round"/>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke-width="2" stroke-linecap="round"/>
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke-width="2" stroke-linecap="round"/>
      <line x1="1" y1="12" x2="3" y2="12" stroke-width="2" stroke-linecap="round"/>
      <line x1="21" y1="12" x2="23" y2="12" stroke-width="2" stroke-linecap="round"/>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke-width="2" stroke-linecap="round"/>
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke-width="2" stroke-linecap="round"/>
    </svg>
  </button>
</template>

<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'

const { isDark, toggleTheme } = useTheme()
</script>

<style scoped lang="scss">
.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  padding: 0;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius, 8px);
  color: var(--text-primary);
  cursor: pointer;
  transition: all var(--transition-base);
  
  // Touch-friendly size (44x44px minimum)
  min-width: 44px;
  min-height: 44px;
  
  .icon {
    width: 20px;
    height: 20px;
    transition: transform var(--transition-base);
  }
  
  &:hover {
    background: var(--background-card);
    border-color: var(--primary-color);
    color: var(--primary-color);
    transform: translateY(-1px);
    
    .icon {
      transform: rotate(15deg) scale(1.1);
    }
  }
  
  &:active {
    transform: translateY(0);
    
    .icon {
      transform: rotate(0deg) scale(0.95);
    }
  }
  
  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}

// Animation when theme changes
[data-theme="light"] .theme-toggle {
  .icon {
    animation: rotate-in 0.3s var(--vue-ease-out);
  }
}

:root:not([data-theme="light"]) .theme-toggle {
  .icon {
    animation: rotate-in 0.3s var(--vue-ease-out);
  }
}

@keyframes rotate-in {
  from {
    transform: rotate(-30deg) scale(0.8);
    opacity: 0;
  }
  to {
    transform: rotate(0deg) scale(1);
    opacity: 1;
  }
}
</style>
