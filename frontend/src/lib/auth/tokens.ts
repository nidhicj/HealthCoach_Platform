// Access token lives in module memory — never localStorage (XSS hardening, ADR-0005 §5).
// Cleared on page refresh; re-acquired via the HttpOnly refresh cookie through /api/auth/refresh.

let _token: string | null = null;

export function getToken(): string | null {
  return _token;
}

export function setToken(token: string): void {
  _token = token;
}

export function clearToken(): void {
  _token = null;
}
