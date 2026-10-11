import { expect, test } from "@playwright/test";
import { analyze, setPrompt } from "./helpers";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("analyze-button")).toBeEnabled();
});

const node = (page: import("@playwright/test").Page, text: string) =>
  page.locator('[data-testid="graph-canvas"][data-view="kg"] [data-testid="graph-node"]').filter({ hasText: text });

test("selecting a node keeps its neighbours at full strength and dims everything else; the pane click restores", async ({ page }) => {
  // two chains that share nothing: {{a}} belongs to the first task, {{b}} to the second
  await setPrompt(page, "Extract {{a}}.\nSummarize {{b}}.");
  await analyze(page);
  await expect(page.locator('[data-testid="graph-node"]')).toHaveCount(4);
  await expect(page.locator('[data-testid="graph-node"][data-dimmed="true"]')).toHaveCount(0); // nothing selected: nothing dimmed

  await node(page, "Extract {{a}}.").click();
  await expect(node(page, "Extract {{a}}.")).toHaveAttribute("data-dimmed", "false");
  await expect(page.locator('[data-testid="graph-node"][title="{{a}}"]')).toHaveAttribute("data-dimmed", "false"); // its variable
  await expect(page.locator('[data-testid="graph-node"][title="{{b}}"]')).toHaveAttribute("data-dimmed", "true");
  await expect(node(page, "Summarize {{b}}.")).toHaveAttribute("data-dimmed", "true");
  await expect(page.locator('[data-testid="graph-node"][data-dimmed="true"]')).toHaveCount(2); // the other task and {{b}}
  await expect(page.locator('[data-testid="graph-node"][data-dimmed="false"]')).toHaveCount(2); // the selected task and {{a}}

  await page.locator(".react-flow__pane").click({ position: { x: 5, y: 5 } });
  await expect(page.locator('[data-testid="graph-node"][data-dimmed="true"]')).toHaveCount(0);
});

test("a node can be dragged and keeps its new position", async ({ page }) => {
  await setPrompt(page, "Extract {{a}}.\nSummarize {{b}}.");
  await analyze(page);
  const target = node(page, "Summarize {{b}}.");
  await target.scrollIntoViewIfNeeded();
  const before = (await target.boundingBox())!;
  const cx = before.x + before.width / 2;
  const cy = before.y + before.height / 2;
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  await page.mouse.move(cx + 40, cy + 30, { steps: 5 });
  await page.mouse.move(cx + 90, cy + 60, { steps: 5 });
  await page.mouse.up();
  const after = (await target.boundingBox())!;
  // it follows the pointer (within the few pixels the drag threshold and the animated fit-view may take off)
  expect(Math.abs(after.x - (before.x + 90))).toBeLessThan(16);
  expect(Math.abs(after.y - (before.y + 60))).toBeLessThan(16);
  // and the other task did not move with it
  const other = (await node(page, "Extract {{a}}.").boundingBox())!;
  expect(other.x).toBeLessThan(after.x);
});
