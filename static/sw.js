/*
 * QuizWeaver Service Worker
 * Provides offline support and caching for the PWA.
 *
 * Cache-first for static assets (CSS, JS, fonts).
 * Network-first for HTML pages and API calls.
 * Falls back to /offline when the network is unavailable.
 */

var CACHE_VERSION = 'qw-cache-v1';

var STATIC_ASSETS = [
    '/static/css/style.css',
    '/static/css/loading.css',
    '/static/css/accessibility.css',
    '/static/js/loading.js',
    '/static/js/shortcuts.js',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/offline'
];

// Install: pre-cache static assets and the offline page
self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_VERSION).then(function(cache) {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', function(event) {
    event.waitUntil(
        caches.keys().then(function(cacheNames) {
            return Promise.all(
                cacheNames.filter(function(name) {
                    return name !== CACHE_VERSION;
                }).map(function(name) {
                    return caches.delete(name);
                })
            );
        })
    );
    self.clients.claim();
});

// Fetch: choose strategy based on request type
self.addEventListener('fetch', function(event) {
    var url = new URL(event.request.url);

    // Only handle same-origin requests
    if (url.origin !== location.origin) {
        return;
    }

    // Static assets: cache-first
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(event.request).then(function(cached) {
                if (cached) {
                    return cached;
                }
                return fetch(event.request).then(function(response) {
                    if (response.ok) {
                        var responseClone = response.clone();
                        caches.open(CACHE_VERSION).then(function(cache) {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return response;
                });
            })
        );
        return;
    }

    // HTML pages and API calls: network-first with offline fallback
    if (event.request.mode === 'navigate' || event.request.headers.get('Accept').indexOf('text/html') !== -1) {
        event.respondWith(
            fetch(event.request).catch(function() {
                return caches.match('/offline');
            })
        );
        return;
    }

    // All other requests: network-first, fall back to cache
    event.respondWith(
        fetch(event.request).then(function(response) {
            return response;
        }).catch(function() {
            return caches.match(event.request);
        })
    );
});
