/* eslint-disable no-restricted-globals */

self.addEventListener('push', (event) => {
  try {
    if (!event || !event.data) return;

    let payload = {};
    try {
      payload = event.data.json();
    } catch (_e) {
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
      vibrate: payload.vibrate || [100, 50, 100],
    };

    event.waitUntil(self.registration.showNotification(title, options));
  } catch (err) {
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

    for (const client of allClients) {
      try {
        const clientUrl = client.url || root;
        if (clientUrl.startsWith(self.location.origin)) {
          await client.focus();
          client.postMessage({ type: 'navigate', url: target });
          return;
        }
      } catch (_) { /* ignore */ }
    }

    await clients.openWindow(target);
  };

  event.waitUntil((async () => {
    try {
      if (action !== 'dismiss') await openOrFocus(targetUrl);
    } finally {
      notification.close();
    }
  })());
});
