/**
 * BFF proxy — all /api/* requests from the browser land here, then are
 * forwarded server-to-server to the FastAPI backend.
 *
 * Why: run.app is in the Public Suffix List, making frontend and backend
 * cross-site. Firefox (Total Cookie Protection) and Safari (ITP) block
 * third-party cookies, so the refresh cookie must live on the frontend domain.
 * This proxy makes all browser requests same-origin; the cookie is attributed
 * to hc-platform-frontend-*.run.app instead of the backend domain.
 *
 * For the OAuth callback (backend returns 302 + Set-Cookie), we intercept the
 * redirect, copy the Set-Cookie onto the frontend domain, and re-emit the 302.
 */

import { type NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// RFC 2616 §13.5.1 — strip hop-by-hop headers before forwarding
const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
]);

type Ctx = { params: Promise<{ path: string[] }> };

async function handler(req: NextRequest, { params }: Ctx): Promise<Response> {
  const { path } = await params;
  const target = `${BACKEND}/api/${path.join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  req.headers.forEach((v, k) => {
    if (!HOP_BY_HOP.has(k) && k !== "host") headers.set(k, v);
  });

  const init: RequestInit & { duplex?: string } = {
    method: req.method,
    headers,
    redirect: "manual",
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    init.duplex = "half"; // required for streaming body in Node.js fetch
  }

  const upstream = await fetch(target, init);

  // OAuth callback: backend returns 302 + Set-Cookie on the backend domain.
  // Re-emit as a redirect with Set-Cookie so the browser attributes the cookie
  // to the frontend domain (hc-platform-frontend-*.run.app).
  if (upstream.status >= 300 && upstream.status < 400) {
    const location = upstream.headers.get("location") ?? "/";
    const res = NextResponse.redirect(location, upstream.status);
    upstream.headers.getSetCookie().forEach((c) => res.headers.append("set-cookie", c));
    return res;
  }

  const resHeaders = new Headers();
  upstream.headers.forEach((v, k) => {
    if (!HOP_BY_HOP.has(k)) resHeaders.set(k, v);
  });

  return new Response(upstream.body, {
    status: upstream.status,
    headers: resHeaders,
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
export const OPTIONS = handler;
