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