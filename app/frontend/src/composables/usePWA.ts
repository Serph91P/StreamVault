import { ref, onMounted, onUnmounted } from 'vue'

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
                       (window.navigator as any).standalone === true
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
      let subscription = await registration.value.pushManager.getSubscription()
      
      if (!subscription) {
        // Generate VAPID keys on server side and use the public key here
        const response = await fetch('/api/push/vapid-public-key')
        const { publicKey } = await response.json()

        subscription = await registration.value.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey)
        })
      }

      // Send subscription to server
      await fetch('/api/push/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          subscription: subscription.toJSON(),
          userAgent: navigator.userAgent
        })
      })

      console.log('Push subscription successful:', subscription)
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
      vibrate: [200, 100, 200],
      tag: 'streamvault-notification',
      ...options
    }

    return registration.value.showNotification(title, defaultOptions)
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
    requestNotificationPermission
  }
}

// Helper function to convert VAPID key
function urlBase64ToUint8Array(base64String: string): Uint8Array {
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
