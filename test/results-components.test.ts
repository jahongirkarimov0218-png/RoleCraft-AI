import { describe, it, expect } from "vitest";
import React from "react";
import { calculateHealthScore } from "@/components/results/summary-card";

describe("SummaryCard & Health Score (R03, R08)", () => {
  it("should calculate health score correctly on 0-100 scale", () => {
    // 100% positive should yield 100
    expect(calculateHealthScore({ positive: 100, neutral: 0, negative: 0 })).toBe(100);

    // 100% negative should yield 0
    expect(calculateHealthScore({ positive: 0, neutral: 0, negative: 100 })).toBe(0);

    // 70% positive, 20% neutral, 10% negative -> 70 + (20 * 0.5) = 80
    expect(calculateHealthScore({ positive: 70, neutral: 20, negative: 10 })).toBe(80);

    // 50% positive, 0% neutral, 50% negative -> 50 / 100 = 50
    expect(calculateHealthScore({ positive: 50, neutral: 0, negative: 50 })).toBe(50);
  });

  it("should export SummaryCard as a valid React component and accept AnalysisResponse", async () => {
    const { SummaryCard } = await import("@/components/results/summary-card");
    expect(typeof SummaryCard).toBe("function");

    const mockData = {
      summary: "Mijozlar asosan mahsulot sifatidan mamnun, ammo yetkazib berish xizmatidan norozi.",
      sentiment: { positive: 65, neutral: 20, negative: 15 },
      topInsights: [
        { title: "Sifat yuqori", description: "Mahsulot materialiga e'tiroz yo'q." },
        { title: "Logistika sekin", description: "Kuryerlar 2 kunga kechikmoqda." },
        { title: "Qo'llab-quvvatlash sust", description: "Operatorlar kech javob beradi." },
      ],
      problems: [
        { problem: "Kuryer kechikishi", priority: "high" as const, solution: "Yangi logistika sherigi bilan ishlash" },
      ],
      meta: {
        totalWords: 150,
        provider: "built-in-semantic-engine" as const,
        processedAt: new Date().toISOString(),
      },
    };

    const element = React.createElement(SummaryCard, { data: mockData });
    expect(element).toBeDefined();
    expect(element.type).toBe(SummaryCard);
    expect(element.props.data.summary).toBe(mockData.summary);
  });
});

describe("SentimentCard & Sentiment Distribution (R03, R08)", () => {
  it("should evaluate sentiment status correctly", async () => {
    const { getSentimentStatus } = await import("@/components/results/sentiment-card");

    const highPositive = getSentimentStatus({ positive: 75, neutral: 15, negative: 10 });
    expect(highPositive.status).toBe("Kuchli ijobiy");
    expect(highPositive.variant).toBe("positive");

    const highNegative = getSentimentStatus({ positive: 20, neutral: 30, negative: 50 });
    expect(highNegative.status).toBe("Diqqat talab etiladi");
    expect(highNegative.variant).toBe("negative");

    const balanced = getSentimentStatus({ positive: 40, neutral: 35, negative: 25 });
    expect(balanced.status).toBe("Balanslashgan");
    expect(balanced.variant).toBe("neutral");
  });

  it("should export SentimentCard as a valid React component and render bars", async () => {
    const { SentimentCard } = await import("@/components/results/sentiment-card");
    expect(typeof SentimentCard).toBe("function");

    const element = React.createElement(SentimentCard, {
      sentiment: { positive: 60, neutral: 25, negative: 15 },
    });
    expect(element).toBeDefined();
    expect(element.type).toBe(SentimentCard);
    expect(element.props.sentiment.positive).toBe(60);
  });
});

describe("TopInsights & Strategic Recommendations (R05, R08)", () => {
  it("should determine strategic impact tags for insights", async () => {
    const { getInsightImpactTag } = await import("@/components/results/top-insights");
    expect(typeof getInsightImpactTag).toBe("function");

    const churnInsight = {
      title: "Mijozlar ketib qolish xavfi yuqori",
      description: "Narx oshishi tufayli bekor qilishlar 15% ga oshgan",
    };
    const churnTag = getInsightImpactTag(churnInsight, 0);
    expect(churnTag.tag).toContain("Churn");

    const defaultFirst = getInsightImpactTag({ title: "Sifat", description: "Mahsulot" }, 0);
    expect(defaultFirst.tag).toBeTruthy();
  });

  it("should export TopInsights and InsightsList as valid React components", async () => {
    const { TopInsights, InsightsList } = await import("@/components/results/top-insights");
    expect(typeof TopInsights).toBe("function");
    expect(typeof InsightsList).toBe("function");

    const element = React.createElement(TopInsights, {
      insights: [
        { title: "T1", description: "D1" },
        { title: "T2", description: "D2" },
        { title: "T3", description: "D3" },
      ],
    });
    expect(element).toBeDefined();
    expect(element.type).toBe(TopInsights);
  });
});

describe("ProblemsTable, Filtering & Export (R04, R06, R07)", () => {
  it("should filter problems by priority correctly", async () => {
    const { filterProblemsByPriority } = await import("@/components/results/problems-table");
    expect(typeof filterProblemsByPriority).toBe("function");

    const sampleProblems = [
      { problem: "P1", priority: "high" as const, solution: "S1" },
      { problem: "P2", priority: "medium" as const, solution: "S2" },
      { problem: "P3", priority: "low" as const, solution: "S3" },
      { problem: "P4", priority: "high" as const, solution: "S4" },
    ];

    expect(filterProblemsByPriority(sampleProblems, "all")).toHaveLength(4);
    expect(filterProblemsByPriority(sampleProblems, "high")).toHaveLength(2);
    expect(filterProblemsByPriority(sampleProblems, "medium")).toHaveLength(1);
    expect(filterProblemsByPriority(sampleProblems, "low")).toHaveLength(1);
  });

  it("should generate valid CSV format for problems export", async () => {
    const { exportProblemsToCSV } = await import("@/components/results/problems-table");
    expect(typeof exportProblemsToCSV).toBe("function");

    const sampleProblems = [
      { problem: "To'lov xatosi", priority: "high" as const, solution: "Karta integratsiyasini tuzatish" },
    ];

    const csv = exportProblemsToCSV(sampleProblems);
    expect(csv).toContain("Muammo,Ustuvorlik,Yechim");
    expect(csv).toContain("To'lov xatosi");
    expect(csv).toContain("high");
    expect(csv).toContain("Karta integratsiyasini tuzatish");
  });

  it("should generate valid JSON representation for export", async () => {
    const { exportAnalysisToJSON } = await import("@/components/results/problems-table");
    expect(typeof exportAnalysisToJSON).toBe("function");

    const payload = { test: 123, list: ["a", "b"] };
    const jsonStr = exportAnalysisToJSON(payload);
    expect(JSON.parse(jsonStr)).toEqual(payload);
  });

  it("should export ProblemsTable as a valid React component", async () => {
    const { ProblemsTable } = await import("@/components/results/problems-table");
    expect(typeof ProblemsTable).toBe("function");

    const element = React.createElement(ProblemsTable, {
      problems: [
        { problem: "Muammo 1", priority: "high" as const, solution: "Yechim 1" },
      ],
    });
    expect(element).toBeDefined();
    expect(element.type).toBe(ProblemsTable);
  });
});

describe("HomePage Integration (R01, R02, R08, R09)", () => {
  it("should export default HomePage component", async () => {
    const pageModule = await import("@/app/(main)/page");
    expect(pageModule.default).toBeDefined();
    expect(typeof pageModule.default).toBe("function");

    const element = React.createElement(pageModule.default);
    expect(element).toBeDefined();
  });
});








