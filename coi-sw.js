/* Cross-origin isolation for hosts that cannot send response headers.
 *
 * The build needs crossOriginIsolated === true (SharedArrayBuffer, real
 * threads). index.html registers this worker, waits for it to take control,
 * then reloads; from then on every response this worker passes through carries
 * COOP/COEP, so the document is isolated.
 *
 * Requires a secure context (https or localhost) - service workers are not
 * available on plain http over a LAN address.
 */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", event => {
  const request = event.request;
  // a cache-only request for another origin cannot be re-fetched
  if (request.cache === "only-if-cached" && request.mode !== "same-origin") return;

  event.respondWith(
    fetch(request).then(response => {
      // opaque/error responses, and statuses that must not carry a body
      const s = response.status;
      if (s === 0 || s === 204 || s === 205 || s === 304) return response;

      const headers = new Headers(response.headers);
      headers.set("Cross-Origin-Opener-Policy", "same-origin");
      headers.set("Cross-Origin-Embedder-Policy", "require-corp");
      headers.set("Cross-Origin-Resource-Policy", "cross-origin");

      return new Response(response.body, {
        status: s,
        statusText: response.statusText,
        headers,
      });
    })
  );
});
