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
