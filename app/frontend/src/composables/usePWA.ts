import { ref, onMounted, onUnmounted } from 'vue'
import router from '@/router'
import { normalizeNotificationTargetUrl } from '@/types/events'

interface PWAInstallPrompt {
  prompt(): Promise<void>
  userChoice: Promise<{outcome: 'accepted' | 'dismissed'}>
}

interface NotificationPermission {
  state: 'granted' | 'denied' | 'default'
}

export type PushState = 'unsubscribed' | 'subscribed' | 'checking' | 'subscribing' | 'error'
export type PWAInstallResult = 'accepted' | 'dismissed' | 'installed' | 'unavailable' | 'error'

export function usePWA() {
  const isInstallable = ref(false)
  const isInstalled = ref(false)
  const isOnline = ref(navigator.onLine)
  const registration = ref<ServiceWorkerRegistration | null>(null)
  const installPrompt = ref<PWAInstallPrompt | null>(null)
  const pushSupported = ref('serviceWorker' in navigator && 'PushManager' in window)
  const notificationPermission = ref<NotificationPermission['state']>('default')
  const pushState = ref<PushState>('unsubscribed')
  const pushError = ref<string | null>(null)
  const installError = ref<string | null>(null)
  const existingSubscription = ref<PushSubscription | null>(null)

  const subscriptionUsesApplicationServerKey = (
    subscription: PushSubscription,
    applicationServerKey: Uint8Array
  ): boolean => {
    const subscriptionKey = subscription.options?.applicationServerKey
    if (!subscriptionKey) return false

    const currentKey = new Uint8Array(subscriptionKey)
    if (currentKey.length !== applicationServerKey.length) return false

    return currentKey.every((value, index) => value === applicationServerKey[index])
  }

  const checkInstallStatus = () => {
    isInstalled.value = window.matchMedia('(display-mode: standalone)').matches ||
                       (window.navigator as any).standalone === true ||
                       window.matchMedia('(display-mode: fullscreen)').matches ||
                       window.matchMedia('(display-mode: minimal-ui)').matches
  }

  const resolveServiceWorkerRegistration = async () => {
    if (!('serviceWorker' in navigator)) {
      return null
    }

    try {
      const existingRegistration = await navigator.serviceWorker.getRegistration()
      if (existingRegistration) {
        registration.value = existingRegistration
        return existingRegistration
      }

      const readyRegistration = await navigator.serviceWorker.ready
      registration.value = readyRegistration
      return readyRegistration
    } catch (error) {
      console.error('Service Worker registration unavailable:', error)
      return null
    }
  }

  const installPWA = async (): Promise<PWAInstallResult> => {
    installError.value = null

    if (isInstalled.value) {
      return 'installed'
    }

    if (!installPrompt.value) {
      installError.value = 'The browser install prompt is not available right now. Follow the setup guide for manual install steps.'
      return 'unavailable'
    }

    try {
      await installPrompt.value.prompt()
      const choiceResult = await installPrompt.value.userChoice

      isInstallable.value = false
      installPrompt.value = null

      if (choiceResult.outcome === 'accepted') {
        return 'accepted'
      }

      installError.value = 'Install was dismissed. You can return here and try again when the browser offers the install prompt.'
      return 'dismissed'
    } catch (error) {
      console.error('PWA installation failed:', error)
      installError.value = 'Installation failed. Follow the setup guide or try again from your browser menu.'
      isInstallable.value = false
      installPrompt.value = null
      return 'error'
    }
  }

  const requestNotificationPermission = async (): Promise<NotificationPermission['state']> => {
    if (!('Notification' in window)) {
      notificationPermission.value = 'denied'
      return 'denied'
    }

    let permission = Notification.permission

    if (permission === 'default') {
      permission = await Notification.requestPermission()
    }

    notificationPermission.value = permission
    return permission
  }

  const sendSubscriptionToServer = async (subscription: PushSubscription): Promise<boolean> => {
    try {
      const subscriptionData = {
        subscription: subscription.toJSON(),
        userAgent: navigator.userAgent
      }

      const response = await fetch('/api/push/subscribe', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(subscriptionData)
      })

      return response.ok
    } catch {
      return false
    }
  }

  const fetchVapidPublicKey = async (): Promise<string | null> => {
    try {
      const response = await fetch('/api/push/vapid-public-key', {
        credentials: 'include'
      })
      if (!response.ok) return null
      const { publicKey } = await response.json()
      return publicKey
    } catch {
      return null
    }
  }

  const checkExistingSubscription = async (): Promise<PushSubscription | null> => {
    if (!registration.value || !pushSupported.value) {
      pushState.value = 'unsubscribed'
      return null
    }

    pushState.value = 'checking'

    try {
      const sub = await registration.value.pushManager.getSubscription()
      existingSubscription.value = sub

      if (sub) {
        const publicKey = await fetchVapidPublicKey()
        if (publicKey && !subscriptionUsesApplicationServerKey(sub, urlBase64ToUint8Array(publicKey))) {
          pushState.value = 'error'
          pushError.value = 'Subscription uses an old push key. Click Retry to renew it.'
          return sub
        }

        const success = await sendSubscriptionToServer(sub)
        if (success) {
          pushState.value = 'subscribed'
          pushError.value = null
        } else {
          pushState.value = 'error'
          pushError.value = 'Failed to sync subscription with server'
        }
        return sub
      } else {
        pushState.value = 'unsubscribed'
        return null
      }
    } catch (error) {
      console.error('Failed to check push subscription:', error)
      pushState.value = 'unsubscribed'
      return null
    }
  }

  const subscribeToPush = async (): Promise<PushSubscription | null> => {
    if (!registration.value || !pushSupported.value) {
      return null
    }

    if (!('Notification' in window) || Notification.permission !== 'granted') {
      return null
    }

    pushState.value = 'subscribing'
    pushError.value = null

    try {
      const publicKey = await fetchVapidPublicKey()
      if (!publicKey) {
        throw new Error('Could not fetch VAPID public key')
      }

      const applicationServerKey = urlBase64ToUint8Array(publicKey)

      let subscription = await registration.value.pushManager.getSubscription()

      if (subscription && !subscriptionUsesApplicationServerKey(subscription, applicationServerKey)) {
        await subscription.unsubscribe()
        subscription = null
      }

      if (!subscription) {
        subscription = await registration.value.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: applicationServerKey as unknown as BufferSource
        })
      }

      const serverSuccess = await sendSubscriptionToServer(subscription)
      if (!serverSuccess) {
        throw new Error('Failed to register subscription with server')
      }

      existingSubscription.value = subscription
      pushState.value = 'subscribed'
      return subscription
    } catch (error) {
      console.error('Push subscription failed:', error)

      const errorMessage = error instanceof Error ? error.message : 'Push subscription failed'
      pushError.value = errorMessage
      pushState.value = 'error'
      return null
    }
  }

  const unsubscribeFromPush = async (): Promise<boolean> => {
    if (!registration.value) {
      return false
    }

    try {
      const subscription = await registration.value.pushManager.getSubscription()
      if (subscription) {
        await subscription.unsubscribe()

        await fetch('/api/push/unsubscribe', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            endpoint: subscription.endpoint
          })
        })
      }

      existingSubscription.value = null
      pushState.value = 'unsubscribed'
      pushError.value = null
      return true
    } catch (error) {
      console.error('Push unsubscription failed:', error)
      return false
    }
  }

  const showNotification = async (title: string, options: NotificationOptions = {}) => {
    if (!registration.value) {
      return
    }

    if (!('Notification' in window) || Notification.permission !== 'granted') {
      return
    }

    const defaultOptions: NotificationOptions = {
      icon: '/android-icon-192x192.png',
      badge: '/android-icon-96x96.png',
      tag: 'streamvault-notification',
      ...options
    }

    if ('vibrate' in navigator && navigator.vibrate) {
      navigator.vibrate([200, 100, 200])
    }

    return registration.value.showNotification(title, defaultOptions)
  }

  const getPlatformInfo = () => {
    const userAgent = navigator.userAgent

    let platform = 'Unknown'
    let browser = 'Unknown'

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

  const checkPWAInstallCriteria = () => {
    const criteria = {
      hasManifest: !!document.querySelector('link[rel="manifest"]'),
      hasServiceWorker: 'serviceWorker' in navigator,
      hasHTTPS: location.protocol === 'https:' || location.hostname === 'localhost',
      hasIcons: true,
      hasStartUrl: true,
      hasName: true,
      hasDisplay: true
    }

    const allCriteriaMet = Object.values(criteria).every(Boolean)
    return { criteria, allCriteriaMet }
  }

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

  const handleOnline = () => {
    isOnline.value = true
  }

  const handleOffline = () => {
    isOnline.value = false
  }

  const handleBeforeInstallPrompt = (event: Event) => {
    event.preventDefault()
    installPrompt.value = event as any
    isInstallable.value = true
  }

  const handleServiceWorkerMessage = (event: MessageEvent) => {
    if (event.data.type === 'navigate' && event.data.url) {
      try {
        const normalizedTarget = normalizeNotificationTargetUrl(event.data.url)
        const url = new URL(normalizedTarget, location.origin)
        if (url.origin === location.origin) {
          router.push(url.pathname + url.search + url.hash)
        } else {
          window.location.href = event.data.url
        }
      } catch (e) {
        console.error('Failed to navigate from SW message:', e)
      }
    }
  }

  onMounted(() => {
    checkInstallStatus()
    resolveServiceWorkerRegistration().then(() => {
      checkExistingSubscription()
    })

    if ('Notification' in window) {
      notificationPermission.value = Notification.permission
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)

    window.addEventListener('appinstalled', () => {
      isInstalled.value = true
      isInstallable.value = false
      installPrompt.value = null
    })

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
    isInstallable,
    isInstalled,
    isOnline,
    pushSupported,
    notificationPermission,
    registration,
    pushState,
    pushError,
    installError,
    existingSubscription,

    installPWA,
    subscribeToPush,
    unsubscribeFromPush,
    showNotification,
    requestNotificationPermission,
    checkExistingSubscription,
    getPlatformInfo,
    checkPWAInstallCriteria,
    getInstallInstructions
  }
}

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
