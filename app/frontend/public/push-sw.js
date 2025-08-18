// Custom push and notification click handlers for the generated Workbox SW
// This file is imported by the generated service worker via workbox.importScripts

/* eslint-disable no-restricted-globals */

self.addEventListener('push', (event) => {
  try {
    if (!event || !event.data) return;

    let payload = {};
    try {
      payload = event.data.json();
    } catch (_e) {
      // Fallback for non-JSON payloads
      payload = { title: 'Notification', body: event.data.text() };
    }

    const title = payload.title || 'StreamVault';
    const options = {
      body: payload.body || '',
      icon: payload.icon || '/android-icon-192x192.png',
      badge: payload.badge || '/android-icon-96x96.png',
      tag: payload.tag || undefined,
      data: payload.data || {},
      actions: payload.actions || [],
      requireInteraction: !!payload.requireInteraction,
      // Optional: vibrate pattern for attention
      vibrate: payload.vibrate || [100, 50, 100],
    };

    event.waitUntil(self.registration.showNotification(title, options));
  } catch (err) {
    // Swallow errors to avoid crashing the SW
    // eslint-disable-next-line no-console
    console.error('SW push handler error:', err);
  }
});

self.addEventListener('notificationclick', (event) => {
  const notification = event.notification;
  const action = event.action;
  const data = notification && notification.data ? notification.data : {};

  const internalUrl = data.internal_url || data.url || '/';

  const openOrFocus = async (url) => {
    const allClients = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    const root = new URL('/', self.location.origin).href;
    const targetUrl = new URL(internalUrl, self.location.origin).href;

    // Try focus an existing tab on same origin
    for (const client of allClients) {
      try {
        const clientUrl = client.url || root;
        if (clientUrl.startsWith(self.location.origin)) {
          await client.focus();
          // If router-based SPA, navigate within the app
          // Note: postMessage can be handled by app to navigate
          client.postMessage({ type: 'navigate', url: targetUrl });
          return;
        }
      } catch (_) { /* ignore */ }
    }

    // Otherwise open a new window
    await clients.openWindow(targetUrl);
  };

  event.waitUntil((async () => {
    try {
      if (action && action !== 'dismiss') {
        await openOrFocus(internalUrl);
      } else if (!action) {
        await openOrFocus(internalUrl);
      }
    } finally {
      notification.close();
    }
  })());
});
