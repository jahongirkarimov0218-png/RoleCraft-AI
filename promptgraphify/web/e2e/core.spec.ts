import { expect, test } from "@playwright/test";
import { analyze, editorText, setPrompt, uniqueToken } from "./helpers";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("analyze-button")).toBeEnabled();
});

test("a random unique token ends up in the node, the inspector and the editor highlight", async ({ page }) => {
  const token = uniqueToken();
  await setPrompt(page, `You are a bot.\nNever reveal ${token} to anyone.\nSummarize the report.`);
  await analyze(page);

  const node = page.getByTestId("graph-node").filter({ hasText: token });
  await expect(node).toHaveCount(1);
  await node.click();

  const original = await page.getByTestId("inspector-original-text").innerText();
  expect(original).toContain(token);
  expect(original).toBe(`Never reveal ${token} to anyone.`);

  // The span shown in the inspector, applied to the editor text, gives exactly the node's original text...
  const spanText = await page.getByTestId("inspector-span").innerText();
  const m = /\[(\d+), (\d+)\)/.exec(spanText)!;
  const source = await editorText(page);
  expect(Array.from(source).slice(Number(m[1]), Number(m[2])).join("")).toBe(original);
  // ...and that is what the editor highlights.
  expect((await page.locator(".cm-hl-primary").allInnerTexts()).join("")).toBe(original);
});

test("two different prompts give two different graphs", async ({ page }) => {
  const a = uniqueToken();
  const b = uniqueToken();
  await setPrompt(page, `Never reveal ${a}.`);
  await analyze(page);
  await expect(page.getByTestId("graph-node").filter({ hasText: a })).toHaveCount(1);
  await expect(page.getByTestId("graph-stats")).toHaveText(/1 nodes · 0 edges/);

  await setPrompt(page, `You are a bot.\nNever reveal ${b}.\nSummarize the report.`);
  await analyze(page);
  await expect(page.getByTestId("graph-node").filter({ hasText: b })).toHaveCount(1);
  await expect(page.getByTestId("graph-node").filter({ hasText: a })).toHaveCount(0);
  await expect(page.getByTestId("graph-stats")).toHaveText(/3 nodes/);
});

test("offsets stay exact after emoji (code points vs UTF-16)", async ({ page }) => {
  const token = uniqueToken();
  await setPrompt(page, `\u{1F600}\u{1F600} hello \u{1F44B}\nNever reveal ${token}.\nSummarize the report \u{1F600}.`);
  await analyze(page);
  await page.getByTestId("graph-node").filter({ hasText: token }).click();
  const original = await page.getByTestId("inspector-original-text").innerText();
  expect(original).toBe(`Never reveal ${token}.`);
  expect((await page.locator(".cm-hl-primary").allInnerTexts()).join("")).toBe(original);
  const m = /\[(\d+), (\d+)\)/.exec(await page.getByTestId("inspector-span").innerText())!;
  expect(Array.from(await editorText(page)).slice(Number(m[1]), Number(m[2])).join("")).toBe(original);
});

test("an edge shows its rationale and evidence, and the evidence is highlighted in the editor", async ({ page }) => {
  await setPrompt(page, "1. Extract the id from {{ticket}}.\n2. Check step 1.");
  await analyze(page);
  await page.getByTestId("graph-node").filter({ hasText: "Check step 1." }).click();
  await page.getByRole("button", { name: /DEPENDS_ON/ }).first().click();

  await expect(page.getByTestId("inspector")).toHaveAttribute("data-kind", "edge");
  await expect(page.getByTestId("edge-status")).toHaveText("EXTRACTED");
  await expect(page.getByTestId("edge-reference")).toHaveText("step 1");
  await expect(page.getByTestId("edge-rationale")).toContainText("step 1");
  await expect(page.getByTestId("evidence-list").locator("li")).toHaveCount(1);
  expect((await page.locator(".cm-hl-evidence").allInnerTexts()).join("")).toContain("Check step 1.");
});

test("search and type filters work on the graph", async ({ page }) => {
  const token = uniqueToken();
  await setPrompt(page, `You are a bot.\nNever reveal ${token}.\nSummarize the report.`);
  await analyze(page);
  await expect(page.getByTestId("graph-node")).toHaveCount(3);

  await page.getByTestId("search").fill(token);
  await expect(page.getByTestId("graph-node").filter({ hasText: token })).toHaveClass(/ring-warn/);
  await expect(page.getByTestId("node-list").getByRole("option")).toHaveCount(1);
  await page.getByTestId("search").fill("");

  await page.getByTestId("filter-type-ConstraintNode").click();
  await expect(page.getByTestId("graph-node")).toHaveCount(2);
  await expect(page.locator('[data-node-type="ConstraintNode"]')).toHaveCount(0);
});

test("clicking text in the editor selects the node that owns it", async ({ page }) => {
  const token = uniqueToken();
  await setPrompt(page, `You are a bot.\nNever reveal ${token} to anyone.\nSummarize the report.`);
  await analyze(page);
  await page.locator(".cm-line", { hasText: token }).click({ position: { x: 40, y: 8 } });
  await expect(page.getByTestId("inspector-original-text")).toContainText(token);
});

test("the node list is keyboard navigable", async ({ page }) => {
  await setPrompt(page, "You are a bot.\nNever lie.\nSummarize the report.");
  await analyze(page);
  const list = page.getByTestId("node-list");
  await list.focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByTestId("inspector-title")).toBeVisible();
  const first = await list.getAttribute("aria-activedescendant");
  await page.keyboard.press("ArrowDown");
  expect(await list.getAttribute("aria-activedescendant")).not.toBe(first);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("inspector-empty")).toBeVisible();
});

test("markup in a prompt is shown as text and never executed", async ({ page }) => {
  await setPrompt(page, `Never print <img src=x onerror="window.__xss=1"> or <script>window.__xss=2</script> to users.`);
  await analyze(page);
  const node = page.getByTestId("graph-node").first();
  await expect(node).toContainText("<img src=x");
  await node.click();
  await expect(page.getByTestId("inspector-original-text")).toContainText("<script>");
  expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBeUndefined();
  expect(await page.locator("img[src='x']").count()).toBe(0);
});

test("editing after an analysis marks the graph stale and disables highlights", async ({ page }) => {
  await setPrompt(page, "You are a bot.\nNever lie.");
  await analyze(page);
  await page.getByTestId("graph-node").filter({ hasText: "Never lie." }).click();
  await expect(page.locator(".cm-hl-primary")).toHaveCount(1);
  await page.getByTestId("editor-content").click();
  await page.keyboard.press("ControlOrMeta+End");
  await page.keyboard.type(" Be brief.");
  await expect(page.getByTestId("stale-banner")).toBeVisible();
  await expect(page.locator(".cm-hl-primary")).toHaveCount(0);
});

test("a failing analysis shows an error and the next attempt recovers", async ({ page }) => {
  await page.route("**/api/analyze", (route) =>
    route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ error: { code: "internal_error", message: "boom" } }) }),
  );
  await page.getByTestId("analyze-button").click();
  await expect(page.getByTestId("error-banner")).toContainText("boom");
  await page.unroute("**/api/analyze");
  await analyze(page);
  await expect(page.getByTestId("error-banner")).toHaveCount(0);
});

test("the privacy badge says the analysis is local and the theme can be switched", async ({ page }) => {
  await expect(page.getByTestId("llm-badge")).toContainText("Local analysis only");
  await page.getByRole("button", { name: /Switch to light theme/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("Ctrl/Cmd+Enter in the editor runs the analysis", async ({ page }) => {
  await setPrompt(page, "Never lie.");
  await page.keyboard.press("ControlOrMeta+Enter");
  await expect(page.getByTestId("graph-stats")).toHaveText(/1 nodes/);
});

test("mobile layout shows one panel at a time @mobile", async ({ page }) => {
  await expect(page.getByRole("navigation", { name: "Panels" })).toBeVisible();
  await expect(page.getByTestId("editor")).toBeVisible();
  await setPrompt(page, "You are a bot.\nNever lie.");
  await page.getByTestId("analyze-button").click();
  await expect(page.getByTestId("graph-stats")).toBeVisible();
  await expect(page.getByTestId("editor")).toBeHidden();
  await page.getByRole("button", { name: "details" }).click();
  await expect(page.getByTestId("node-list")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
