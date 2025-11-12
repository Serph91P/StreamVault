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

/**
 * Codec Configuration (Streamlink 8.0.0+)
 * H.265/AV1 Support for higher quality recordings (up to 1440p60)
 */
export const CODEC_OPTIONS = {
  'h264': {
    label: 'H.264 Only',
    description: 'Maximum 1080p60, highest compatibility',
    maxResolution: '1080p60',
    compatibility: 'high' as const,
    requiresModernHardware: false,
    icon: '📺'
  },
  'h265': {
    label: 'H.265/HEVC Only',
    description: 'Up to 1440p60, modern hardware required',
    maxResolution: '1440p60',
    compatibility: 'medium' as const,
    requiresModernHardware: true,
    icon: '🎬'
  },
  'av1': {
    label: 'AV1 Only',
    description: 'Experimental, newest hardware required, very rare',
    maxResolution: '1440p60',
    compatibility: 'low' as const,
    requiresModernHardware: true,
    icon: '🚀'
  },
  'h264,h265': {
    label: 'H.264 + H.265 (RECOMMENDED)',
    description: 'Best quality/compatibility balance, auto-fallback to H.264',
    maxResolution: '1440p60',
    compatibility: 'high' as const,
    requiresModernHardware: false,
    icon: '⭐'
  },
  'h264,h265,av1': {
    label: 'All Codecs (Future-proof)',
    description: 'Maximum quality, requires AV1 decode support',
    maxResolution: '1440p60',
    compatibility: 'medium' as const,
    requiresModernHardware: true,
    icon: '🔮'
  }
} as const

export const DEFAULT_CODEC_PREFERENCE = 'h264,h265' as const
