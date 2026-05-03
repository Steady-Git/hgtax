/* ═══════════════════════════════════════
   MY.zip — Service Worker
   캐시 전략: Cache First (오프라인 지원)
═══════════════════════════════════════ */

const CACHE_NAME = 'myzip-v1';

/* 앱 실행에 필요한 핵심 파일 목록 */
const PRECACHE_URLS = [
  './index.html',
  './portfolio.html',
  './scheduler-annual.html',
  './scheduler-weekly.html',
  './manifest.json',
  './icon-192.png',
  './icon-512.png',
];

/* ── 설치: 핵심 파일 사전 캐시 ── */
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return Promise.allSettled(
        PRECACHE_URLS.map(url =>
          cache.add(url).catch(err => console.warn('[SW] 캐시 실패:', url, err))
        )
      );
    }).then(() => self.skipWaiting())
  );
});

/* ── 활성화: 오래된 캐시 삭제 ── */
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

/* ── 요청 가로채기: Cache First → Network Fallback ── */
self.addEventListener('fetch', event => {
  /* 크로스오리진 요청(Google Fonts 등)은 그냥 통과 */
  if (!event.request.url.startsWith(self.location.origin)) return;

  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;

      return fetch(event.request).then(response => {
        /* 정상 응답만 캐시에 저장 */
        if (response && response.status === 200 && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => {
        /* 오프라인 + 캐시 없음: HTML 요청이면 앱 셸 반환 */
        if (event.request.destination === 'document') {
          return caches.match('./index-hub.html');
        }
      });
    })
  );
});
