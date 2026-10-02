# Границы и интерфейсы (interfaces.md)

## Проектные правила
- Стек: Next.js 14 App Router, React 18, TypeScript, Tailwind CSS, Lucide React, Vitest, Playwright.
- Команды: `npm run build`, `npm test` (vitest), `npm run test:e2e` (playwright).
- Никаких внешних секретов для базовой работы: Intelligent Fallback / Heuristic Engine работает 100% автономно при отсутствии API ключей.
- Дизайн: Emil Kowalski mikromotion (`:active { transform: scale(0.98); }`, никаких `transition: all`, только явные свойства), Impeccable (8px grid, Geist/Inter), Taste (Slate/Zinc, 1px subtle borders, zero AI-slop).

## Границы, решённые в спецификации

### Модуль 1: Core Engine (`src/lib/rolecraft/`)
- **Владеет:** Типизацией (`RoleCraftInput`, `RoleCraftOutput`), анти-слоп фильтрами (`anti-slop-filter.ts`), 4 готовыми пресетами (`presets.ts`), и семантическим генератором Thinking Partner + Lou Adler (`prompt-nenujna-engine.ts`).
- **Экспортирует:**
  - `generateRoleCraftOutcome(input: RoleCraftInput): Promise<RoleCraftOutput>`
  - `cleanAntiSlopText(text: string): { cleaned: string; replacedPhrases: string[] }`
  - `ROLECRAFT_PRESETS: RoleCraftPreset[]`
- **Скрывает:** Внутренние шаблоны промптов, эвристики семантического анализа, fallback генератор, парсинг ответов LLM.

### Модуль 2: API Route Handler (`src/app/api/rolecraft/generate/`)
- **Владеет:** Валидацией входящих данных, SSE / chunked streaming и fallback HTTP ответами.
- **Экспортирует:**
  - `POST /api/rolecraft/generate`: принимает `{ roleTitle, companyContext, coreBusinessPain, techStackAndSkills }`, возвращает либо SSE stream, либо JSON `{ success: true, data: RoleCraftOutput }`.

### Модуль 3: UI Komponentlar (`src/components/rolecraft/`)
- **Владеет:** Интерактивной формой, Thinking Partner карточкой, Streaming Markdown рендерером с тактильным копированием и экспортными действиями.
- **Экспортирует:**
  - `<RoleCraftForm onGenerate={...} isLoading={...} />`
  - `<ThinkingPartnerCard data={output.thinkingPartner} />`
  - `<StreamingMarkdownView markdown={output.jobDescriptionMarkdown} />`
  - `<ActionBar onCopy={...} onExportPdf={...} />`
  - `<PresetsBar onSelect={...} />`
- **Скрывает:** Локальные состояния таймеров, тактильные микро-анимации, clipboard API вызовы.

### Модуль 4: E2E Тесты (`e2e/rolecraft.spec.ts`)
- **Владеет:** Проверкой пользовательского пути: выбор пресета -> валидация -> генерация -> чтение Markdown -> копирование с тактильным откликом -> PDF диалог.

## Что построено в Таске 01
- `src/lib/rolecraft/` полностью готов и протестирован (9 unit тестов).
- Экспорты: `generateRoleCraftOutcome`, `cleanAntiSlopText`, `detectSlopPhrases`, `ROLECRAFT_PRESETS`, типы `RoleCraftInput`, `RoleCraftOutput`, `ThinkingPartnerAnalysis`, `RoleCraftPreset`.
- `POST /api/rolecraft/generate` работает со стримингом и fallback режимом. Тесты зелёные (53 passed). Commit: `96fcc57`.

## Что построено в Таске 02
- `src/components/rolecraft/` полностью реализован:
  - `RoleCraftHeader` с enterprise стилизацией и модальным окном манифеста.
  - `PresetsBar` с 4 пресетами и тактильным откликом.
  - `RoleCraftForm` с валидацией, счетчиками символов (`tabular-nums`) и CTA кнопкой `:active { transform: scale(0.98); }`.
  - `ThinkingPartnerCard` с 3 измерениями (Root Cause, A-Player психология: страхи vs драйверы).
  - `ShimmerLoader` контекстный скелетон.
  - `StreamingMarkdownView` с бейджами 🛑 Anti-Persona и 🚀 Value Proposition.
  - `ActionBar` с 1-клик копированием Markdown и чистым экспортом PDF.
- Стили `src/app/globals.css` обогащены `@media print` стилями и Emil Kowalski физикой.
- `src/app/page.tsx` объединен со стримингом и управлением состоянием. Тесты: 62 passed, build: green. Commit: `d5606ba`.

## Что построено в Таске 03
- `e2e/rolecraft.spec.ts` с 7 сценариями тестирования: загрузка, выбор 4 пресетов, генерация, 1-клик копирование с тактильным текстом "Copied!", PDF экспорт, валидация ошибок, мобильная адаптивность (Pixel 5, 375px).
- Прогон тестов: Playwright 20/20 passed, Vitest 62/62 passed, `npm run build` green. Commit: `02958be`.
