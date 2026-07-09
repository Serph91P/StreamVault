type StorageArea = 'local' | 'session'

type StorageValue = string | null

const KEYS = {
  sessionToken: 'streamvault_session',
  theme: 'streamvault-theme',
  sidebarExpanded: 'sidebar-expanded',
  liveCodecMode: 'streamvault-live-codec-mode',
  notifications: 'streamvault_notifications',
  legacyReadTimestamp: 'lastReadTimestamp',
  oauthReturnUrl: 'oauth_return_url',
  pwaInstallDismissed: 'pwa-install-dismissed',
  viewModePrefix: 'streamvault-view-mode'
} as const

function resolveStorage(area: StorageArea): Storage | null {
  if (typeof window === 'undefined') return null
  return area === 'local' ? window.localStorage : window.sessionStorage
}

function getItem(key: string, area: StorageArea = 'local'): StorageValue {
  try {
    return resolveStorage(area)?.getItem(key) ?? null
  } catch {
    return null
  }
}

function setItem(key: string, value: string, area: StorageArea = 'local'): void {
  try {
    resolveStorage(area)?.setItem(key, value)
  } catch (error) {
    console.error(`Failed to write storage key ${key}:`, error)
  }
}

function removeItem(key: string, area: StorageArea = 'local'): void {
  try {
    resolveStorage(area)?.removeItem(key)
  } catch (error) {
    console.error(`Failed to remove storage key ${key}:`, error)
  }
}

function clear(area: StorageArea = 'local'): void {
  try {
    resolveStorage(area)?.clear()
  } catch (error) {
    console.error(`Failed to clear ${area} storage:`, error)
  }
}

export const appStorage = {
  get sessionToken() {
    return getItem(KEYS.sessionToken)
  },
  setSessionToken(token: string) {
    setItem(KEYS.sessionToken, token)
  },
  clearSessionToken() {
    removeItem(KEYS.sessionToken)
  },

  get theme() {
    return getItem(KEYS.theme)
  },
  setTheme(theme: string) {
    setItem(KEYS.theme, theme)
  },
  hasThemePreference() {
    return getItem(KEYS.theme) !== null
  },

  get sidebarExpanded() {
    return getItem(KEYS.sidebarExpanded)
  },
  setSidebarExpanded(expanded: boolean) {
    setItem(KEYS.sidebarExpanded, String(expanded))
  },

  /** Persisted grid/list preference per page (e.g. 'streamers', 'videos') */
  getViewMode(page: string): 'grid' | 'list' | null {
    const value = getItem(`${KEYS.viewModePrefix}-${page}`)
    return value === 'grid' || value === 'list' ? value : null
  },
  setViewMode(page: string, mode: 'grid' | 'list') {
    setItem(`${KEYS.viewModePrefix}-${page}`, mode)
  },

  get liveCodecMode() {
    return getItem(KEYS.liveCodecMode)
  },
  setLiveCodecMode(mode: string) {
    setItem(KEYS.liveCodecMode, mode)
  },

  get notifications() {
    return getItem(KEYS.notifications)
  },
  setNotifications(value: string) {
    setItem(KEYS.notifications, value)
  },
  clearNotifications() {
    removeItem(KEYS.notifications)
  },

  get legacyReadTimestamp() {
    return getItem(KEYS.legacyReadTimestamp)
  },

  setOauthReturnUrl(url: string) {
    setItem(KEYS.oauthReturnUrl, url, 'session')
  },
  get pwaInstallDismissed() {
    return getItem(KEYS.pwaInstallDismissed)
  },
  setPwaInstallDismissed(value: boolean) {
    setItem(KEYS.pwaInstallDismissed, String(value))
  },
  clearPwaInstallDismissed() {
    removeItem(KEYS.pwaInstallDismissed)
  },
  clearSessionStorage() {
    clear('session')
  }
}

export { KEYS as storageKeys }
