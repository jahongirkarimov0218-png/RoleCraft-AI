import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { analyze } from "./helpers";

// Layout at six viewport sizes in both themes: no horizontal page scroll, the primary action stays reachable, panels can
// be switched on small screens, axe is clean on the compact layout, and interactive targets are at least 24x24 CSS px
// (WCAG 2.2 AA, 2.5.8). Screenshots are written to the test output for review.
const SIZES = [
  { name: "phone-small", width: 360, height: 640 },
  { name: "phone", width: 390, height: 844 },
  { name: "tablet-portrait", width: 768, height: 1024 },
  { name: "tablet-landscape", width: 1024, height: 768 },
  { name: "laptop", width: 1440, height: 900 },
  { name: "wide", width: 2560, height: 1440 },
];

async function loadExample(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("analyze-button")).toBeEnabled();
  await page.getByRole("button", { name: "Load example" }).click();
  await page.getByTestId("analyze-button").click();
  await expect(page.getByTestId("graph-stats")).toBeVisible();
}

const overflow = (page: Page) =>
  page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth, bodyScrollWidth: document.body.scrollWidth }));

const smallTargets = (page: Page) =>
  page.evaluate(() => {
    const sel = 'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"], [role="option"], [role="tab"], [tabindex="0"]';
    const out: string[] = [];
    for (const el of document.querySelectorAll<HTMLElement>(sel)) {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      if (r.width === 0 || r.height === 0 || cs.visibility === "hidden" || cs.display === "none") continue;
      if (el.closest(".react-flow__minimap, .react-flow__node, .react-flow__edge, .cm-editor")) continue; // graph surface and editor are not button targets
      if (el.matches('input[type="checkbox"]') && el.closest("label")) continue; // the label is the target
      if (r.width < 24 || r.height < 24) out.push(`${el.tagName.toLowerCase()}[${el.getAttribute("aria-label") ?? el.getAttribute("data-testid") ?? el.textContent?.trim().slice(0, 20)}] ${Math.round(r.width)}x${Math.round(r.height)}`);
    }
    return out;
  });

for (const theme of ["dark", "light"] as const) {
  for (const size of SIZES) {
    test(`layout at ${size.name} ${size.width}x${size.height} (${theme})`, async ({ page }, info) => {
      test.setTimeout(90_000);
      await page.setViewportSize({ width: size.width, height: size.height });
      await loadExample(page);
      if ((await page.evaluate(() => document.documentElement.dataset.theme)) !== theme) {
        await page.getByRole("button", { name: /Switch to (light|dark) theme/ }).click();
      }
      await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe(theme);

      const compact = size.width < 1024;
      const o = await overflow(page);
      expect(o.scrollWidth).toBeLessThanOrEqual(o.innerWidth);

      // The primary action is on screen at every size.
      await expect(page.getByTestId("analyze-button")).toBeInViewport();

      if (compact) {
        const nav = page.getByRole("navigation", { name: "Panels" });
        await expect(nav).toBeVisible();
        await nav.getByRole("button", { name: "graph" }).click();
        await expect(page.getByTestId("graph-canvas")).toBeVisible();
        await expect(page.getByTestId("graph-node").first()).toBeVisible();
        await page.screenshot({ path: info.outputPath(`${size.name}-${theme}-graph.png`) });
        await nav.getByRole("button", { name: "details" }).click();
        await expect(page.getByTestId("node-list")).toBeVisible();
        await page.screenshot({ path: info.outputPath(`${size.name}-${theme}-details.png`) });
        await nav.getByRole("button", { name: "editor" }).click();
        await expect(page.getByTestId("editor-content")).toBeVisible();
        await page.screenshot({ path: info.outputPath(`${size.name}-${theme}-editor.png`) });
      } else {
        await expect(page.getByTestId("editor-content")).toBeVisible();
        await expect(page.getByTestId("graph-canvas")).toBeVisible();
        await expect(page.getByTestId("node-list")).toBeVisible();
        await page.screenshot({ path: info.outputPath(`${size.name}-${theme}.png`) });
      }

      const violations = (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]).analyze()).violations;
      expect(violations.map((v) => `${v.id}: ${v.nodes.slice(0, 2).map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
      expect(await smallTargets(page), "interactive targets smaller than 24x24 px").toEqual([]);
    });
  }
}
