// Runtime config wins (Docker writes window.__APP_CONFIG__ via /env.js),
// then build-time Vite env vars (Vercel), then local defaults.

declare global {
  interface Window {
    __APP_CONFIG__?: { API_URL?: string; USER_NAME?: string; ORB_BASE_URL?: string };
  }
}

const runtime = (typeof window !== "undefined" && window.__APP_CONFIG__) || {};

function clean(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

export const API_URL = clean(
  runtime.API_URL || (import.meta.env.VITE_API_URL as string | undefined) || "http://localhost:8000",
);

export const USER_NAME =
  runtime.USER_NAME || (import.meta.env.VITE_USER_NAME as string | undefined) || "Ankit";

export const ORB_BASE_URL = clean(
  runtime.ORB_BASE_URL || (import.meta.env.VITE_ORB_BASE_URL as string | undefined) || "/orb",
);

export const MAX_MESSAGE_CHARS = 4000;
