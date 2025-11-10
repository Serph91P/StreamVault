import { ref, onMounted, onUnmounted } from 'vue'
import router from '@/router'

interface PWAInstallPrompt {
  prompt(): Promise<void>
  userChoice: Promise<{outcome: 'accepted' | 'dismissed'}>
}

interface NotificationPermission {
  state: 'granted' | 'denied' | 'default'
}

export function usePWA() {
  const isInstallable = ref(false)
  const isInstalled = ref(false)
  const isOnline = ref(navigator.onLine)
  const registration = ref<ServiceWorkerRegistration | null>(null)
  const installPrompt = ref<PWAInstallPrompt | null>(null)
  const pushSupported = ref('serviceWorker' in navigator && 'PushManager' in window)
  const notificationPermission = ref<NotificationPermission['state']>('default')

  // Check if app is installed (running in standalone mode)
  const checkInstallStatus = () => {
    isInstalled.value = window.matchMedia('(display-mode: standalone)').matches ||
                       (window.navigator as any).standalone === true ||
                       window.matchMedia('(display-mode: fullscreen)').matches ||
                       window.matchMedia('(display-mode: minimal-ui)').matches
  }

  // Register service worker
  const registerServiceWorker = async () => {
    if ('serviceWorker' in navigator) {
      try {
        const reg = await navigator.serviceWorker.register('/sw.js')
        registration.value = reg
        console.log('Service Worker registered successfully:', reg)

        // Listen for updates
        reg.addEventListener('updatefound', () => {
          const newWorker = reg.installing
          if (newWorker) {
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                // New version available
                console.log('New version available!')
                // You could show a toast here asking user to refresh
              }
            })
          }
        })

        return reg
      } catch (error) {
        console.error('Service Worker registration failed:', error)
        return null
      }
    }
    return null
  }

  // Install PWA
  const installPWA = async () => {
    if (installPrompt.value) {
      try {
        await installPrompt.value.prompt()
        const choiceResult = await installPrompt.value.userChoice
        
        if (choiceResult.outcome === 'accepted') {
          console.log('PWA installed successfully')
          isInstallable.value = false
          installPrompt.value = null
        }
      } catch (error) {
        console.error('PWA installation failed:', error)
      }
    }
  }

  // Request notification permission
  const requestNotificationPermission = async (): Promise<NotificationPermission['state']> => {
    if (!('Notification' in window)) {
      console.warn('This browser does not support notifications')
      return 'denied'
    }

    let permission = Notification.permission

    if (permission === 'default') {
      permission = await Notification.requestPermission()
    }

    notificationPermission.value = permission
    return permission
  }

  // Subscribe to push notifications
  const subscribeToPush = async (): Promise<PushSubscription | null> => {
    if (!registration.value || !pushSupported.value) {
      console.warn('Push notifications not supported')
      return null
    }

    try {
      // Request notification permission first
      const permission = await requestNotificationPermission()
      if (permission !== 'granted') {
        throw new Error('Notification permission denied')
      }

      // Get existing subscription or create new one
      console.log('🔔 Starting push subscription process...')
      let subscription = await registration.value.pushManager.getSubscription()
      console.log('🔔 Existing subscription:', subscription ? 'Found' : 'None')
      
      if (!subscription) {
        console.log('🔔 Fetching VAPID public key...')
        // Generate VAPID keys on server side and use the public key here
        const response = await fetch('/api/push/vapid-public-key', {
          credentials: 'include' // CRITICAL: Required to send session cookie
        })
        const { publicKey } = await response.json()
        console.log('🔔 VAPID public key received:', publicKey?.substring(0, 20) + '...')

        console.log('🔔 Creating new push subscription...')
        subscription = await registration.value.pushManager.subscribe({
          userVisibleOnly: true,
          // Cast to BufferSource to satisfy TS lib.dom variations across environments
          applicationServerKey: urlBase64ToUint8Array(publicKey) as unknown as BufferSource
        })
        console.log('🔔 New subscription created:', subscription)
      }

      console.log('🔔 Sending subscription to server...')
      const subscriptionData = {
        subscription: subscription.toJSON(),
        userAgent: navigator.userAgent
      }
      console.log('🔔 Subscription data:', subscriptionData)
      
      // Send subscription to server
      const serverResponse = await fetch('/api/push/subscribe', {
        method: 'POST',
        credentials: 'include', // CRITICAL: Required to send session cookie
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(subscriptionData)
      })
      
      const result = await serverResponse.json()
      console.log('🔔 Server response:', result)
      
      if (!serverResponse.ok) {
        throw new Error(`Server error: ${result.message || 'Unknown error'}`)
      }

      console.log('🔔 Push subscription successful!')
      return subscription
    } catch (error) {
      console.error('Push subscription failed:', error)
      return null
    }
  }

  // Unsubscribe from push notifications
  const unsubscribeFromPush = async (): Promise<boolean> => {
    if (!registration.value) {
      return false
    }

    try {
      const subscription = await registration.value.pushManager.getSubscription()
      if (subscription) {
        await subscription.unsubscribe()
        
        // Notify server
        await fetch('/api/push/unsubscribe', {
          method: 'POST',
          credentials: 'include', // CRITICAL: Required to send session cookie
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            endpoint: subscription.endpoint
          })
        })
      }
      
      return true
    } catch (error) {
      console.error('Push unsubscription failed:', error)
      return false
    }
  }
  // Show local notification
  const showNotification = async (title: string, options: NotificationOptions = {}) => {
    if (!registration.value) {
      console.warn('Service Worker not registered')
      return
    }

    const permission = await requestNotificationPermission()
    if (permission !== 'granted') {
      console.warn('Notification permission not granted')
      return
    }

    const defaultOptions: NotificationOptions = {
      icon: '/android-icon-192x192.png',
      badge: '/android-icon-96x96.png',
      tag: 'streamvault-notification',
      ...options
    }

    // Add vibration on mobile devices
    if ('vibrate' in navigator && navigator.vibrate) {
      navigator.vibrate([200, 100, 200])
    }

    console.log('Showing notification:', title, defaultOptions)
    return registration.value.showNotification(title, defaultOptions)
  }

  // Get platform information for installation
  const getPlatformInfo = () => {
    const userAgent = navigator.userAgent
    
    let platform = 'Unknown'
    let browser = 'Unknown'
    
    // Detect platform
    if (/iPad|iPhone|iPod/.test(userAgent)) {
      platform = 'iOS'
    } else if (/Android/.test(userAgent)) {
      platform = 'Android'
    } else if (/Windows/.test(userAgent)) {
      platform = 'Windows'
    } else if (/Macintosh|Mac OS X/.test(userAgent)) {
      platform = 'macOS'
    } else if (/Linux/.test(userAgent) && !/Android/.test(userAgent)) {
      platform = 'Linux'
    }
    
    // Detect browser
    if (/Edge/.test(userAgent)) {
      browser = 'Microsoft Edge'
    } else if (/Chrome/.test(userAgent) && !/Edge/.test(userAgent)) {
      browser = 'Google Chrome'
    } else if (/Safari/.test(userAgent) && !/Chrome/.test(userAgent)) {
      browser = 'Safari'
    } else if (/Firefox/.test(userAgent)) {
      browser = 'Firefox'
    } else if (/Opera|OPR/.test(userAgent)) {
      browser = 'Opera'
    } else if (/SamsungBrowser/.test(userAgent)) {
      browser = 'Samsung Internet'
    }
    
    return { platform, browser }
  }

  // Check PWA installation criteria
  const checkPWAInstallCriteria = () => {
    const criteria = {
      hasManifest: !!document.querySelector('link[rel="manifest"]'),
      hasServiceWorker: 'serviceWorker' in navigator,
      hasHTTPS: location.protocol === 'https:' || location.hostname === 'localhost',
      hasIcons: true, // We know we have icons
      hasStartUrl: true, // We have a start_url in manifest
      hasName: true, // We have name in manifest
      hasDisplay: true // We have display mode in manifest
    }
    
    const allCriteriaMet = Object.values(criteria).every(Boolean)
    return { criteria, allCriteriaMet }
  }

  // Get installation instructions for current platform
  const getInstallInstructions = () => {
    const { platform, browser } = getPlatformInfo()
    
    if (platform === 'iOS' && browser === 'Safari') {
      return {
        steps: [
          'Tap the Share button (box with arrow) at the bottom of the screen',
          'Scroll down and tap "Add to Home Screen"',
          'Edit the name if desired, then tap "Add"',
          'StreamVault will appear on your home screen'
        ],
        icon: '📱'
      }
    }
    
    if (platform === 'Android' && (browser === 'Google Chrome' || browser === 'Samsung Internet')) {
      return {
        steps: [
          'Look for the "Install" or "Add to Home Screen" prompt',
          'If no prompt appears, tap the menu (⋮) and select "Install App" or "Add to Home Screen"',
          'Tap "Install" in the confirmation dialog',
          'StreamVault will be added to your app drawer and home screen'
        ],
        icon: '🤖'
      }
    }
    
    if (platform === 'Windows' && (browser === 'Google Chrome' || browser === 'Microsoft Edge')) {
      return {
        steps: [
          'Look for the install icon (⊞) in the address bar',
          'Click the install icon and select "Install"',
          'Or open browser menu and select "Install StreamVault"',
          'The app will be added to your Start Menu and taskbar'
        ],
        icon: '🪟'
      }
    }
    
    if (platform === 'macOS' && (browser === 'Google Chrome' || browser === 'Safari' || browser === 'Microsoft Edge')) {
      return {
        steps: [
          'Look for the install icon in the address bar',
          'Click the install icon and select "Install"',
          'Or use browser menu and select "Install StreamVault"',
          'The app will be added to your Applications folder and Dock'
        ],
        icon: '🍎'
      }
    }
    
    if (platform === 'Linux' && browser === 'Google Chrome') {
      return {
        steps: [
          'Look for the install icon in the address bar',
          'Click the install icon and select "Install"',
          'Or open browser menu and select "Install StreamVault"',
          'The app will be added to your applications menu'
        ],
        icon: '🐧'
      }
    }
    
    return {
      steps: [
        'PWA installation may not be supported on this platform/browser combination',
        'For the best experience, use Chrome, Edge, or Safari on a supported platform'
      ],
      icon: '❓'
    }
  }

  // Online/offline handlers
  const handleOnline = () => {
    isOnline.value = true
    console.log('App is online')
  }

  const handleOffline = () => {
    isOnline.value = false
    console.log('App is offline')
  }

  // Install prompt handler
  const handleBeforeInstallPrompt = (event: Event) => {
    event.preventDefault()
    installPrompt.value = event as any
    isInstallable.value = true
    console.log('PWA install prompt available')
  }

  // Service worker message handler
  const handleServiceWorkerMessage = (event: MessageEvent) => {
    console.log('Message from Service Worker:', event.data)
    
    if (event.data.type === 'NOTIFICATION_CLICK') {
      // Handle notification click from service worker
      const { action, data, url } = event.data
      console.log('Notification clicked:', { action, data, url })
      
      // You can emit events here or use router to navigate
      // router.push(url)
    } else if (event.data.type === 'navigate' && event.data.url) {
      try {
        const url = new URL(event.data.url, location.origin)
        // Navigate within SPA if same origin
        if (url.origin === location.origin) {
          router.push(url.pathname + url.search + url.hash)
        } else {
          // Fallback open
          window.location.href = event.data.url
        }
      } catch (e) {
        console.error('Failed to navigate from SW message:', e)
      }
    }
  }

  onMounted(() => {
    checkInstallStatus()
    registerServiceWorker()
    
    // Update notification permission status
    if ('Notification' in window) {
      notificationPermission.value = Notification.permission
    }

    // Event listeners
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    
    // Special handling for mobile browsers
    window.addEventListener('appinstalled', () => {
      console.log('PWA was installed')
      isInstalled.value = true
      isInstallable.value = false
      installPrompt.value = null
    })
    
    // Check for display mode changes (mobile)
    const mediaQuery = window.matchMedia('(display-mode: standalone)')
    mediaQuery.addEventListener('change', checkInstallStatus)
    
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', handleServiceWorkerMessage)
    }
  })

  onUnmounted(() => {
    window.removeEventListener('online', handleOnline)
    window.removeEventListener('offline', handleOffline)
    window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.removeEventListener('message', handleServiceWorkerMessage)
    }
  })

  return {
    // State
    isInstallable,
    isInstalled,
    isOnline,
    pushSupported,
    notificationPermission,
    registration,
    
    // Methods
    installPWA,
    subscribeToPush,
    unsubscribeFromPush,
    showNotification,
    requestNotificationPermission,
    getPlatformInfo,
    checkPWAInstallCriteria,
    getInstallInstructions
  }
}

// Helper function to convert VAPID key (base64url to Uint8Array)
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  // base64url decode - handle both regular base64 and base64url
  const padding = '='.repeat((4 - base64String.length % 4) % 4)
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/')

  const rawData = window.atob(base64)
  const outputArray = new Uint8Array(rawData.length)

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i)
  }
  return outputArray
}
