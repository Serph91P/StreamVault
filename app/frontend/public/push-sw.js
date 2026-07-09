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

const normalizeNotificationTarget = (data) => {
  const requestedUrl = data.target_url || data.internal_url || data.url || '/';
  let url;

  try {
    url = new URL(requestedUrl, self.location.origin);
  } catch (_error) {
    url = new URL('/', self.location.origin);
  }

  if (url.origin === self.location.origin) {
    const streamerMatch = url.pathname.match(/^\/streamer\/([^/]+)\/?$/);
    if (streamerMatch) {
      url.pathname = `/streamers/${streamerMatch[1]}`;
    }
  }

  return url.href;
};

self.addEventListener('notificationclick', (event) => {
  const notification = event.notification;
  const action = event.action;
  const data = notification && notification.data ? notification.data : {};

  const targetUrl = normalizeNotificationTarget(data);

  const openOrFocus = async (url) => {
    const allClients = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    const root = new URL('/', self.location.origin).href;
    const target = new URL(url, self.location.origin).href;

    // Try focus an existing tab on same origin
    for (const client of allClients) {
      try {
        const clientUrl = client.url || root;
        if (clientUrl.startsWith(self.location.origin)) {
          await client.focus();
          // If router-based SPA, navigate within the app
          // Note: postMessage can be handled by app to navigate
          client.postMessage({ type: 'navigate', url: target });
          return;
        }
      } catch (_) { /* ignore */ }
    }

    // Otherwise open a new window
    await clients.openWindow(target);
  };

  event.waitUntil((async () => {
    try {
      if (action && action !== 'dismiss') {
        await openOrFocus(targetUrl);
      } else if (!action) {
        await openOrFocus(targetUrl);
      }
    } finally {
      notification.close();
    }
  })());
});
