/**
 * Frontend Configuration Constants
 * 
 * Centralized configuration values for the StreamVault frontend.
 * Extract magic numbers and frequently-used thresholds here for better maintainability.
 */

/**
 * Image Loading Configuration
 */
export const IMAGE_LOADING = {
  /**
   * Number of category images to preload on initial render.
   * Balances initial load performance vs. perceived responsiveness.
   * Remaining images lazy-load with intersection observer.
   */
  VISIBLE_CATEGORIES_PRELOAD_COUNT: 20,
} as const

/**
 * API Configuration
 */
export const API = {
  /**
   * Default timeout for API requests (ms)
   */
  DEFAULT_TIMEOUT: 30000,
} as const

/**
 * UI Configuration
 */
export const UI = {
  /**
   * Debounce delay for search inputs (ms)
   */
  SEARCH_DEBOUNCE_MS: 300,
  
  /**
   * Toast notification duration (ms)
   */
  TOAST_DURATION_MS: 3000,
} as const
