/**
 * Niche Report content (intent/niche-analysis-intent.md).
 *
 * STATUS: DRAFT — placeholder data for layout and tests only (plan step 3).
 * The real content is plan step 7: it needs answers to Q-01, Q-04 and Q-10 and
 * sourced research. No market facts are stated here, so every score is marked
 * "unknown" and the verdict is not a recommendation.
 */
import type { Evidence, NicheReport } from "./types";

const notResearched = (question: string): Evidence => ({
  claim: `Оценка-заглушка: исследование не проведено, нужен ответ на ${question}.`,
  kind: "unknown",
});

export const NICHE_REPORT: NicheReport = {
  meta: {
    title: "Выбор ниши для своего приложения",
    author: "Рома Райт",
    status: "draft",
    generatedAt: "2026-10-12",
    version: "0.1.0",
  },
  verdict: {
    candidateId: "clinic-ops",
    reasons: [
      {
        text: "Заглушка: выбран первый по списку кандидат, чтобы проверить вёрстку. Это не вывод.",
        criterionIds: ["time-to-revenue"],
      },
    ],
  },
  criteria: [
    {
      id: "time-to-revenue",
      label: "Срок до первых денег",
      weight: 0.35,
      rationale: "Без выручки — не больше 3 месяцев. Самый тяжёлый вес — предположение A4, ждёт подтверждения (Q-12).",
    },
    {
      id: "payer-access",
      label: "Прямой доступ к тому, кто платит",
      weight: 0.25,
      rationale: "Тёплая аудитория — маркетологи, агентства и медицина; платят клиники и владельцы МСБ (Q-04).",
    },
    {
      id: "sales-fit",
      label: "Подходит под «строю сам, продавать сложно»",
      weight: 0.15,
      rationale: "Ручные продажи допустимы только для первых 10–20 клиентов.",
    },
    {
      id: "income-ceiling",
      label: "Достижимость «дохода на жизнь»",
      weight: 0.15,
      rationale: "Цель — небольшой прибыльный продукт для одного человека; сумма не названа (Q-01).",
    },
    {
      id: "regulatory-exposure",
      label: "Риск уйти в регулируемую зону",
      weight: 0.1,
      rationale: "В здоровье — только операционка клиник, без диагностики и медданных.",
    },
  ],
  candidates: [
    {
      id: "clinic-ops",
      label: "Операционка клиник",
      scores: [
        { criterionId: "time-to-revenue", value: 4, evidence: [notResearched("Q-02 и Q-06")] },
        { criterionId: "payer-access", value: 3, evidence: [notResearched("Q-05")] },
        { criterionId: "sales-fit", value: 3, evidence: [notResearched("Q-05")] },
        { criterionId: "income-ceiling", value: 3, evidence: [notResearched("Q-01 и Q-06")] },
        { criterionId: "regulatory-exposure", value: 3, evidence: [notResearched("Q-07")] },
      ],
    },
    {
      id: "smb-marketing",
      label: "Маркетинг для владельцев МСБ",
      scores: [
        { criterionId: "time-to-revenue", value: 3, evidence: [notResearched("Q-02 и Q-06")] },
        { criterionId: "payer-access", value: 3, evidence: [notResearched("Q-04")] },
        { criterionId: "sales-fit", value: 3, evidence: [notResearched("Q-04")] },
        { criterionId: "income-ceiling", value: 3, evidence: [notResearched("Q-01 и Q-06")] },
        { criterionId: "regulatory-exposure", value: 3, evidence: [notResearched("Q-07")] },
      ],
    },
  ],
  test: {
    durationDays: 14,
    audience: "Заглушка: тёплые контакты в выбранной нише (уточнить в Q-05 / Q-04).",
    action: "Заглушка: формат теста не выбран (Q-10).",
    metric: "Заглушка: метрика не выбрана (Q-10).",
    threshold: { value: 0, unit: "— порог не задан (Q-10)" },
    goRule: "Если результат ≥ порога — идём, иначе — вторая ниша.",
    fallbackCandidateId: "smb-marketing",
  },
  unknowns: [
    "Сумма «дохода на жизнь» (Q-01).",
    "Есть ли прямой доступ к владельцам МСБ (Q-04).",
    "Формат 2-недельного теста и кто задаёт порог (Q-10).",
    "Средний чек и модель оплаты в обоих направлениях (Q-06).",
  ],
};
