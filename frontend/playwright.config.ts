import { defineConfig } from "@playwright/test";

// Runs the UI contract checks against a running app.
// Usage: FRONTEND_URL=https://your-app.vercel.app npm run test:e2e
export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  use: { baseURL: process.env.FRONTEND_URL || "http://localhost:3000" },
});
