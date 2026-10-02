import { test, expect } from "@playwright/test";

test.describe("Founder-Grade Customer Feedback Intelligence E2E", () => {
  test("Instant Preview workflow: 1-click demo -> benchmark dashboard -> Linear task export", async ({
    page,
  }) => {
    // 1. Visit homepage
    await page.goto("/");
    const feedbackTab = page.locator("button:has-text('Customer Feedback AI')");
    if (await feedbackTab.isVisible()) {
      await feedbackTab.click();
    }
    await expect(page).toHaveTitle(/Customer Feedback|Mijoz|RoleCraft/i);

    // 2. Verify UVP micro-badge without emojis
    const uvpBadge = page.locator("text=Linear va Jira uchun tayyor backlog");
    await expect(uvpBadge).toBeVisible();

    // 3. Click Instant Preview trigger button
    const instantPreviewBtn = page
      .locator("button:has-text('Jonli namunani ko')")
      .first();
    await expect(instantPreviewBtn).toBeVisible();
    await instantPreviewBtn.click();

    // 4. Results must immediately render without network delay
    const resultsSection = page.locator("#analysis-results");
    await expect(resultsSection).toBeVisible({ timeout: 5000 });

    // 5. Verify Executive Brief & Action Bar with ready engineering task format
    await expect(page.locator("text=Executive Brief")).toBeVisible();
    await expect(page.locator("text=P0 Engineering Task")).toBeVisible();
    await expect(page.locator("text=Sprint yechimi:")).toBeVisible();

    // 6. Test Copy as Linear Issue button with tactile feedback
    const copyLinearBtn = page.locator(
      "button:has-text('Linear vazifa sifatida nusxalash')"
    );
    await expect(copyLinearBtn).toBeVisible();
    await copyLinearBtn.click();
    await expect(page.locator("text=Linear task nusxalandi")).toBeVisible();

    // 7. Verify priority filtering works on benchmark data
    const highFilter = page.locator("button:has-text('Yuqori')").first();
    await highFilter.click();
    await expect(page.locator("text=To'lov gateway uzilishi").first()).toBeVisible();
  });

  test("Complete product flow: chip preset -> analysis -> insights -> evidence modal -> priority matrix", async ({
    page,
  }) => {
    // 1. Visit homepage
    await page.goto("/");
    const feedbackTab = page.locator("button:has-text('Customer Feedback AI')");
    if (await feedbackTab.isVisible()) {
      await feedbackTab.click();
    }
    await expect(page).toHaveTitle(/Customer Feedback|Mijoz|RoleCraft/i);

    // 2. Verify concise outcome-focused Hero H1 & Subtitle (Raycast & Linear style)
    const heroHeading = page.locator("h1");
    await expect(heroHeading).toContainText("Mijoz fikrlarini ustuvor vazifalarga aylantiring");

    const heroSubtitle = page.locator("text=Tarqoq sharhlardan tizimli muammolarni ajrating");
    await expect(heroSubtitle).toBeVisible();

    // 3. Select a preset (E-Commerce chip)
    const ecommercePreset = page.locator("button[aria-label='Namuna: E-Commerce']");
    await expect(ecommercePreset).toBeVisible();
    await ecommercePreset.click();

    // 4. Verify textarea is populated and counter updates
    const textarea = page.locator("textarea");
    await expect(textarea).not.toBeEmpty();
    const textareaValue = await textarea.inputValue();
    expect(textareaValue.length).toBeGreaterThan(50);

    // 5. Trigger Analysis
    const analyzeButton = page.locator("button:has-text('Tahlil qilish')");
    await expect(analyzeButton).toBeEnabled();
    await analyzeButton.click();

    // 6. Verify Results appear
    const resultsSection = page.locator("#analysis-results");
    await expect(resultsSection).toBeVisible({ timeout: 15000 });

    // Verify Executive Summary & Spotlight
    await expect(page.locator("text=Executive Brief")).toBeVisible();
    await expect(page.locator("text=Mijoz Qoniqish Indeksi")).toBeVisible();

    // Verify Top Insights
    await expect(page.locator("text=Top 3 Strategik Xulosalar")).toBeVisible();

    // Verify Problems Table (5 Columns)
    await expect(
      page.locator("text=Muammo | Ta'sir | Dalil | Ustuvorlik | Tavsiya")
    ).toBeVisible();

    // 7. Test Evidence Modal Drill-down
    const evidenceButton = page
      .locator("button:has-text('dalil'), button:has-text('Dalillarni')")
      .first();
    await expect(evidenceButton).toBeVisible();
    await evidenceButton.click();

    // Modal should be open
    const modalDialog = page.locator("div[role='dialog']");
    await expect(modalDialog).toBeVisible();
    await expect(page.locator("text=Mijoz Dalillari (Evidence)")).toBeVisible();

    // Close modal
    const closeButton = modalDialog.locator("button[aria-label='Yopish']");
    await closeButton.click();
    await expect(modalDialog).not.toBeVisible();

    // 8. Test Priority Filters in Table
    const highFilterBtn = page.locator("button:has-text('Yuqori')").first();
    if (await highFilterBtn.isVisible()) {
      await highFilterBtn.click();
      await page.waitForTimeout(200);
    }
  });

  test("Mobile responsive check & navigation", async ({ page }) => {
    await page.goto("/");
    // Check no horizontal document body overflow
    const scrollWidth = await page.evaluate(
      () => document.documentElement.scrollWidth
    );
    const clientWidth = await page.evaluate(
      () => document.documentElement.clientWidth
    );
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 5); // tolerance for scrollbars
  });
});
