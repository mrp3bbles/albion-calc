// Offline support: our own files are network-first (so updates show up), with the cache as fallback.
// Price API and sync calls go straight to the network.
const CACHE = 'albion-calc-v2';
const SHELL = ['./', 'index.html', 'data.json', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', ev => ev.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener('activate', ev => ev.waitUntil(self.clients.claim()));
self.addEventListener('fetch', ev => {
  if (ev.request.method !== 'GET' || new URL(ev.request.url).origin !== location.origin) return;
  ev.respondWith(fetch(ev.request)
    .then(res => { const copy = res.clone(); caches.open(CACHE).then(c => c.put(ev.request, copy)); return res; })
    .catch(() => caches.match(ev.request, { ignoreSearch: true })));
});
