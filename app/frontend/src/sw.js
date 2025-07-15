import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';
import { registerRoute } from 'workbox-routing';
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';
// Precache all static assets
precacheAndRoute(self.__WB_MANIFEST);
// Clean up outdated caches
cleanupOutdatedCaches();
// Cache static assets (images, fonts, etc.)
registerRoute(({ request }) => request.destination === 'image', new CacheFirst({
    cacheName: 'images',
    plugins: [
        new ExpirationPlugin({
            maxEntries: 60,
            maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
        }),
    ],
}));
// Cache Google Fonts
registerRoute(({ url }) => url.origin === 'https://fonts.googleapis.com', new StaleWhileRevalidate({
    cacheName: 'google-fonts-stylesheets',
}));
registerRoute(({ url }) => url.origin === 'https://fonts.gstatic.com', new CacheFirst({
    cacheName: 'google-fonts-webfonts',
    plugins: [
        new ExpirationPlugin({
            maxEntries: 30,
            maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
        }),
    ],
}));
// Network first for API requests
registerRoute(({ url }) => url.pathname.startsWith('/api/'), new NetworkFirst({
    cacheName: 'api-cache',
    networkTimeoutSeconds: 10,
    plugins: [
        new ExpirationPlugin({
            maxEntries: 50,
            maxAgeSeconds: 60 * 60 * 24, // 1 day
        }),
    ],
}));
// Push notification handling
self.addEventListener('push', (event) => {
    console.log('Service Worker: Push notification received', event);
    let notificationTitle = 'StreamVault';
    let notificationData = {
        body: 'New notification',
        icon: '/android-icon-192x192.png',
        badge: '/android-icon-96x96.png',
        tag: 'streamvault-notification',
        requireInteraction: false,
        vibrate: [200, 100, 200],
        timestamp: Date.now(),
        silent: false,
        actions: [],
        data: {}
    };
    if (event.data) {
        try {
            const data = event.data.json();
            console.log('Service Worker: Push data parsed:', data);
            notificationTitle = data.title || notificationTitle;
            notificationData = {
                ...notificationData,
                body: data.body || notificationData.body,
                icon: data.icon || notificationData.icon,
                badge: data.badge || notificationData.badge,
                tag: data.tag || `streamvault-${data.type || 'notification'}-${Date.now()}`,
                data: data.data || {},
                timestamp: data.timestamp || Date.now()
            };
            // Add actions based on notification type
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
                ];
            }
            else if (data.type === 'recording_finished') {
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
                ];
            }
            else if (data.type === 'test') {
                notificationData.body = 'Test notification from StreamVault - PWA notifications are working!';
                notificationData.requireInteraction = true;
            }
        }
        catch (e) {
            console.error('Service Worker: Error parsing push data', e);
        }
    }
    console.log('Service Worker: Showing notification with data:', notificationData);
    event.waitUntil(self.registration.showNotification(notificationTitle, notificationData)
        .then(() => {
        console.log('Service Worker: Notification shown successfully');
    })
        .catch((error) => {
        console.error('Service Worker: Error showing notification:', error);
    }));
});
// Notification click handling
self.addEventListener('notificationclick', (event) => {
    console.log('Service Worker: Notification clicked', event);
    const notification = event.notification;
    const action = event.action;
    notification.close();
    if (action === 'dismiss') {
        return;
    }
    event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true })
        .then((clientList) => {
        const data = notification.data || {};
        let url = '/';
        if (action === 'view_stream') {
            if (data.url && data.url.includes('twitch.tv')) {
                url = data.url;
            }
            else if (data.internal_url) {
                url = data.internal_url;
            }
            else if (data.streamer_id) {
                url = `/streamer/${data.streamer_id}`;
            }
        }
        else if (action === 'view_recording' && data.streamer_id && data.stream_id) {
            url = `/streamer/${data.streamer_id}/stream/${data.stream_id}/watch`;
        }
        else if (data.url) {
            url = data.url;
        }
        for (let client of clientList) {
            if (client.url.includes(self.location.origin) && 'focus' in client) {
                if (url.includes('twitch.tv')) {
                    if (self.clients.openWindow) {
                        return self.clients.openWindow(url);
                    }
                }
                else {
                    client.focus();
                    client.postMessage({
                        type: 'NOTIFICATION_CLICK',
                        action: action,
                        data: data,
                        url: url
                    });
                    return;
                }
            }
        }
        if (self.clients.openWindow) {
            return self.clients.openWindow(url);
        }
    }));
});
// Background sync
self.addEventListener('sync', (event) => {
    console.log('Service Worker: Background sync', event.tag);
    if (event.tag === 'background-sync') {
        event.waitUntil(handleBackgroundSync());
    }
});
async function handleBackgroundSync() {
    console.log('Service Worker: Performing background sync');
    // Handle any queued actions when back online
}
