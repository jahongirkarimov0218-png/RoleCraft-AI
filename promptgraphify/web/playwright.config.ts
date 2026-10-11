import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against the real backend and the production build of the web app. No mocks of the
// analyzer: every graph on screen comes from POST /api/analyze.
const API_PORT = Number(process.env.PG_API_PORT ?? 8000);
const WEB_PORT = Number(process.env.PG_WEB_PORT ?? 3100);
// The sandbox ships Chromium outside Playwright's cache; PG_CHROMIUM overrides it for other machines.
const executablePath = process.env.PG_CHROMIUM ?? (process.env.CI ? undefined : "/opt/pw-browsers/chromium-1194/chrome-linux/chrome");

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    launchOptions: { executablePath, args: ["--no-sandbox"] },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } }, grepInvert: /@mobile/ },
    { name: "mobile", use: { ...devices["Pixel 5"] }, grep: /@mobile/ },
  ],
  webServer: [
    {
      command: `../.venv/bin/python -m uvicorn promptgraphify.api.app:app --host 127.0.0.1 --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: `npm run build && npx next start -p ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { PROMPTGRAPHIFY_API_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: true,
      timeout: 240_000,
    },
  ],
});
