import { test, expect } from "@playwright/test";
import { NICHE_REPORT } from "../src/lib/niche-report/report-data";

/**
 * Niche Report page (intent/spec.md §8.2).
 * Requires NICHE_REPORT_ENABLED=true on the dev server — playwright.config.ts sets it for the server it starts.
 * With reuseExistingServer, an already running `npm run dev` without the flag serves 404 here.
 */
const ROUTE = "/niche-report";
const chosen = NICHE_REPORT.candidates.find((c) => c.id === NICHE_REPORT.verdict.candidateId)!;

test.describe("Niche Report page", () => {
  test("Scenario 1: page loads with exactly one verdict naming the chosen niche", async ({ page }) => {
    const response = await page.goto(ROUTE);
    expect(
      response?.status(),
      "404 here usually means the dev server runs without NICHE_REPORT_ENABLED=true"
    ).toBe(200);

    await expect(page.locator("[data-testid=verdict]")).toHaveCount(1);
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.locator("h1")).toHaveText(chosen.label);
    await expect(page.locator("html")).toHaveAttribute("lang", "ru");
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  });

  test("Scenario 2: the 14-day test shows a numeric threshold", async ({ page }) => {
    await page.goto(ROUTE);
    const block = page.locator("[data-testid=validation-test]");
    await expect(block).toContainText(`Тест на ${NICHE_REPORT.test.durationDays} дней`);
    const threshold = await block.locator("[data-testid=threshold-value]").innerText();
    expect(Number.isFinite(Number(threshold))).toBe(true);
    const fallback = NICHE_REPORT.candidates.find((c) => c.id === NICHE_REPORT.test.fallbackCandidateId)!;
    await expect(block).toContainText(fallback.label);
  });

  test("Scenario 3: no horizontal page scroll", async ({ page }) => {
    await page.goto(ROUTE);
    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
  });

  test("Scenario 4: print hides buttons and fits one A4 page", async ({ page }) => {
    await page.goto(ROUTE);
    await page.emulateMedia({ media: "print" });
    await expect(page.getByRole("button", { name: /Печать/ })).toBeHidden();

    // Chromium's own print pipeline: count pages in the generated PDF.
    const pdf = await page.pdf({ format: "A4", preferCSSPageSize: true });
    const pages = pdf.toString("latin1").match(/\/Type\s*\/Page[^s]/g) ?? [];
    expect(pages.length).toBe(1);
  });

  test("Scenario 5: external links are https and isolated", async ({ page }) => {
    await page.goto(ROUTE);
    const links = await page.locator("a[href^='http']").evaluateAll((anchors) =>
      anchors.map((a) => ({
        href: a.getAttribute("href") ?? "",
        rel: a.getAttribute("rel") ?? "",
        target: a.getAttribute("target") ?? "",
      }))
    );
    for (const link of links) {
      expect(link.href.startsWith("https://")).toBe(true);
      expect(link.rel).toContain("noopener");
      expect(link.rel).toContain("noreferrer");
      expect(link.target).toBe("_blank");
    }
  });

  test("Scenario 6: a draft is visibly marked as not a verdict", async ({ page }) => {
    await page.goto(ROUTE);
    const banner = page.locator("[data-testid=draft-banner]");
    if (NICHE_REPORT.meta.status === "draft") {
      await expect(banner).toBeVisible();
      await expect(banner).toContainText("Это не вердикт");
    } else {
      await expect(banner).toHaveCount(0);
    }
  });
});
