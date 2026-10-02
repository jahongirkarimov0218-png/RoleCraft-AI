# Таск 01: Core Domain Engine, Types, Anti-Slop Filter & Streaming API

> Волна: 1 · Зона: `src/lib/rolecraft/`, `src/app/api/rolecraft/`, `test/rolecraft/`
> Блокирует: 02
> Требования: R01, R02, R03, R04, R05, R06, R07, R08, R19, R20, R24i, R25i

## Что сделать
1. Создать `src/lib/rolecraft/types.ts`:
   - `RoleCraftInput`: `roleTitle`, `companyContext`, `coreBusinessPain`, `techStackAndSkills`
   - `ThinkingPartnerAnalysis`: `rootProblemAnalysis`, `candidateFearsAndDrivers`, `strategicAngle`
   - `RoleCraftOutput`: `thinkingPartner`, `jobDescriptionMarkdown`, `rawMetrics`
   - `RoleCraftPreset`: `id`, `name`, `badge`, `input`: `RoleCraftInput`
2. Создать `src/lib/rolecraft/presets.ts`:
   - 4 эталонных enterprise пресета:
     - `staff-ai-engineer`: "Staff AI / LLM Architect" (Series B GenAI platform, PoC trap, production scaling)
     - `head-of-growth`: "Head of Growth Engineering" (Post-PMF SaaS, funnel drops, data-informed experimentation)
     - `lead-product-designer`: "Lead Product Designer (Design Systems)" (Enterprise SaaS, UI inconsistency, multi-product scale)
     - `director-engineering`: "Engineering Director (Platform & Reliability)" (High-load Fintech, legacy monolith to services, zero-downtime)
3. Создать `src/lib/rolecraft/anti-slop-filter.ts`:
   - Словарь и эвристики для детекции и замены 15+ токсичных HR-клише ("динамичный коллектив", "стрессоустойчивость", "печеньки и кофе", "5+ лет опыта") на бизнес-импакт метрики и реальные результаты.
4. Создать `src/lib/rolecraft/prompt-nenujna-engine.ts`:
   - Thinking Partner семантический генератор:
     - Анализ скрытой боли бизнеса (Root Cause)
     - Психология A-Player (страхи бюрократии, потребность в автономности)
     - Lou Adler Outcome-driven структура (6-Month Deliverables, Track Record, 🛑 Anti-Persona, 🚀 Value Proposition)
     - Поддержка Gemini / OpenAI (если ключи есть) + 100% надежный Offline Heuristic Synthesis Engine (без ключей работает безупречно).
5. Создать `src/app/api/rolecraft/generate/route.ts`:
   - POST эндпоинт, валидация полей (минимум 3 символа для роли, 10 символов для контекста/боли).
   - Поддержка как SSE потока (Server-Sent Events) для плавного стриминга, так и JSON fallback.
6. Написать Vitest тесты в `test/rolecraft/engine.test.ts`:
   - Проверка генерации для всех 4 пресетов.
   - Проверка работы anti-slop фильтра.
   - Проверка валидации входных данных.

## Критерии приёмки
- [ ] Все типы строгие, без `any`.
- [ ] Пресеты валидны и покрывают реальные enterprise сценарии.
- [ ] Anti-slop фильтр отлавливает клише и заменяет/подсвечивает их.
- [ ] `POST /api/rolecraft/generate` возвращает валидный `RoleCraftOutput` со всеми обязательными секциями (Thinking Partner, 6-месячный импакт, 🛑 Anti-Persona, 🚀 Value Proposition).
- [ ] Тесты `npm test test/rolecraft/engine.test.ts` проходят успешно.
