// Cache only the generic public recovery shell/assets, NEVER authenticated records.
const CACHE='stocklog-recovery-v1';
const PUBLIC=['/static/herd/recovery.html','/static/herd/offline.js','/static/herd/recovery.js','/static/herd/app.css'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(PUBLIC)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(Promise.all([self.clients.claim(),caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('stocklog-recovery-')&&k!==CACHE).map(k=>caches.delete(k))))])));
self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET')return;
  const path=new URL(event.request.url).pathname;
  if(event.request.mode==='navigate')event.respondWith(fetch(event.request).catch(()=>caches.match('/static/herd/recovery.html')));
  else if(PUBLIC.includes(path))event.respondWith(fetch(event.request).catch(()=>caches.match(event.request)));
});
