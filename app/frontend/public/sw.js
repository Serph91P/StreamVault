const CACHE_NAME = 'streamvault-v10'
const urlsToCache = [
  '/',
  '/?source=pwa',
  '/?source=pwa&utm_source=homescreen',
  '/?source=shortcut',
  '/index.html',
  '/manifest.json',
  '/manifest.webmanifest',
  '/favicon.ico',
  '/pwa-test.html',
  '/apple-icon-180x180.png',
  '/android-icon-192x192.png',
  '/android-icon-144x144.png',
  '/icon-512x512.png',
  '/maskable-icon-192x192.png',
  '/maskable-icon-512x512.png',
  '/browserconfig.xml',
  // Pre-cache main app routes for offline access
  '/streamers',
  '/videos',
  '/subscriptions',
  '/add-streamer',
  '/settings',
]

// Install event - cache essential resources
self.addEventListener('install', event => {
  console.log('Service Worker installing...')
  self.skipWaiting()
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Caching essential resources')
        return cache.addAll(urlsToCache)
      })
      .catch(err => console.error('Cache addAll failed:', err))
  )
})

// Activate event - clean old caches
self.addEventListener('activate', event => {
  console.log('Service Worker activating...')
  event.waitUntil(
    Promise.all([
      self.clients.claim(),
      caches.keys().then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName !== CACHE_NAME) {
              console.log('Deleting old cache:', cacheName)
              return caches.delete(cacheName)
            }
          })
        )
      })
    ])
  )
})

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url)
  
  // Skip cross-origin requests
  if (url.origin !== self.origin) {
    return
  }
  
  // Skip video streaming requests - let browser handle these directly
  if (url.pathname.includes('/api/videos/stream/') || 
      url.pathname.includes('/api/videos/') ||
      event.request.destination === 'video' ||
      event.request.destination === 'audio' ||
      event.request.headers.get('range')) {
    // Don't intercept video/audio requests or range requests
    console.log('Service Worker: Skipping video/audio request:', url.pathname)
    return
  }
  
  // For API requests (except videos), always use network first
  if (url.pathname.includes('/api/') || url.pathname.includes('/auth/')) {
    console.log('Service Worker: Handling API request:', url.pathname)
    event.respondWith(
      fetch(event.request)
        .catch(error => {
          console.error('Service Worker: API request failed:', error)
          return caches.match(event.request)
        })
    )
    return
  }
  
  // For navigation requests (HTML pages), implement fallback to index.html for SPA routing
  if (event.request.mode === 'navigate') {
    console.log('Service Worker: Handling navigation request:', url.pathname)
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // If we get a successful response, return it
          if (response.ok) {
            return response
          }
          // If not found (404), return index.html for client-side routing
          if (response.status === 404) {
            return caches.match('/index.html') || caches.match('/')
          }
          return response
        })
        .catch(() => {
          // Network failed, return cached index.html for offline support
          return caches.match('/index.html') || caches.match('/')
        })
    )
    return
  }
  
  // For other requests (assets), use cache first with network fallback
  console.log('Service Worker: Handling asset request:', url.pathname)
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          console.log('Service Worker: Serving from cache:', url.pathname)
          return response
        }
        console.log('Service Worker: Fetching from network:', url.pathname)
        return fetch(event.request)
          .catch(error => {
            console.error('Service Worker: Network request failed:', url.pathname, error)
            throw error
          })
      })
      .catch(error => {
        console.error('Service Worker: Cache match failed:', url.pathname, error)
        // Return a fallback response or re-throw
        throw error
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
    vibrate: [200, 100, 200],
    timestamp: Date.now(),
    silent: false,
    actions: []
  }

  // Parse push data if available
  if (event.data) {
    try {
      const data = event.data.json()
      console.log('Service Worker: Push data parsed:', data)
      
      notificationData = {
        ...notificationData,
        title: data.title || notificationData.title,
        body: data.body || notificationData.body,
        icon: data.icon || notificationData.icon,
        badge: data.badge || notificationData.badge,
        tag: data.tag || `streamvault-${data.type || 'notification'}-${Date.now()}`,
        data: data.data || {},
        timestamp: data.timestamp || Date.now()
      }      // Add actions based on notification type
      if (data.type === 'stream_online' || data.type === 'stream_update' || data.type === 'favorite_category') {
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
      } else if (data.type === 'recording_finished') {
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
      } else if (data.type === 'test') {
        notificationData.body = 'Test notification from StreamVault - PWA notifications are working!'
        notificationData.requireInteraction = true
      }
    } catch (e) {
      console.error('Service Worker: Error parsing push data', e)
    }
  }

  console.log('Service Worker: Showing notification with data:', notificationData)
  
  event.waitUntil(
    self.registration.showNotification(notificationData.title, notificationData)
      .then(() => {
        console.log('Service Worker: Notification shown successfully')
      })
      .catch((error) => {
        console.error('Service Worker: Error showing notification:', error)
      })
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
        let url = '/'        // Determine URL based on action and data
        if (action === 'view_stream') {
          // For stream viewing, prefer external Twitch URL if available, otherwise internal
          if (data.url && data.url.includes('twitch.tv')) {
            url = data.url
          } else if (data.internal_url) {
            url = data.internal_url
          } else if (data.streamer_id) {
            url = `/streamer/${data.streamer_id}`
          }
        } else if (action === 'view_recording' && data.streamer_id && data.stream_id) {
          url = `/streamer/${data.streamer_id}/stream/${data.stream_id}/watch`
        } else if (data.url) {
          url = data.url
        }        // Try to focus existing window or open new one
        for (let client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            // If it's a Twitch URL, open in new tab/window
            if (url.includes('twitch.tv')) {
              if (clients.openWindow) {
                return clients.openWindow(url)
              }
            } else {
              // For internal URLs, focus existing window and navigate
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
        }

        // Open new window if no existing one found or for external URLs
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