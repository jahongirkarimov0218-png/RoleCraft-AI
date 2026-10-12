import { describe, it, expect } from "vitest";
import {
  validateNicheReport,
  weightedScore,
  containsProductIdea,
  countVisibleWords,
  isNicheReportEnabled,
  type NicheReport,
} from "@/lib/niche-report";

/** Valid final report used as the base for every negative case. */
function makeReport(): NicheReport {
  const fact = (claim: string) => ({
    claim,
    kind: "fact" as const,
    source: {
      title: "Example source",
      publisher: "Example publisher",
      url: "https://example.org/data",
      accessedAt: "2026-10-01",
    },
  });
  return {
    meta: {
      title: "Отчёт о выборе ниши",
      author: "Рома Райт",
      status: "final",
      generatedAt: "2026-10-12",
      version: "1.0.0",
    },
    verdict: {
      candidateId: "clinic-ops",
      reasons: [{ text: "Быстрее первые деньги", criterionIds: ["speed"] }],
    },
    criteria: [
      { id: "speed", label: "Срок до первых денег", weight: 0.6, rationale: "Запас ≤3 месяцев" },
      { id: "access", label: "Доступ к плательщику", weight: 0.4, rationale: "Тёплая аудитория" },
    ],
    candidates: [
      {
        id: "clinic-ops",
        label: "Операционка клиник",
        scores: [
          { criterionId: "speed", value: 4, evidence: [fact("Факт A")] },
          { criterionId: "access", value: 4, evidence: [{ claim: "Предположение", kind: "assumption" }] },
        ],
      },
      {
        id: "smb-marketing",
        label: "Маркетинг для МСБ",
        scores: [
          { criterionId: "speed", value: 3, evidence: [fact("Факт B")] },
          { criterionId: "access", value: 2, evidence: [{ claim: "Неизвестно", kind: "unknown" }] },
        ],
      },
    ],
    test: {
      durationDays: 14,
      audience: "Владельцы клиник из тёплых контактов",
      action: "Провести интервью о том, как клиника записывает пациентов",
      metric: "Согласия на платный пилот",
      threshold: { value: 3, unit: "клиники" },
      goRule: "Если ≥ 3 — идём",
      fallbackCandidateId: "smb-marketing",
    },
    unknowns: ["Есть ли доступ к владельцам МСБ"],
  };
}

function rules(report: NicheReport): string[] {
  return validateNicheReport(report).map((e) => e.slice(0, 4));
}

describe("validateNicheReport — positive", () => {
  it("accepts a valid final report", () => {
    expect(validateNicheReport(makeReport())).toEqual([]);
  });

  it("computes weighted scores", () => {
    const r = makeReport();
    expect(weightedScore(r.candidates[0], r.criteria)).toBeCloseTo(4);
    expect(weightedScore(r.candidates[1], r.criteria)).toBeCloseTo(2.6);
  });
});

describe("validateNicheReport — one negative case per invariant", () => {
  it("V-01 weights must sum to 1", () => {
    const r = makeReport();
    r.criteria[0].weight = 0.5;
    expect(rules(r)).toContain("V-01");
  });

  it("V-02 candidates must be exactly clinic-ops and smb-marketing with full scores", () => {
    const r = makeReport();
    r.candidates[1].scores.pop();
    expect(rules(r)).toContain("V-02");
  });

  it("V-03 a tie is not a verdict", () => {
    const r = makeReport();
    r.candidates[1].scores[0].value = 4;
    r.candidates[1].scores[1].value = 4;
    expect(rules(r)).toContain("V-03");
  });

  it("V-04 at most three reasons", () => {
    const r = makeReport();
    r.verdict.reasons = Array.from({ length: 4 }, () => ({ text: "x", criterionIds: ["speed"] }));
    expect(rules(r)).toContain("V-04");
  });

  it("V-05 every score needs evidence", () => {
    const r = makeReport();
    r.candidates[0].scores[1].evidence = [];
    expect(rules(r)).toContain("V-05");
  });

  it("V-06 threshold must be a finite number", () => {
    const r = makeReport();
    r.test.threshold.value = Number.NaN;
    expect(rules(r)).toContain("V-06");
  });

  it("V-07 fallback must differ from the verdict", () => {
    const r = makeReport();
    r.test.fallbackCandidateId = "clinic-ops";
    expect(rules(r)).toContain("V-07");
  });

  it("V-08 a fact needs an https source", () => {
    const r = makeReport();
    r.candidates[0].scores[0].evidence[0].source!.url = "http://example.org";
    expect(rules(r)).toContain("V-08");
  });

  it("V-09 a source older than 180 days is stale", () => {
    const r = makeReport();
    r.candidates[0].scores[0].evidence[0].source!.accessedAt = "2025-01-01";
    expect(rules(r)).toContain("V-09");
  });

  it("V-10 unknown evidence requires a non-empty unknowns block", () => {
    const r = makeReport();
    r.unknowns = [];
    expect(rules(r)).toContain("V-10");
  });

  it("V-11 the test must not describe a product", () => {
    const r = makeReport();
    r.test.action = "Показать владельцам MVP Telegram-бота";
    expect(rules(r)).toContain("V-11");
  });

  it("V-12 visible text is capped at 700 words", () => {
    const r = makeReport();
    r.unknowns = [Array.from({ length: 701 }, () => "слово").join(" ")];
    expect(rules(r)).toContain("V-12");
  });
});

describe("validateNicheReport — draft status", () => {
  it("checks only structural rules V-01…V-07 for drafts", () => {
    const r = makeReport();
    r.meta.status = "draft";
    r.candidates[0].scores[0].evidence[0].source = undefined; // would be V-08
    r.test.action = "Сделать бота"; // would be V-11
    expect(validateNicheReport(r)).toEqual([]);
  });

  it("still enforces structural rules for drafts", () => {
    const r = makeReport();
    r.meta.status = "draft";
    r.test.durationDays = 7 as 14;
    expect(rules(r)).toContain("V-06");
  });
});

describe("containsProductIdea — whole-word Cyrillic matching", () => {
  it("does not flag words that merely contain a marker", () => {
    expect(containsProductIdea("Работа с клиниками и разработка гипотез")).toBe(false);
    expect(containsProductIdea("Обработать заявки")).toBe(false);
  });

  it("flags product markers in their inflected forms", () => {
    expect(containsProductIdea("показать бота")).toBe(true);
    expect(containsProductIdea("демо приложения")).toBe(true);
    expect(containsProductIdea("список фич")).toBe(true);
    expect(containsProductIdea("Build an app")).toBe(true);
  });
});

describe("countVisibleWords", () => {
  it("ignores urls, ids and dates", () => {
    expect(
      countVisibleWords({ claim: "два слова", source: { url: "https://a.b/c d", accessedAt: "2026-10-12" } })
    ).toBe(2);
  });
});

describe("isNicheReportEnabled", () => {
  it("is disabled unless the flag is exactly 'true'", () => {
    expect(isNicheReportEnabled({})).toBe(false);
    expect(isNicheReportEnabled({ NICHE_REPORT_ENABLED: "false" })).toBe(false);
    expect(isNicheReportEnabled({ NICHE_REPORT_ENABLED: "1" })).toBe(false);
  });

  it("is enabled when the flag is 'true'", () => {
    expect(isNicheReportEnabled({ NICHE_REPORT_ENABLED: "true" })).toBe(true);
  });
});
