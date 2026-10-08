/**
 * WildStep AI — Service Worker (Application Shell)
 * Developer & Maintainer: Nainish Jaiswal
 *
 * Local-first, privacy-respecting service worker providing an offline
 * application shell for WildStep AI.
 *
 * Privacy & Security Constraints:
 * - Strictly caches static application shell assets only.
 * - NEVER caches API requests (/api/*).
 * - NEVER caches POST requests (/api/check, /api/quests, etc.).
 * - NEVER stores user photos in service worker cache.
 * - Zero third-party or external domain interception.
 */

const CACHE_NAME = 'wildstep-shell-v1';

const SHELL_ASSETS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/icon-192.png',
  '/icon-512.png',
  '/icon.svg',
  '/icon-maskable-192.png',
  '/icon-maskable-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(SHELL_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((k) => k.startsWith('wildstep-') && k !== CACHE_NAME)
            .map((k) => caches.delete(k))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  // Only handle GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  const url = new URL(event.request.url);

  // Strictly same-origin
  if (url.origin !== self.location.origin) {
    return;
  }

  // Never intercept or cache API requests — live local server required for Ollama / health
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  // Stale-while-revalidate for application shell assets and navigation
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetchPromise = fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const toCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, toCache);
          });
        }
        return networkResponse;
      }).catch(() => {
        // Fallback for navigation when completely offline
        if (event.request.mode === 'navigate') {
          return cached || caches.match('/index.html') || caches.match('/');
        }
        return cached;
      });

      return cached || fetchPromise;
    })
  );
});
