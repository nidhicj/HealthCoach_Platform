/**
 * tapas-domain-proxy
 *
 * Rewrites requests arriving at app.tapas.fitness (via Cloudflare's proxy)
 * to target the real Cloud Run origin hostname, both as the fetch target
 * and as the Host header the origin receives. Cloud Run's front door routes
 * purely by Host header — without this rewrite it doesn't recognize
 * app.tapas.fitness and returns a generic 404.
 *
 * Everything else (method, headers, body, streaming, cookies) passes through
 * unmodified — this is a transparent reverse proxy, not a content transform.
 *
 * See docs/decisions/0008-custom-domain-cloudflare-worker.md for the
 * decision record (why a Worker, not CF Origin Rules [Enterprise-only] or
 * Cloud Run Domain Mapping [unsupported in asia-south1]).
 */

export default {
  async fetch(request, env) {
    const originalUrl = new URL(request.url);
    const originUrl = new URL(request.url);
    originUrl.hostname = env.ORIGIN_HOSTNAME;

    // Clone headers and rewrite Host so the origin's front door matches on
    // its own hostname instead of app.tapas.fitness.
    const headers = new Headers(request.headers);
    headers.set("Host", env.ORIGIN_HOSTNAME);

    // Preserve the original public hostname for the app to see, in case
    // it ever needs it (e.g. building absolute URLs, redirect targets).
    // X-Forwarded-Host/Proto are the standard convention for this.
    headers.set("X-Forwarded-Host", originalUrl.hostname);
    headers.set("X-Forwarded-Proto", "https");

    const originRequest = new Request(originUrl.toString(), {
      method: request.method,
      headers,
      body: request.body,
      redirect: "manual", // don't let fetch() silently follow redirects —
                           // pass the origin's redirect straight back to the
                           // client so relative Location headers stay correct
    });

    return fetch(originRequest);
  },
};
