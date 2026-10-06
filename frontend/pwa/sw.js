/* ============================================================
   Butler 翻译 PWA Service Worker
   - 静态资源：缓存优先 + 后台更新（离线可打开 UI，不白屏）
   - /api/* ：网络优先；后端不可达时返回明确中文 JSON 错误
   ============================================================ */
"use strict";

const CACHE_NAME = "butler-pwa-v1";
const ASSETS = [
  "./",
  "./index.html",
  "./app.js",
  "./styles.css",
  "./manifest.webmanifest",
  "./icon.svg",
  "./icon-maskable.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") {
    return; // 非 GET（POST /api/translate 等）直接走网络
  }

  const url = new URL(req.url);

  // API：网络优先，失败时给出结构化离线错误
  if (url.pathname.indexOf("/api/") === 0 && url.origin === self.location.origin) {
    event.respondWith(
      fetch(req).catch(() => new Response(
        JSON.stringify({
          error: "当前离线或后端不可达：请确认已运行 python3 frontend/pwa/server.py --port 8766",
          offline: true,
        }),
        { status: 503, headers: { "Content-Type": "application/json; charset=utf-8" } }
      ))
    );
    return;
  }

  // 静态资源：缓存优先 + 后台刷新
  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((res) => {
          if (res && res.status === 200 && res.type === "basic") {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          }
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
