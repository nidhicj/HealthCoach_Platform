import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  trailingSlash: true,
  // Allow the dev script to redirect Turbopack's output to a faster filesystem
  // (e.g. /dev/shm on Linux) so the build cache is not on a slow FUSE mount.
  // Production builds leave NEXT_DIST_DIR unset and use the default ".next".
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
};

export default nextConfig;
