/**
 * Niche Report invariants V-01…V-12 (intent/spec.md D-04).
 * Returns a list of violations; an empty list means the report is valid.
 * Draft reports are checked against the structural rules V-01…V-07 only.
 */
import type { Candidate, Criterion, NicheReport } from "./types";

export const CANDIDATE_IDS = ["clinic-ops", "smb-marketing"] as const;
export const TEST_DURATION_DAYS = 14;
export const MAX_REASONS = 3;
export const MAX_SOURCE_AGE_DAYS = 180;
export const MAX_VISIBLE_WORDS = 700;
const WEIGHT_TOLERANCE = 0.001;
const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * Product-idea markers forbidden in the validation test (spec C-04).
 * Whole-word matching via \p{L} lookarounds: JS `\b` is ASCII-only, so "работа" must not match "бот".
 */
const PRODUCT_IDEA_PATTERNS: RegExp[] = [
  /(?<!\p{L})приложени\p{L}*/iu,
  /(?<!\p{L})бот(?:а|у|ом|е|ы|ов|ам|ами|ах)?(?!\p{L})/iu,
  /(?<!\p{L})фич\p{L}*/iu,
  /(?<!\p{L})mvp(?!\p{L})/iu,
  /(?<!\p{L})функционал\p{L}*/iu,
  /(?<!\p{L})(?:app|bot|feature)s?(?!\p{L})/iu,
];

/** Fields that are identifiers or metadata, not visible prose (V-12). */
const NON_PROSE_KEYS = new Set([
  "url",
  "accessedAt",
  "id",
  "criterionId",
  "criterionIds",
  "candidateId",
  "fallbackCandidateId",
  "kind",
  "status",
  "generatedAt",
  "version",
]);

export function weightedScore(candidate: Candidate, criteria: Criterion[]): number {
  return criteria.reduce((sum, criterion) => {
    const score = candidate.scores.find((s) => s.criterionId === criterion.id);
    return sum + (score ? score.value * criterion.weight : 0);
  }, 0);
}

export function containsProductIdea(text: string): boolean {
  return PRODUCT_IDEA_PATTERNS.some((pattern) => pattern.test(text));
}

export function countVisibleWords(value: unknown, key?: string): number {
  if (key && NON_PROSE_KEYS.has(key)) return 0;
  if (typeof value === "string") return value.match(/[\p{L}\p{N}]+/gu)?.length ?? 0;
  if (Array.isArray(value)) return value.reduce((n, item) => n + countVisibleWords(item), 0);
  if (value && typeof value === "object") {
    return Object.entries(value).reduce((n, [k, v]) => n + countVisibleWords(v, k), 0);
  }
  return 0;
}

function parseDate(iso: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}/.test(iso)) return null;
  const time = Date.parse(iso);
  return Number.isNaN(time) ? null : time;
}

function isHttpsUrl(url: string): boolean {
  try {
    return new URL(url).protocol === "https:";
  } catch {
    return false;
  }
}

function checkStructure(report: NicheReport): string[] {
  const errors: string[] = [];
  const { criteria, candidates, verdict, test } = report;
  const criterionIds = new Set(criteria.map((c) => c.id));

  // V-01
  const weightSum = criteria.reduce((sum, c) => sum + c.weight, 0);
  if (criteria.length === 0 || Math.abs(weightSum - 1) > WEIGHT_TOLERANCE) {
    errors.push(`V-01: сумма весов критериев должна быть 1, сейчас ${weightSum.toFixed(3)}`);
  }
  for (const c of criteria) {
    if (!(c.weight > 0 && c.weight <= 1)) errors.push(`V-01: вес критерия «${c.id}» вне (0, 1]`);
  }
  if (criterionIds.size !== criteria.length) errors.push("V-01: id критериев не уникальны");

  // V-02
  const candidateIds = candidates.map((c) => c.id).sort();
  if (candidates.length !== 2 || candidateIds.join() !== [...CANDIDATE_IDS].sort().join()) {
    errors.push(`V-02: кандидаты должны быть ровно ${CANDIDATE_IDS.join(" и ")}`);
  }
  for (const candidate of candidates) {
    const scored = candidate.scores.map((s) => s.criterionId);
    const missing = criteria.filter((c) => !scored.includes(c.id)).map((c) => c.id);
    const unknown = scored.filter((id) => !criterionIds.has(id));
    if (missing.length || unknown.length || scored.length !== criteria.length) {
      errors.push(`V-02: у «${candidate.id}» должна быть ровно одна оценка на каждый критерий`);
    }
  }

  // V-03
  const chosen = candidates.find((c) => c.id === verdict.candidateId);
  if (!chosen) {
    errors.push("V-03: вердикт ссылается на несуществующего кандидата");
  } else {
    const chosenScore = weightedScore(chosen, criteria);
    const beaten = candidates.some(
      (c) => c !== chosen && weightedScore(c, criteria) >= chosenScore - WEIGHT_TOLERANCE
    );
    if (beaten) errors.push("V-03: у выбранной ниши нет строго максимального взвешенного балла");
  }

  // V-04
  if (verdict.reasons.length < 1 || verdict.reasons.length > MAX_REASONS) {
    errors.push(`V-04: причин должно быть от 1 до ${MAX_REASONS}`);
  }
  for (const reason of verdict.reasons) {
    if (reason.criterionIds.length === 0 || reason.criterionIds.some((id) => !criterionIds.has(id))) {
      errors.push(`V-04: причина «${reason.text.slice(0, 40)}» не ссылается на существующий критерий`);
    }
  }

  // V-05
  for (const candidate of candidates) {
    for (const score of candidate.scores) {
      if (score.evidence.length === 0) {
        errors.push(`V-05: у оценки «${candidate.id}/${score.criterionId}» нет доказательств`);
      }
    }
  }

  // V-06
  if (test.durationDays !== TEST_DURATION_DAYS) errors.push(`V-06: тест должен длиться ${TEST_DURATION_DAYS} дней`);
  if (!Number.isFinite(test.threshold.value)) errors.push("V-06: порог теста должен быть конечным числом");
  if (!test.threshold.unit.trim()) errors.push("V-06: у порога теста нет единицы измерения");

  // V-07
  if (test.fallbackCandidateId === verdict.candidateId) {
    errors.push("V-07: запасная ниша совпадает с выбранной");
  } else if (!candidates.some((c) => c.id === test.fallbackCandidateId)) {
    errors.push("V-07: запасная ниша не входит в кандидатов");
  }

  return errors;
}

function checkEvidence(report: NicheReport): string[] {
  const errors: string[] = [];
  const generatedAt = parseDate(report.meta.generatedAt);
  const evidence = report.candidates.flatMap((c) => c.scores.flatMap((s) => s.evidence));

  for (const item of evidence) {
    if (item.kind !== "fact") continue;
    const label = `«${item.claim.slice(0, 40)}»`;
    // V-08
    if (!item.source || !isHttpsUrl(item.source.url)) {
      errors.push(`V-08: у факта ${label} нет https-источника`);
      continue;
    }
    const accessedAt = parseDate(item.source.accessedAt);
    if (accessedAt === null) {
      errors.push(`V-08: у факта ${label} некорректная дата обращения`);
      continue;
    }
    // V-09
    if (generatedAt === null) {
      errors.push("V-09: некорректная meta.generatedAt");
    } else if ((generatedAt - accessedAt) / DAY_MS > MAX_SOURCE_AGE_DAYS) {
      errors.push(`V-09: источник факта ${label} старше ${MAX_SOURCE_AGE_DAYS} дней`);
    }
  }

  // V-10
  if (evidence.some((e) => e.kind === "unknown") && report.unknowns.length === 0) {
    errors.push("V-10: есть доказательства с пометкой unknown, но блок «неизвестное» пуст");
  }

  return errors;
}

function checkContent(report: NicheReport): string[] {
  const errors: string[] = [];
  // V-11
  for (const field of ["action", "metric"] as const) {
    if (containsProductIdea(report.test[field])) {
      errors.push(`V-11: test.${field} описывает продукт, а не проблему`);
    }
  }
  // V-12
  const words = countVisibleWords(report);
  if (words > MAX_VISIBLE_WORDS) {
    errors.push(`V-12: ${words} слов видимого текста, допустимо не больше ${MAX_VISIBLE_WORDS}`);
  }
  return errors;
}

export function validateNicheReport(report: NicheReport): string[] {
  const structural = checkStructure(report);
  if (report.meta.status === "draft") return structural;
  return [...structural, ...checkEvidence(report), ...checkContent(report)];
}
