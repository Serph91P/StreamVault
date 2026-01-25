/**
 * Theme Management Composable
 * 
 * Provides theme switching functionality between dark and light mode.
 * Theme preference is persisted in localStorage.
 * 
 * Usage:
 * ```ts
 * import { useTheme } from '@/composables/useTheme'
 * 
 * const { theme, toggleTheme, setTheme, isDark } = useTheme()
 * ```
 */

import { ref, computed, onMounted } from 'vue'

export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'streamvault-theme'
const DEFAULT_THEME: Theme = 'dark'

// Reactive theme state (shared across all components)
const currentTheme = ref<Theme>(DEFAULT_THEME)

/**
 * Theme management composable
 */
export function useTheme() {
  /**
   * Initialize theme from localStorage or system preference
   */
  const initializeTheme = () => {
    // 1. Check localStorage first
    const stored = localStorage.getItem(STORAGE_KEY) as Theme | null
    
    if (stored && (stored === 'dark' || stored === 'light')) {
      currentTheme.value = stored
    } else {
      // 2. Fall back to system preference
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      currentTheme.value = prefersDark ? 'dark' : 'light'
    }
    
    applyTheme(currentTheme.value)
  }
  
  /**
   * Apply theme to DOM
   */
  const applyTheme = (theme: Theme) => {
    if (theme === 'light') {
      document.documentElement.setAttribute('data-theme', 'light')
    } else {
      document.documentElement.removeAttribute('data-theme')
    }
  }
  
  /**
   * Set theme explicitly
   */
  const setTheme = (theme: Theme) => {
    currentTheme.value = theme
    localStorage.setItem(STORAGE_KEY, theme)
    applyTheme(theme)
  }
  
  /**
   * Toggle between dark and light
   */
  const toggleTheme = () => {
    const newTheme: Theme = currentTheme.value === 'dark' ? 'light' : 'dark'
    setTheme(newTheme)
  }
  
  /**
   * Computed: Is dark mode active?
   */
  const isDark = computed(() => currentTheme.value === 'dark')
  
  /**
   * Computed: Is light mode active?
   */
  const isLight = computed(() => currentTheme.value === 'light')
  
  // Watch for system theme changes
  onMounted(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    
    const handleChange = (e: MediaQueryListEvent) => {
      // Only auto-switch if user hasn't explicitly set a preference
      const hasExplicitPreference = localStorage.getItem(STORAGE_KEY)
      
      if (!hasExplicitPreference) {
        const newTheme: Theme = e.matches ? 'dark' : 'light'
        currentTheme.value = newTheme
        applyTheme(newTheme)
      }
    }
    
    // Modern browsers
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange)
    } else {
      // Fallback for older browsers
      mediaQuery.addListener(handleChange)
    }
  })
  
  return {
    theme: currentTheme,
    isDark,
    isLight,
    setTheme,
    toggleTheme,
    initializeTheme
  }
}
