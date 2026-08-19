"use client";

/**
 * PHASE-02c final-review fix (Finding 1): message attachments are served from
 * Bearer-token-protected backend endpoints. A plain <img src=...> GET cannot
 * carry an Authorization header — the access token lives only in module
 * memory (frontend/src/lib/auth/tokens.ts, per ADR-0005 §5), and the backend
 * has no cookie-auth fallback (backend/src/auth/dependencies.py's
 * `HTTPBearer(auto_error=False)` 401s without a bearer credential).
 *
 * This component fetches the image via fetchWithAuth (which injects the
 * Bearer token and handles silent refresh) and renders it from a local
 * object URL instead.
 */
import { useEffect, useState } from "react";
import { fetchWithAuth } from "@/lib/auth/client";

interface AuthedImageProps {
  url: string;
  alt: string;
  className?: string;
}

export function AuthedImage({ url, alt, className }: AuthedImageProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let localObjectUrl: string | null = null;

    setObjectUrl(null);
    setFailed(false);

    fetchWithAuth(url)
      .then((res) => {
        if (!res.ok) throw new Error(`Attachment fetch failed: ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        localObjectUrl = URL.createObjectURL(blob);
        setObjectUrl(localObjectUrl);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
      if (localObjectUrl) URL.revokeObjectURL(localObjectUrl);
    };
  }, [url]);

  if (failed) {
    return <p className="font-sans text-xs italic text-muted-foreground">Attachment unavailable</p>;
  }

  if (!objectUrl) return null;

  // eslint-disable-next-line @next/next/no-img-element -- object URL, not a static asset next/image can optimize
  return <img src={objectUrl} alt={alt} className={className} />;
}
