/* Minimal service worker: cache app shell for basic offline use. */
const CACHE = 'tms-cache-v1';
const ASSETS = [
  '/',
  '/dashboards',
  '/auth/login',
  '/static/manifest.webmanifest'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((k) => (k !== CACHE ? caches.delete(k) : null)))).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req)
        .then((res) => {
          // Cache same-origin navigations and static assets.
          try {
            const url = new URL(req.url);
            if (url.origin === self.location.origin && (req.mode === 'navigate' || url.pathname.startsWith('/static/'))) {
              const copy = res.clone();
              caches.open(CACHE).then((cache) => cache.put(req, copy));
            }
          } catch (e) {}
          return res;
        })
        .catch(() => cached || new Response('Offline. Please reconnect and retry.', { status: 503 }));
    })
  );
});

