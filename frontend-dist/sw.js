self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open("cotai-shell-v4");
    await cache.addAll([
      "/",
      "/dashboard.html",
      "/new-request.html",
      "/requests.html",
      "/projects.html",
      "/settings.html",
      "/manifest.webmanifest",
      "/assets/css/apex.css",
      "/assets/css/base.css",
      "/assets/css/components.css",
      "/assets/css/layout.css",
      "/assets/css/tokens.css",
      "/assets/css/utilities.css",
      "/assets/js/ui.js",
      "/assets/js/app.js",
      "/assets/js/mobileNotifications.js",
      "/assets/favicon.svg",
    ]);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const expected = new Set(["cotai-shell-v4"]);
    const keys = await caches.keys();
    await Promise.all(keys.map((key) => (expected.has(key) ? null : caches.delete(key))));
    await self.clients.claim();
  })());
});

self.addEventListener("message", (event) => {
  const payload = event.data || {};
  if (payload.type !== "SHOW_NOTIFICATION") return;
  const { title = "Cotai", options = {} } = payload;
  event.waitUntil(
    self.registration.showNotification(title, {
      icon: "/assets/favicon.svg",
      badge: "/assets/favicon.svg",
      ...options,
    })
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        const cache = await caches.open("cotai-shell-v4");
        cache.put(request, response.clone());
        return response;
      } catch (_) {
        const cached = await caches.match(request);
        if (cached) return cached;
        return (await caches.match("/dashboard.html")) || new Response("Offline", { status: 503, statusText: "Offline" });
      }
    })());
    return;
  }

  if (url.pathname.startsWith("/assets/") || url.pathname === "/manifest.webmanifest") {
    event.respondWith((async () => {
      const cache = await caches.open("cotai-shell-v4");
      const cached = await cache.match(request);
      const networkFetch = fetch(request)
        .then((response) => {
          cache.put(request, response.clone());
          return response;
        })
        .catch(() => cached);
      return cached || networkFetch;
    })());
  }
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification?.data?.url || "/requests.html";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
      return undefined;
    })
  );
});
