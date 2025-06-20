const CACHE_NAME = 'streamvault-v2'
const urlsToCache = [
  '/',
  '/index.html',
  '/manifest.json',
  '/assets',
  '/manifest.webmanifest',
  '/favicon.ico',
  '/apple-touch-icon.png',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
  '/assets/index-*.js',
  '/assets/index-*.css',
  '/api/streamers'
]

self.addEventListener('install', event => {
  self.skipWaiting()
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  )
})

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName)
          }
        })
      )
    })
  )
})

self.addEventListener('fetch', event => {
  // Für API-Anfragen immer zuerst das Netzwerk verwenden
  if (event.request.url.includes('/api/')) {
    event.respondWith(
      fetch(event.request)
        .catch(() => {
          return caches.match(event.request)
        })
    )
    return
  }

  // Für andere Anfragen zuerst den Cache prüfen
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response
        }
        return fetch(event.request)
      })
  )
})

// Push event - handle incoming push notifications
self.addEventListener('push', (event) => {
  console.log('Service Worker: Push notification received', event)

  let notificationData = {
    title: 'StreamVault',
    body: 'New notification',
    icon: '/android-icon-192x192.png',
    badge: '/android-icon-96x96.png',
    tag: 'streamvault-notification',
    requireInteraction: false,
    actions: []
  }

  // Parse push data if available
  if (event.data) {
    try {
      const data = event.data.json()
      notificationData = {
        ...notificationData,
        ...data,
        icon: data.icon || notificationData.icon,
        badge: data.badge || notificationData.badge
      }

      // Add actions based on notification type
      if (data.type === 'stream_online') {
        notificationData.actions = [
          {
            action: 'view_stream',
            title: 'View Stream',
            icon: '/android-icon-96x96.png'
          },
          {
            action: 'dismiss',
            title: 'Dismiss'
          }
        ]
      } else if (data.type === 'recording_started') {
        notificationData.actions = [
          {
            action: 'view_recording',
            title: 'View Recording',
            icon: '/android-icon-96x96.png'
          },
          {
            action: 'dismiss',
            title: 'Dismiss'
          }
        ]
      }
    } catch (e) {
      console.error('Service Worker: Error parsing push data', e)
    }
  }

  event.waitUntil(
    self.registration.showNotification(notificationData.title, notificationData)
  )
})

// Notification click event
self.addEventListener('notificationclick', (event) => {
  console.log('Service Worker: Notification clicked', event)

  const notification = event.notification
  const action = event.action
  
  notification.close()

  if (action === 'dismiss') {
    return
  }

  // Handle notification actions
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        const data = notification.data || {}
        let url = '/'

        // Determine URL based on action and data
        if (action === 'view_stream' && data.streamer_id) {
          url = `/streamer/${data.streamer_id}`
        } else if (action === 'view_recording' && data.streamer_id && data.stream_id) {
          url = `/streamer/${data.streamer_id}/stream/${data.stream_id}/watch`
        } else if (data.url) {
          url = data.url
        }

        // Try to focus existing window or open new one
        for (let client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            client.focus()
            client.postMessage({
              type: 'NOTIFICATION_CLICK',
              action: action,
              data: data,
              url: url
            })
            return
          }
        }

        // Open new window if no existing one found
        if (clients.openWindow) {
          return clients.openWindow(url)
        }
      })
  )
})

// Background sync for offline actions
self.addEventListener('sync', (event) => {
  console.log('Service Worker: Background sync', event.tag)

  if (event.tag === 'background-sync') {
    event.waitUntil(
      handleBackgroundSync()
    )
  }
})

async function handleBackgroundSync() {
  console.log('Service Worker: Performing background sync')
  // Handle any queued actions when back online
}