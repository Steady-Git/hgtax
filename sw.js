// ══════════════════════════════════════════
//  MY.zip — Service Worker
//  전략: Stale-While-Revalidate
//  (캐시 먼저 응답 + 백그라운드 갱신 → 다음 방문 시 최신 버전 보장)
// ══════════════════════════════════════════

const CACHE_NAME = 'myzip-v1';

const CACHE_URLS = [
  '/',
  '/index.html',
  '/portfolio.html',
  '/scheduler-annual.html',
  '/scheduler-weekly.html',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png'
];

// ── 설치: 핵심 파일 사전 캐시 ──
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return Promise.allSettled(
        CACHE_URLS.map(url =>
          cache.add(url).catch(err => console.warn('[SW] 캐시 실패:', url, err))
        )
      );
    }).then(() => self.skipWaiting())  // 즉시 활성화
  );
});

// ── 활성화: 이전 버전 캐시 자동 삭제 ──
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key !== CACHE_NAME)  // 현재 버전 외 전부 삭제
          .map(key => {
            console.log('[SW] 구 캐시 삭제:', key);
            return caches.delete(key);
          })
      )
    ).then(() => self.clients.claim())  // 열린 탭 즉시 제어
  );
});

// ── Fetch: Stale-While-Revalidate ──
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // 외부 요청(Google Fonts 등)은 그냥 통과
  if (url.origin !== location.origin) return;

  event.respondWith(
    caches.open(CACHE_NAME).then(cache => {
      return cache.match(event.request).then(cached => {

        // 백그라운드에서 네트워크 요청 → 캐시 갱신
        const fetchPromise = fetch(event.request).then(response => {
          if (response && response.status === 200) {
            cache.put(event.request, response.clone());
          }
          return response;
        }).catch(() => null);

        // 캐시 있으면 즉시 반환 (동시에 백그라운드 갱신)
        // 캐시 없으면 네트워크 응답 대기
        return cached || fetchPromise || cache.match('/index.html');
      });
    })
  );
});
