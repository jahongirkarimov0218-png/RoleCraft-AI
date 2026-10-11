import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { analyze, setPrompt } from "./helpers";

// Automated accessibility checks with axe-core (WCAG 2.0/2.1 A and AA rules plus best practices) in both themes and in
// the main states of the app. axe finds part of the problems (it cannot judge reading order or the meaning of labels);
// the keyboard tests below cover navigation. A clean axe run is evidence, not a certificate.
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"];

async function violations(page: Page, label: string) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  return results.violations.map((v) => ({
    state: label,
    rule: v.id,
    impact: v.impact,
    help: v.help,
    nodes: v.nodes.slice(0, 4).map((n) => n.target.join(" ") + " :: " + (n.failureSummary ?? "").split("\n").slice(1, 3).join(" ").slice(0, 160)),
  }));
}

const currentTheme = (page: Page) => page.evaluate(() => document.documentElement.dataset.theme);

async function setTheme(page: Page, theme: "dark" | "light") {
  if ((await currentTheme(page)) !== theme) await page.getByRole("button", { name: /Switch to (light|dark) theme/ }).click();
  await expect.poll(() => currentTheme(page)).toBe(theme);
}

for (const theme of ["dark", "light"] as const) {
  test(`axe: no violations in the main states (${theme} theme)`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto("/");
    await expect(page.getByTestId("analyze-button")).toBeEnabled();
    await setTheme(page, theme);
    const found: unknown[] = [];

    found.push(...(await violations(page, "empty editor")));

    await setPrompt(page, "You are a support bot.\n1. Extract the ticket id from {{ticket}}.\n2. Check step 1.\n3. Send step 2 with the notify tool.\nNever promise a refund.\nKeep every answer under 50 words.");
    await analyze(page);
    found.push(...(await violations(page, "graph after analysis")));

    await page.getByTestId("graph-node").first().click();
    await expect(page.getByTestId("inspector")).toBeVisible();
    found.push(...(await violations(page, "node selected, inspector open")));

    await page.getByTestId("tab-dag").click();
    await expect(page.getByTestId("dag-panel")).toBeVisible();
    found.push(...(await violations(page, "execution DAG tab")));

    await page.getByTestId("tab-diagnostics").click();
    found.push(...(await violations(page, "diagnostics tab")));

    await page.getByTestId("tab-queries").click();
    found.push(...(await violations(page, "queries tab")));

    await page.getByTestId("export-button").click();
    await expect(page.getByTestId("export-list")).toBeVisible();
    found.push(...(await violations(page, "export menu open")));

    expect(found, JSON.stringify(found, null, 2)).toEqual([]);
  });
}

test("keyboard: every control is reachable with Tab, shows a focus indicator, and Escape closes the export menu", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("analyze-button")).toBeEnabled();
  await setPrompt(page, "You are a bot.\nSummarize the report.");
  await analyze(page);

  // Walk the tab order from the top of the page; collect what receives focus.
  await page.locator("body").click({ position: { x: 1, y: 1 } });
  const seen: string[] = [];
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press("Tab");
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return null;
      const cs = getComputedStyle(el);
      const outlined = cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0;
      const shadow = cs.boxShadow !== "none";
      const name = el.getAttribute("aria-label") || el.getAttribute("data-testid") || el.textContent?.trim().slice(0, 30) || el.tagName;
      return { name: `${el.tagName.toLowerCase()}:${name}`, visibleFocus: outlined || shadow || el.closest(".cm-editor") !== null || el.classList.contains("react-flow__node") };
    });
    if (info) seen.push(info.name);
    if (info && !info.visibleFocus) throw new Error(`no visible focus indicator on ${info.name}`);
  }
  const joined = seen.join(" | ");
  for (const must of ["analyze-button", "export-button", "Switch to", "File name", "Search nodes", "tab-graph", "filter-type-TaskNode", "Fit view", "ul:Nodes"]) {
    expect(joined, `${must} is never reached with Tab`).toContain(must);
  }
  expect(new Set(seen).size).toBeGreaterThan(15); // not trapped on a few elements
  expect(seen.filter((n) => /fit view/i.test(n))).toHaveLength(1); // one Fit control, not two
  expect(seen.indexOf("button:analyze-button")).toBe(0);
  expect(seen.lastIndexOf("button:analyze-button")).toBeGreaterThan(0); // the order is a loop: focus wraps to the top

  // Export menu: Enter opens, the first link takes focus order, Escape closes it.
  await page.getByTestId("export-button").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("export-list")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("export-list")).toHaveCount(0);
});

test("keyboard: nodes can be selected and the inspector read without a mouse (node list)", async ({ page }) => {
  await page.goto("/");
  await setPrompt(page, "You are a bot.\nSummarize the report.\nNever lie.");
  await analyze(page);
  const list = page.getByRole("listbox", { name: "Nodes" });
  await list.focus();
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("inspector")).toBeVisible();
  await expect(page.getByTestId("inspector-original-text")).not.toBeEmpty();
});
