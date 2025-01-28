const CACHE_NAME = 'streamvault-v1'
const urlsToCache = [
  '/',
  '/index.html',
  '/manifest.json',
  '/assets/*'
]

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  )
})

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response
        }
        return fetch(event.request).catch(() => {
          // Return cached version if network fetch fails
          return caches.match(event.request)
        })
      })
  )
})
