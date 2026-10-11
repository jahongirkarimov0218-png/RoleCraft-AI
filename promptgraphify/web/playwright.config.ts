import { existsSync } from "node:fs";
import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against the real backend and the production build of the web app. No mocks of the
// analyzer: every graph on screen comes from POST /api/analyze.
const API_PORT = Number(process.env.PG_API_PORT ?? 8000);
const WEB_PORT = Number(process.env.PG_WEB_PORT ?? 3100);
const LLM_PORT = Number(process.env.PG_FAKE_LLM_PORT ?? 8002);
// PG_CHROMIUM names a Chromium binary explicitly. Otherwise the sandbox's pre-installed one is used when it exists;
// everywhere else Playwright's own browser (`npx playwright install chromium`) is used.
const SANDBOX_CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const executablePath = process.env.PG_CHROMIUM ?? (existsSync(SANDBOX_CHROMIUM) ? SANDBOX_CHROMIUM : undefined);
// The API runs from the virtual environment `uv sync` creates; PG_PYTHON points at another interpreter.
const python = process.env.PG_PYTHON ?? "../.venv/bin/python";

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
      // A fake OpenAI-compatible provider on loopback: the backend below is configured to use it, so the optional
      // LLM layer is exercised end to end (HTTP, verifier, UI) without any external network or key.
      command: "node e2e/fake-llm.mjs",
      url: `http://127.0.0.1:${LLM_PORT}/__stats`,
      env: { PG_FAKE_LLM_PORT: String(LLM_PORT) },
      reuseExistingServer: Boolean(process.env.PG_REUSE_SERVER),
    },
    {
      command: `${python} -m uvicorn promptgraphify.api.app:app --host 127.0.0.1 --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      env: {
        PROMPTGRAPHIFY_LLM_PROVIDER: "openai-compatible",
        PROMPTGRAPHIFY_LLM_BASE_URL: `http://127.0.0.1:${LLM_PORT}/v1`,
        PROMPTGRAPHIFY_LLM_MODEL: "fake-model",
        PROMPTGRAPHIFY_LLM_API_KEY: "e2e-not-a-real-key",
      },
      // A stale server on the port would silently test old code: fail loudly unless asked to reuse it.
      reuseExistingServer: Boolean(process.env.PG_REUSE_SERVER),
      timeout: 60_000,
    },
    {
      command: `npm run build && npx next start -p ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { PROMPTGRAPHIFY_API_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: Boolean(process.env.PG_REUSE_SERVER),
      timeout: 240_000,
    },
  ],
});
