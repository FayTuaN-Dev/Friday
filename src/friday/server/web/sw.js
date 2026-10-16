// L'application du téléphone s'installe comme une app (écran d'accueil). Toujours le réseau
// d'abord (Friday est sur le Pi) ; sans réseau, la dernière page vue s'ouvre quand même.
const CACHE = "friday-v1", PAGES = ["/", "/app.js", "/manifest.webmanifest", "/icone-192.png"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PAGES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return;  // jamais en cache
  e.respondWith(fetch(e.request).then((r) => {
    const copie = r.clone();
    caches.open(CACHE).then((c) => c.put(e.request, copie));
    return r;
  }).catch(() => caches.match(e.request)));
});
