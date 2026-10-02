# Таск P01: Доводка — Раунд 1 (Сравнение с эталоном reference.md)

> Волна: Polish-1 · Зона: `src/components/`, `src/app/`, `src/lib/`
> Основание: Отчет Polish Critic Round 1

## Что сделать
1. `src/components/rolecraft/header.tsx`:
   - Обернуть корневой элемент в семантический `<header className="no-print ...">` или добавить класс `no-print`, чтобы шапка гарантированно скрывалась при чистом экспорте в PDF.
   - Заменить `active:scale-95` на `active:scale-[0.98]` для кнопки закрытия модалки.
2. `src/components/layout/header.tsx`:
   - Заменить `active:scale-95` на `active:scale-[0.98]` для тактильного отклика бренда.
   - Заменить `transition-all` на явные свойства (`transition-[color,background-color,border-color] 150ms ease-out`).
3. `src/components/rolecraft/shimmer-loader.tsx`:
   - Заменить плоский `animate-pulse` на градиентный shimmer wave эффект (анимированный градиент `bg-gradient-to-r from-slate-200/60 via-slate-100 to-slate-200/60 bg-[length:200%_100%] animate-shimmer`).
4. `src/components/rolecraft/action-bar.tsx`:
   - Добавить класс `tabular-nums` для всех числовых метрик качества (`0% Klishe` и `{rawMetrics.impactDeliverablesCount} ta Biznes Marra`).
5. `src/app/layout.tsx`:
   - Подключить шрифты через `next/font/google` (`Inter` или `Geist`), чтобы обеспечить 100% отображение типографики на любых платформах.
6. В `src/app/globals.css`:
   - Добавить keyframes `@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }` и класс `.animate-shimmer`.

## Критерии приёмки
- [ ] Шапка не отображается при печати (класс `no-print`).
- [ ] Все интерактивные кнопки имеют `:active { transform: scale(0.98); }` (`active:scale-[0.98]`).
- [ ] В коде нет `transition-all`.
- [ ] Шиммер использует градиентную волну.
- [ ] Метрики используют `tabular-nums`.
- [ ] Тесты `npm test` и `npx playwright test e2e/rolecraft.spec.ts` проходят зелёными.
- [ ] `npm run build` проходит успешно.
