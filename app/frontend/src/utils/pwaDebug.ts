// PWA diagnostics helper for development sessions.
import { UI } from '@/config/constants'

export function debugPWA() {
  console.group('🔍 PWA Debug Information')
  
  // Browser information
  console.log('🌐 User Agent:', navigator.userAgent)
  console.log('📱 Platform:', navigator.platform)
  console.log('🗣️ Language:', navigator.language)
  console.log('🔗 URL:', window.location.href)
  console.log('🔒 Protocol:', window.location.protocol)
  
  // Android Chrome specific detection
  const isAndroid = /Android/i.test(navigator.userAgent)
  const isChrome = /Chrome/i.test(navigator.userAgent) && !/Edge|OPR/i.test(navigator.userAgent)
  console.log('📱 Is Android:', isAndroid)
  console.log('🌐 Is Chrome:', isChrome)
  
  // Display mode detection
  const displayModes = ['standalone', 'minimal-ui', 'fullscreen', 'browser']
  let currentDisplayMode = 'browser'
  displayModes.forEach(mode => {
    const isActive = window.matchMedia(`(display-mode: ${mode})`).matches
    console.log(`📐 Display mode ${mode}:`, isActive)
    if (isActive) currentDisplayMode = mode
  })
  
  // PWA Installation status
  const isInstalled = currentDisplayMode !== 'browser'
  console.log('📲 PWA Installed:', isInstalled)
  
  // Service Worker support and status
  console.log('⚙️ Service Worker supported:', 'serviceWorker' in navigator)
  if ('serviceWorker' in navigator) {
    console.log('🎮 Service Worker controller:', !!navigator.serviceWorker.controller)
    navigator.serviceWorker.getRegistrations().then(registrations => {
      console.log('📋 Service Worker registrations:', registrations.length)
      registrations.forEach((reg, i) => {
        console.log(`  Registration ${i + 1}:`, reg.scope)
      })
    })
  }
  
  // Install prompt support
  const manifestSupported = 'onbeforeinstallprompt' in window
  console.log('📲 beforeinstallprompt supported:', manifestSupported)
  console.log('📲 Install prompt available:', !!(window as any).deferredPrompt)
  
  // Push notifications
  console.log('Push Manager supported:', 'PushManager' in window)
  console.log('Notifications supported:', 'Notification' in window)
  if ('Notification' in window) {
    console.log('Notification permission:', Notification.permission)
  }
  
  // Fetch manifest
  fetch('/manifest.json')
    .then(response => response.json())
    .then(manifest => {
      console.log('Manifest loaded successfully:', manifest)
    })
    .catch(error => {
      console.error('Failed to load manifest:', error)
    })
  
  // Check if running as PWA
  const isPWA = window.matchMedia('(display-mode: standalone)').matches ||
                (window.navigator as any).standalone === true
  console.log('Running as PWA:', isPWA)
  
  // Check viewport
  console.log('Viewport width:', window.innerWidth)
  console.log('Viewport height:', window.innerHeight)
  console.log('Device pixel ratio:', window.devicePixelRatio)
  
  // Check orientation
  if ('orientation' in screen) {
    console.log('Screen orientation:', (screen.orientation as any).type)
  }
  
  console.groupEnd()
}

if (import.meta.env.DEV) {
  setTimeout(() => {
    ;(window as typeof window & { debugStreamVaultPWA?: typeof debugPWA }).debugStreamVaultPWA = debugPWA
  }, UI.PWA_DEBUG_DELAY_MS)
}
