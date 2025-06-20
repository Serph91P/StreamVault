// PWA Debug Helper für mobile Browser
export function debugPWA() {
  console.group('🔍 PWA Debug Information')
  
  // Browser information
  console.log('User Agent:', navigator.userAgent)
  console.log('Platform:', navigator.platform)
  console.log('Language:', navigator.language)
  
  // Display mode detection
  const displayModes = ['standalone', 'minimal-ui', 'fullscreen', 'browser']
  displayModes.forEach(mode => {
    const isActive = window.matchMedia(`(display-mode: ${mode})`).matches
    console.log(`Display mode ${mode}:`, isActive)
  })
  
  // Service Worker support
  console.log('Service Worker supported:', 'serviceWorker' in navigator)
  if ('serviceWorker' in navigator) {
    console.log('Service Worker controller:', navigator.serviceWorker.controller)
    navigator.serviceWorker.getRegistrations().then(registrations => {
      console.log('Service Worker registrations:', registrations.length)
    })
  }
  
  // Manifest support
  const manifestSupported = 'onbeforeinstallprompt' in window
  console.log('beforeinstallprompt supported:', manifestSupported)
  
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

// Auto-debug on mobile
if (/Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
  console.log('📱 Mobile device detected - running PWA debug...')
  setTimeout(debugPWA, 1000)
}
