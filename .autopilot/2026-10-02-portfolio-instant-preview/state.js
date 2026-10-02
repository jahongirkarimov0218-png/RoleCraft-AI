window.STATE =
{
  "slug": "portfolio-instant-preview",
  "dir": "2026-10-02-portfolio-instant-preview",
  "title": "Senior Portfolio Polish, Instant Preview & Linear Issue UVP",
  "mode": "full",
  "depth": "deep",
  "polish": { "rounds": 1, "maxRounds": 3, "status": "done" },
  "tier": "T1",
  "briefFile": "2026-10-02-brief.md",
  "memoryFile": "AGENTS.md",
  "skillDir": "C:/Users/user/.gemini/config/skills/autopilot",
  "startedAt": "2026-10-02T13:20:00+05:00",
  "updatedAt": "2026-10-02T13:26:30+05:00",
  "finishedAt": "2026-10-02T13:26:30+05:00",
  "stages": [
    { "id": "preflight", "status": "done", "startedAt": "2026-10-02T13:20:00+05:00", "finishedAt": "2026-10-02T13:20:30+05:00" },
    { "id": "manifest",  "status": "done", "startedAt": "2026-10-02T13:20:30+05:00", "finishedAt": "2026-10-02T13:21:00+05:00" },
    { "id": "briefing",  "status": "skipped", "note": "полный автомат — самобрифинг" },
    { "id": "spec",      "status": "done", "startedAt": "2026-10-02T13:21:00+05:00", "finishedAt": "2026-10-02T13:21:15+05:00" },
    { "id": "plan",      "status": "done", "startedAt": "2026-10-02T13:21:15+05:00", "finishedAt": "2026-10-02T13:21:30+05:00" },
    { "id": "build",     "status": "done", "startedAt": "2026-10-02T13:21:30+05:00", "finishedAt": "2026-10-02T13:25:30+05:00" },
    { "id": "review",    "status": "done", "startedAt": "2026-10-02T13:25:30+05:00", "finishedAt": "2026-10-02T13:26:00+05:00" },
    { "id": "final",     "status": "done", "startedAt": "2026-10-02T13:26:00+05:00", "finishedAt": "2026-10-02T13:26:30+05:00" }
  ],
  "requirements": {
    "total": 17, "done": 17, "inTicket": 0, "inSpec": 0,
    "placeholder": 0, "deferred": 0, "dropped": 0
  },
  "tickets": [
    {
      "id": "01",
      "title": "Внедрение функции мгновенного предпросмотра (Instant Preview)",
      "requirements": ["R01", "R02", "R03", "R04", "R05", "R06", "R07"],
      "blockedBy": [],
      "wave": 1,
      "zone": ["src/components/feedback-input.tsx", "src/app/page.tsx"],
      "status": "done",
      "startedAt": "2026-10-02T13:21:30+05:00",
      "finishedAt": "2026-10-02T13:24:30+05:00",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0
    },
    {
      "id": "02",
      "title": "Инженерный UVP бейдж, Linear Issue Action Bar и экспорт в Markdown",
      "requirements": ["R08", "R09", "R10", "R11", "R12"],
      "blockedBy": ["01"],
      "wave": 2,
      "zone": ["src/app/page.tsx", "src/components/results/summary-card.tsx"],
      "status": "done",
      "startedAt": "2026-10-02T13:23:00+05:00",
      "finishedAt": "2026-10-02T13:24:30+05:00",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0
    },
    {
      "id": "03",
      "title": "Playwright E2E тесты, валидация Figma Bridge MCP, чистый build и Vercel deploy",
      "requirements": ["R13", "R14", "R15", "R16", "R17"],
      "blockedBy": ["02"],
      "wave": 3,
      "zone": ["e2e/product-flow.spec.ts", "playwright.config.ts"],
      "status": "done",
      "startedAt": "2026-10-02T13:24:30+05:00",
      "finishedAt": "2026-10-02T13:26:00+05:00",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0
    }
  ]
}
