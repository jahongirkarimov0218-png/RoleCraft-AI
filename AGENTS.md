<!-- autopilot:start -->
# RoleCraft AI — Enterprise Job Description Generator

Интеллектуальная SaaS-платформа для найма уровня Enterprise, трансформирующая стандартные HR-описания вакансий в стратегические спецификации должностей на основе методологии Lou Adler Performance-Based Hiring и интерактивного фреймворка Thinking Partner (/prompt-nenujna).

## Проверенные команды

| Команда | Описание |
|---------|----------|
| `npm install` | Установка зависимостей проекта |
| `npm run dev` | Запуск локального dev-сервера (http://localhost:3000) |
| `npm test` | Запуск полного набора автотестов Vitest (85 тестов: движок, UI, безопасность, парсеры, отчёт о нише) |
| `npx playwright test e2e/rolecraft.spec.ts` | Запуск Playwright E2E тестов (7 сценариев, десктоп и мобильный Pixel 5) |
| `npx playwright test e2e/niche-report.spec.ts` | E2E страницы `/niche-report` (6 сценариев × 2 проекта); dev-сервер должен быть запущен с `NICHE_REPORT_ENABLED=true` |
| `npm run build` | Сборка production-билда Next.js App Router |

## Структура проекта

```
d:/portfolio/
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── rolecraft/generate/   # Server-side Route Handler POST: валидация, SSE стриминг
│   │   │   └── analyze/              # API Route Handler анализа фидбека
│   │   ├── globals.css               # Emil Kowalski физика (:active scale 0.98), @media print стили
│   │   ├── (main)/                   # Группа маршрутов продукта (URL не меняются)
│   │   │   ├── layout.tsx            # Базовый макет: шрифты Geist/Inter, метаданные, Header/Footer
│   │   │   └── page.tsx              # Главная страница: управление состоянием, SSE поток, UI RoleCraft
│   │   └── (report)/                 # Отдельный корневой layout (lang="ru", без Header/Footer), ADR 0004
│   │       └── niche-report/page.tsx # Отчёт о выборе ниши: 404 без NICHE_REPORT_ENABLED=true, noindex
│   ├── components/
│   │   ├── rolecraft/                # UI-компоненты RoleCraft генератора
│   │   │   ├── header.tsx            # Enterprise-шапка, статус Thinking Partner, модалка методики
│   │   │   ├── presets-bar.tsx       # Панель 4 отраслевых пресетов с тактильным откликом
│   │   │   ├── rolecraft-form.tsx    # Форма ввода (4 поля), валидация, счетчики (tabular-nums)
│   │   │   ├── thinking-partner-card.tsx # Карточка стратегического анализа: Root Cause & A-Player
│   │   │   ├── shimmer-loader.tsx    # Контекстный скелетон стадий синтеза
│   │   │   ├── streaming-markdown-view.tsx # Стриминг Markdown с бейджами Anti-Persona и Value Prop
│   │   │   ├── action-bar.tsx        # Метрики качества, 1-клик копирование и чистый PDF экспорт
│   │   │   └── index.ts              # Баррель-экспорт компонентов
│   │   ├── niche-report/             # Кнопка печати отчёта о нише
│   │   └── layout/                   # Общие элементы макета (Header, Footer)
│   ├── lib/
│   │   ├── rolecraft/                # Доменный движок генерации и обработки
│   │   │   ├── types.ts              # TypeScript контракты (RoleCraftInput, RoleCraftOutput, etc.)
│   │   │   ├── presets.ts            # 4 enterprise пресета (Staff AI, Growth, Design, Engineering Dir)
│   │   │   ├── anti-slop-filter.ts   # Детекция и очистка HR-клише (cleanAntiSlopText, detectSlopPhrases)
│   │   │   ├── prompt-nenujna-engine.ts # Движок синтеза: LLM + офлайн Fallback + генератор SSE стрима
│   │   │   ├── export-pdf.ts         # Утилита вызова чистого браузерного PDF экспорта
│   │   │   └── index.ts              # Баррель-экспорт библиотеки
│   │   ├── niche-report/             # Отчёт о нише: контракт, валидатор V-01…V-12, гард флага, данные
│   │   └── utils.ts                  # Утилиты классов (clsx, tailwind-merge)
│   └── types/                        # Общие системные типы
├── e2e/
│   ├── rolecraft.spec.ts             # Playwright E2E тесты (загрузка, пресеты, генерация, копирование, PDF, валидация, мобайл)
│   └── niche-report.spec.ts          # E2E отчёта о нише (вердикт, порог, мобайл, 1 лист A4, ссылки, черновик)
├── test/
│   ├── rolecraft/
│   │   ├── engine.test.ts            # Юнит-тесты движка, фильтра клише и генератора (9 тестов)
│   │   └── ui-components.test.ts     # Юнит-тесты компонентов формы, карточек и экшенов (9 тестов)
│   ├── niche-report.test.ts          # Валидатор V-01…V-12, гард флага, данные отчёта (23 теста)
│   └── ...                           # Тесты анализатора, контрактов и безопасности (всего 85 тестов)
├── intent/                          # Intent, spec и plan отчёта о выборе ниши
├── docs/adr/                         # Архитектурные решения (ADR 0001–0004)
├── playwright.config.ts              # Конфигурация Playwright E2E
└── vitest.config.ts                  # Конфигурация Vitest
```

## Архитектура и поток данных

1. **Методология Thinking Partner + Lou Adler Outcome-driven (`/prompt-nenujna`)**:
   - Отказ от бессмысленных HR-шаблонов («5+ лет опыта», «стрессоустойчивость», «дружный коллектив»).
   - **Root Cause Analysis**: Выявление истинной боли бизнеса, стоящей за открытием позиции.
   - **Психология A-Player**: Анализ скрытых страхов сильнейших кандидатов (бюрократия, брошенные PoC) и ключевых драйверов (автономия, реальное влияние).
   - **6-месячный измеримый Impact**: Конкретные цели на 30, 90 и 180 дней вместо абстрактных обязанностей.
   - **🛑 Anti-Persona**: Открытое описание типажей, которым категорически не подходит роль.
   - **🚀 Value Proposition**: Реальное ценностное предложение и гарантии компании.
   - **Фильтр Anti-Slop**: Автоматическая детекция и удаление корпоративного буллшита через `cleanAntiSlopText`.

2. **Мультипровайдерный AI и 100% Offline Intelligent Fallback**:
   - `GEMINI_API_KEY`: Google Gemini 1.5 Flash (`temperature: 0.2`, структурированный JSON).
   - `OPENAI_API_KEY`: OpenAI GPT-4o-mini (`response_format: { type: "json_object" }`).
   - При отсутствии API-ключей или сетевых сбоях активируется **Intelligent Fallback Engine** (`synthesizeOfflineOutcome`): автономный эвристический генератор, определяющий доменный профиль (AI/ML, Growth, Design, Platform) и создающий глубокую детализированную спецификацию без внешних зависимостей.

3. **SSE Стриминг (`/api/rolecraft/generate`)**:
   - Эндпоинт поддерживает протокол Server-Sent Events (`accept: text/event-stream` или `stream: true`).
   - Функция-генератор `generateRoleCraftStream` передает поток текста Markdown порционными чанками с плавным рендерингом в реальном времени, завершая передачу метаданными `done`.

4. **Тактильная физика Emil Kowalski**:
   - Отзывчивые микровзаимодействия: `:active { transform: scale(0.98); }` для всех интерактивных кнопок и карточек пресетов.
   - Запрет на недискретные `transition: all` — строго явные свойства: `transition: transform 120ms cubic-bezier(0.16, 1, 0.3, 1), background-color 150ms ease-out, border-color 150ms ease-out`.
   - Всплывающие модальные окна с keyframes `modalEnter`: масштабирование от 0.96 до 1 с прозрачностью за 200ms `ease-out`.
   - Числовые счетчики символов и метрики оформлены через `tabular-nums` для предотвращения скачков верстки.
   - Высококачественный Enterprise дизайн: палитра Slate/Zinc, 1px деликатные границы (`border-slate-200/90`), нулевой AI-slop (без кислотных градиентов и псевдо-неона).

5. **1-клик копирование Markdown и чистый PDF экспорт (`@media print`)**:
   - Панель `ActionBar` обеспечивает мгновенное копирование чистого Markdown (`navigator.clipboard.writeText`) с тактильной обратной связью: зеленая плашка с состоянием `Copied!` и временный toast.
   - Чистый PDF-экспорт реализован через `triggerCleanPdfExport`: динамическая подстановка имени роли в заголовок страницы и вызов системного диалога печати `window.print()`.
   - Специальные правила `@media print` в `globals.css`: полное скрытие навигации, шапки, футера, кнопок и формы ввода (`display: none !important`), белый контрастный фон `#ffffff`, сохранение верстки на страницах A4 без разрыва блоков (`break-inside: avoid !important`).

## Переменные окружения (Environment Variables)

- `GEMINI_API_KEY`: API ключ Google Gemini (опционально)
- `OPENAI_API_KEY`: API ключ OpenAI (опционально)
- `NICHE_REPORT_ENABLED`: `"true"` включает страницу `/niche-report` (по умолчанию выключена, 404). Это **не** механизм приватности: на публичном деплое включённую страницу откроет любой, кто знает URL. Страница статическая, флаг читается при сборке.
*Примечание: Платформа полностью работоспособна без указания API-ключей благодаря встроенному автономному движку семантического синтеза.*

## Autopilot ishlash tartibi
Sборка ведётся навыком `/autopilot`. Требования, спецификация и таски — в `.autopilot/`.
Прогресс — `.autopilot/dashboard.html`. Правило: требование из `manifest.md`
может снять только пользователь.

Если работа продолжается — скажи «продолжи автопилот»: состояние поднимется
из `.autopilot/state.js`, переспрашивать ничего не нужно.
<!-- autopilot:end -->
