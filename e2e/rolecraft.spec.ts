import { test, expect } from "@playwright/test";

test.describe("RoleCraft AI Enterprise Job Description Generator E2E", () => {
  test.beforeEach(async ({ context }) => {
    // Grant clipboard permissions for copy operations
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  });

  // --------------------------------------------------------------------------
  // Scenario 1: Page Load & Initial Enterprise State
  // --------------------------------------------------------------------------
  test("Scenario 1: Page load, RoleCraft brand, Thinking Partner indicator & 4 enterprise presets", async ({
    page,
  }) => {
    await page.goto("/");

    // 1. Verify Page & Brand Header
    await expect(page.locator("text=RoleCraft AI").first()).toBeVisible();
    await expect(page.locator("text=Lou Adler Framework").first()).toBeVisible();

    // 2. Verify Thinking Partner Status Indicator
    const statusPill = page.locator("text=Thinking Partner: Faol").first();
    await expect(statusPill).toBeVisible();

    // 3. Verify Methodology Modal Trigger
    const methodologyBtn = page.locator("button:has-text('Metodika')");
    await expect(methodologyBtn).toBeVisible();
    await methodologyBtn.click();
    await expect(page.locator("text=RoleCraft AI Metodologiyasi")).toBeVisible();
    await page.locator("button:has-text('Tushundim')").click();
    await expect(page.locator("text=RoleCraft AI Metodologiyasi")).not.toBeVisible();

    // 4. Verify Presence of all 4 Enterprise Presets
    const presetAI = page.locator("button:has-text('Staff AI / LLM Architect')");
    const presetGrowth = page.locator("button:has-text('Head of Growth Engineering')");
    const presetDesign = page.locator("button:has-text('Lead Product Designer (Design Systems)')");
    const presetDirector = page.locator("button:has-text('Engineering Director (Platform & Reliability)')");

    await expect(presetAI).toBeVisible();
    await expect(presetGrowth).toBeVisible();
    await expect(presetDesign).toBeVisible();
    await expect(presetDirector).toBeVisible();
  });

  // --------------------------------------------------------------------------
  // Scenario 2: Preset Selection & Instant Form Autofill
  // --------------------------------------------------------------------------
  test("Scenario 2: Preset click instantly populates all form fields", async ({ page }) => {
    await page.goto("/");

    // 1. Click Growth Engineering preset
    const growthPreset = page.locator("button:has-text('Head of Growth Engineering')");
    await growthPreset.click();

    // Verify fields populated with Growth preset values
    await expect(page.locator("#roleTitle")).toHaveValue("Head of Growth Engineering");
    await expect(page.locator("#companyContext")).toHaveValue(/Post-PMF B2B SaaS platformasi/i);
    await expect(page.locator("#coreBusinessPain")).toHaveValue(/Konversiya voronkasining sign-up/i);
    await expect(page.locator("#techStackAndSkills")).toHaveValue(/Next\.js, TypeScript/i);

    // 2. Switch to Staff AI / LLM Architect preset
    const aiPreset = page.locator("button:has-text('Staff AI / LLM Architect')");
    await aiPreset.click();

    // Verify fields updated instantly
    await expect(page.locator("#roleTitle")).toHaveValue("Staff AI / LLM Architect");
    await expect(page.locator("#companyContext")).toHaveValue(/Series B GenAI platform/i);
    await expect(page.locator("#coreBusinessPain")).toHaveValue(/Mavjud prototip va MVP PoC tuzog'ida/i);
    await expect(page.locator("#techStackAndSkills")).toHaveValue(/Python 3\.12, FastAPI/i);
  });

  // --------------------------------------------------------------------------
  // Scenario 3: Form Submission, Shimmer Loader, Thinking Partner Card & Markdown
  // --------------------------------------------------------------------------
  test("Scenario 3: Form submission triggers shimmer loader, produces Thinking Partner Card & full Markdown spec", async ({
    page,
  }) => {
    await page.goto("/");

    // Select Staff AI preset
    const aiPreset = page.locator("button:has-text('Staff AI / LLM Architect')");
    await aiPreset.click();

    // Submit generation
    const submitBtn = page.locator("button[type='submit']");
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Verify shimmer loader or active synthesis state appears
    await expect(page.locator("button[type='submit']")).toContainText("Thinking Partner sintez qilmoqda");

    // Wait for generation completion and results container
    const resultsContainer = page.locator("#rolecraft-results");
    await expect(resultsContainer).toBeVisible({ timeout: 15000 });

    // Verify Thinking Partner Matrix Card
    await expect(resultsContainer.locator("text=Thinking Partner: Strategik Tahlil Matritsasi")).toBeVisible();
    await expect(resultsContainer.getByText("Biznes Dardi (Root Cause)", { exact: true })).toBeVisible();
    await expect(resultsContainer.getByText("A-Player Psixologiyasi", { exact: true })).toBeVisible();
    await expect(resultsContainer.getByText("Strategik Pozitsiya", { exact: true })).toBeVisible();

    // Verify Markdown Spec Required Sections
    await expect(page.locator("text=Staff AI / LLM Architect").first()).toBeVisible();
    await expect(page.locator("text=Lavozim va Hisobot Ierarxiyasi")).toBeVisible();
    await expect(page.locator("text=Asosiy Vazifalar va 6 Oylik Biznes Ta'siri")).toBeVisible();
    await expect(page.locator("text=Talablar va Amaliy Natijalar")).toBeVisible();
    await expect(page.locator("text=Texnik va Amaliy Ko'nikmalar")).toBeVisible();

    // Strict Spec: Anti-Persona and Value Proposition sections with their badges
    await expect(page.locator("text=🛑 Ushbu Rol Kimlarga To'g'ri Kelmaydi").first()).toBeVisible();
    await expect(page.locator("text=Self-Filter Gate").first()).toBeVisible();

    await expect(page.locator("text=🚀 Kompaniya Va'dasi").first()).toBeVisible();
    await expect(page.locator("text=A-Player Promise").first()).toBeVisible();
  });

  // --------------------------------------------------------------------------
  // Scenario 4: 1-Click Markdown Copy with Tactile Feedback ("Copied!")
  // --------------------------------------------------------------------------
  test("Scenario 4: 1-click Markdown copy triggers tactile button change to 'Copied!' and toast", async ({
    page,
  }) => {
    await page.goto("/");

    // Generate output
    const submitBtn = page.locator("button[type='submit']");
    await submitBtn.click();
    await expect(page.locator("#rolecraft-results")).toBeVisible({ timeout: 15000 });

    // Find Copy Markdown button
    const copyBtn = page.locator("button:has-text('Copy Markdown')");
    await expect(copyBtn).toBeVisible();

    // Click copy
    await copyBtn.click();

    // Verify tactile feedback: button text changes to "Copied!"
    const copiedBtn = page.locator("button:has-text('Copied!')");
    await expect(copiedBtn).toBeVisible();

    // Verify ephemeral toast
    await expect(page.locator("text=Markdown nusxalandi!")).toBeVisible();
  });

  // --------------------------------------------------------------------------
  // Scenario 5: Clean PDF Export with window.print() Interception
  // --------------------------------------------------------------------------
  test("Scenario 5: Clean PDF export triggers browser window.print() dialog", async ({
    page,
  }) => {
    await page.goto("/");

    // Setup window.print spy
    await page.evaluate(() => {
      (window as any).__printTriggered = false;
      window.print = () => {
        (window as any).__printTriggered = true;
      };
    });

    // Generate outcome
    const submitBtn = page.locator("button[type='submit']");
    await submitBtn.click();
    await expect(page.locator("#rolecraft-results")).toBeVisible({ timeout: 15000 });

    // Click Export Clean PDF button
    const exportPdfBtn = page.locator("button:has-text('Export Clean PDF')");
    await expect(exportPdfBtn).toBeVisible();
    await exportPdfBtn.click();

    // Verify print spy was triggered
    const isPrintTriggered = await page.evaluate(() => (window as any).__printTriggered);
    expect(isPrintTriggered).toBe(true);
  });

  // --------------------------------------------------------------------------
  // Scenario 6: Validation on Empty / Short Inputs without Page Crash
  // --------------------------------------------------------------------------
  test("Scenario 6: Submitting empty/invalid inputs shows validation errors without page crash", async ({
    page,
  }) => {
    await page.goto("/");

    // Clear the form using Tozalash button
    const clearBtn = page.locator("button:has-text('Tozalash')");
    await clearBtn.click();

    // Verify inputs are cleared
    await expect(page.locator("#roleTitle")).toHaveValue("");
    await expect(page.locator("#companyContext")).toHaveValue("");
    await expect(page.locator("#coreBusinessPain")).toHaveValue("");
    await expect(page.locator("#techStackAndSkills")).toHaveValue("");

    // Attempt submission with empty values
    const submitBtn = page.locator("button[type='submit']");
    await submitBtn.click();

    // Verify field-level validation error messages appear
    await expect(
      page.locator("text=Lavozim nomi kamida 3 ta belgidan iborat bo'lishi kerak")
    ).toBeVisible();
    await expect(
      page.locator("text=Kompaniya konteksti kamida 10 ta belgidan iborat bo'lishi kerak")
    ).toBeVisible();
    await expect(
      page.locator("text=Biznes dardi kamida 10 ta belgidan iborat bo'lishi kerak")
    ).toBeVisible();
    await expect(
      page.locator("text=Texnologik stak kamida 3 ta belgidan iborat bo'lishi kerak")
    ).toBeVisible();

    // Verify accessible role="alert" banner is displayed
    await expect(page.locator("form [role='alert']")).toBeVisible();

    // Verify results section is NOT rendered and page is intact
    await expect(page.locator("#rolecraft-results")).not.toBeVisible();

    // Verify recovery: clicking a preset repopulates and clears error state
    const presetDirector = page.locator(
      "button:has-text('Engineering Director (Platform & Reliability)')"
    );
    await presetDirector.click();

    await expect(page.locator("#roleTitle")).toHaveValue(
      "Engineering Director (Platform & Reliability)"
    );
    await expect(page.locator("form [role='alert']")).not.toBeVisible();
  });

  // --------------------------------------------------------------------------
  // Scenario 7: Mobile Responsiveness (375x667 Viewport)
  // --------------------------------------------------------------------------
  test("Scenario 7: Mobile viewport layout, touchability and no horizontal overflow", async ({
    page,
  }) => {
    // Set explicit mobile viewport (Pixel 5 size)
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("/");

    // 1. Verify Header and Hero are visible and readable
    await expect(page.locator("text=RoleCraft AI").first()).toBeVisible();
    await expect(
      page.locator("h1:has-text('Klishelarsiz, Biznes Ta')")
    ).toBeVisible();

    // 2. Verify all presets are visible and touch-clickable
    const firstPreset = page.locator("button:has-text('Staff AI / LLM Architect')");
    await expect(firstPreset).toBeVisible();
    await firstPreset.click();

    // 3. Verify Form Fields fit and are interactive
    const roleInput = page.locator("#roleTitle");
    await expect(roleInput).toBeVisible();
    await expect(roleInput).toHaveValue("Staff AI / LLM Architect");

    // 4. Verify no broken horizontal document overflow
    const scrollWidth = await page.evaluate(
      () => document.documentElement.scrollWidth
    );
    const clientWidth = await page.evaluate(
      () => document.documentElement.clientWidth
    );
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 5);

    // 5. Test submit and generation on mobile
    const submitBtn = page.locator("button[type='submit']");
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    await expect(page.locator("#rolecraft-results")).toBeVisible({
      timeout: 15000,
    });
    await expect(
      page.locator("text=Thinking Partner: Strategik Tahlil Matritsasi")
    ).toBeVisible();

    // 6. Verify Action Bar buttons are accessible on mobile
    const copyBtn = page.locator("button:has-text('Copy Markdown')");
    await expect(copyBtn).toBeVisible();
    const exportPdfBtn = page.locator("button:has-text('Export Clean PDF')");
    await expect(exportPdfBtn).toBeVisible();
  });
});
