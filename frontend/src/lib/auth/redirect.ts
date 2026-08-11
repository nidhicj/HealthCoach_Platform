import { API_URL } from "@/lib/config";

// Fetches the Google OAuth URL from the backend and redirects the browser to it.
// The backend callback at /api/auth/google/callback will set the refresh cookie
// and redirect back to /auth/callback on the frontend.
export async function redirectToGoogle(): Promise<void> {
  const res = await fetch(`${API_URL}/api/auth/google/start`);
  if (!res.ok) throw new Error("Failed to start Google OAuth flow");
  const { auth_url } = await res.json();
  window.location.href = auth_url;
}

// Fetches the Google OAuth URL for a client invite token and redirects the browser to it.
// The backend validates the invite (exists, unused, unexpired) before returning the URL;
// an invalid/used/expired token results in a non-2xx response, surfaced as a thrown Error.
export async function redirectToClientInviteFlow(inviteToken: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/auth/client/start?invite=${encodeURIComponent(inviteToken)}`);
  if (!res.ok) throw new Error("Invalid or expired invite link");
  const { auth_url } = await res.json();
  window.location.href = auth_url;
}
