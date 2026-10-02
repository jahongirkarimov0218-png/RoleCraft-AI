# Как читать эту папку

- `dashboard.html` — открывается сам в начале сборки; можно и двойным кликом.
  Этапы, прогресс, время, что осталось. Обновляется сам, пока сборка идёт.
  `index.html` рядом — тот же файл под другим именем, чтобы дашборд открывался
  по короткому адресу. Отдельно его открывать не нужно.
- `<дата>-<проект>/` — папка одной сборки. Дата в имени — день, когда сборка началась,
  поэтому папки идут по порядку сверху вниз. Суффикс `--wip` значит «ещё делается»;
  когда сборка сдана, суффикс снимается. Внутри:
  - `<дата>-brief.md` — твоя изначальная задача, слово в слово, и «Дополнения» — всё,
    что ты сказал позже. Сам текст задачи не переписывается.
  - `manifest.md` — список требований и что с каждым стало.
  - `spec.md` — спецификация.
  - `tickets/` — таски, на которые разбита сборка (если сборка мелкая, их нет).

Если сборка прервалась — скажи агенту «продолжи автопилот», он поднимет состояние отсюда.

## Прогоны

| Начат | Папка | Статус | Итог |
|---|---|---|---|
| 2026-10-02 | `2026-10-02-customer-feedback-ai` | сдан | Mijoz fikrlarini AI orqali tahlil qiluvchi full-stack SaaS platformasi (Next.js, Tailwind, Gemini/OpenAI/Fallback, 33 test) |
| 2026-10-02 | `2026-10-02-feedback-deep-redesign` | сдан | Linear/Raycast darajasidagi chuqur redizayn, 5-soniyalik qaror qabul qilish bloki, 4 ta preset, tabular-nums va Emil Kowalski fizikasi, 44 unit va 4 Playwright E2E test |
| 2026-10-02 | `2026-10-02-linear-ui-and-figma-mcp` | сдан | AI-slop tozalash, Linear/Raycast UI, Figma MCP sozlash, chip-presetlar, Playwright E2E va build muvaffaqiyatli |
| 2026-10-02 | `2026-10-02-portfolio-instant-preview` | сдан | Senior Portfolio Polish, Instant Preview & Linear Issue UVP |
| 2026-10-02 | `2026-10-02-rolecraft-ai-generator` | сдан | RoleCraft AI — Enterprise Job Description Generator (Lou Adler Outcome-Driven, Thinking Partner /prompt-nenujna, Anti-Slop, Emil Kowalski tactile physics, 62 Vitest, 14 Playwright E2E) |
