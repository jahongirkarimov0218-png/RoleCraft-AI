import { expect, test } from "@playwright/test";
import { analyze, setPrompt, uniqueToken } from "./helpers";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("analyze-button")).toBeEnabled();
});

test("the Execution DAG tab shows the topological order and the critical path", async ({ page }) => {
  await setPrompt(page, "1. Extract {{x}}.\n2. Check step 1.\n3. Summarize step 2.");
  await analyze(page);
  await page.getByTestId("tab-dag").click();
  await expect(page.getByTestId("dag-status")).toHaveText("ok");
  const order = await page.getByTestId("dag-order").locator("button").allInnerTexts();
  expect(order.map((t) => t.replace(/^\d+\.\s*/, ""))).toEqual(["x", "Extract {{x}}.", "Check step 1.", "Summarize step 2."]);
  await expect(page.getByTestId("dag-critical").locator("button")).toHaveCount(4);
  await expect(page.locator('[data-testid="graph-canvas"][data-view="dag"] [data-testid="graph-node"]')).toHaveCount(4);
});

test("a circular dependency blocks the DAG, explains itself and offers an acyclic subgraph", async ({ page }) => {
  await setPrompt(page, "1. Check step 2.\n2. Check step 1.");
  await analyze(page);
  await page.getByTestId("tab-dag").click();
  await expect(page.getByTestId("dag-status")).toHaveText("blocked");
  await expect(page.getByTestId("dag-cycle")).toContainText("proven");
  await expect(page.getByTestId("dag-order")).toHaveCount(0); // a blocked DAG shows no execution order
  const arrows = page.locator('[data-testid="graph-canvas"][data-view="dag"] .react-flow__edge');
  const before = await arrows.count();
  await page.getByTestId("dag-subgraph-toggle").check();
  await expect(page.getByTestId("dag-removed")).toBeVisible();
  await expect.poll(async () => arrows.count()).toBeLessThan(before);

  await page.getByTestId("tab-diagnostics").click();
  await expect(page.locator('[data-testid="diagnostic"][data-rule="dependency.cycle"]')).toContainText("proven");
});

test("diagnostics list findings with their certainty, and picking one marks the evidence in the editor", async ({ page }) => {
  const token = uniqueToken();
  await setPrompt(page, `Greet {{${token}}}.\nMake it good.`);
  await analyze(page);
  await page.getByTestId("tab-diagnostics").click();
  const undeclared = page.locator('[data-testid="diagnostic"][data-rule="variable.undeclared"]');
  await expect(undeclared).toContainText("proven");
  await expect(page.locator('[data-testid="diagnostic"][data-rule="instruction.ambiguous"]')).toContainText("probable");
  await undeclared.click();
  await expect(undeclared).toContainText("Fix:");
  expect((await page.locator(".cm-hl-evidence, .cm-hl-primary").allInnerTexts()).join("")).toContain(token);
  await expect(page.getByTestId("inspector")).toHaveAttribute("data-kind", "node");
  await page.getByTestId("diag-filter-warning").click();
  await expect(undeclared).toHaveCount(0); // filtered out by severity
});

test("a named query answers from the graph and its rows point at source evidence", async ({ page }) => {
  await setPrompt(page, "Variables:\n- spare: never used\n- used: used below\n\nGreet {{used}}.");
  await analyze(page);
  await page.getByTestId("tab-queries").click();
  await page.getByTestId("query-select").selectOption({ label: "Which variables are declared but never used?" });
  await expect(page.getByTestId("query-definition")).toContainText("declared");
  await page.getByTestId("query-run").click();
  await expect(page.getByTestId("query-result")).toHaveAttribute("data-status", "ok");
  const rows = page.getByTestId("query-row");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("spare");
  await rows.first().click();
  await expect(page.getByTestId("inspector-original-text")).toContainText("spare: never used");
});

test("an ambiguous name in a query lists candidates instead of guessing", async ({ page }) => {
  await setPrompt(page, "1. Extract the id.\n2. Extract the name.");
  await analyze(page);
  await page.getByTestId("tab-queries").click();
  await page.getByTestId("query-select").selectOption({ label: "Which ContextNodes does this TaskNode depend on?" });
  await page.getByTestId("query-param-task").fill("Extract");
  await page.getByTestId("query-run").click();
  await expect(page.getByTestId("query-result")).toHaveAttribute("data-status", "ambiguous");
  await expect(page.getByRole("list", { name: "Candidates" }).locator("li")).toHaveCount(2);
});

test("several files are analysed together and selecting a node opens its file", async ({ page }) => {
  const token = uniqueToken();
  await setPrompt(page, "You are the planner.\nPass the plan to the writer defined in writer.md.");
  await page.getByTestId("add-file").click();
  await page.getByTestId("file-name").fill("writer.md");
  await setPrompt(page, `You are the writer.\nWrite the ${token} article.`);
  await analyze(page);
  await expect(page.getByTestId("graph-stats")).toHaveText(/4 nodes/);
  await page.getByTestId("file-tab").first().click(); // back to prompt.md
  await expect(page.getByTestId("file-name")).toHaveValue("prompt.md");
  await page.getByTestId("tab-nodes").click();
  await page.getByTestId("node-list").getByRole("option", { name: new RegExp(token) }).click();
  await expect(page.getByTestId("file-name")).toHaveValue("writer.md"); // the editor switched to the node's file
  expect((await page.locator(".cm-hl-primary").allInnerTexts()).join("")).toContain(token);
});

test("a JSON prompt is analysed with escapes decoded and exact raw spans", async ({ page }) => {
  await page.getByTestId("file-name").fill("prompt.json");
  await setPrompt(page, String.raw`{"messages": [{"role": "system", "content": "You are a bot.\nSay \"hi\" first."}]}`);
  await analyze(page);
  await page.getByTestId("graph-node").filter({ hasText: "hi" }).click();
  await expect(page.getByTestId("inspector-original-text")).toHaveText(String.raw`Say \"hi\" first.`);
  expect((await page.locator(".cm-hl-primary").allInnerTexts()).join("")).toBe(String.raw`Say \"hi\" first.`);
  await expect(page.getByTestId("inspector")).toContainText('Say "hi" first.'); // the decoded view
});

test("deliberate loops are shown as loops, not as cycles", async ({ page }) => {
  await setPrompt(page, "1. Fetch the next page.\n2. Repeat step 1 until there are no more pages.");
  await analyze(page);
  await page.getByTestId("tab-dag").click();
  await expect(page.getByTestId("dag-status")).toHaveText("ok");
  await expect(page.getByTestId("dag-loops")).toBeVisible();
  await expect(page.getByTestId("dag-cycle")).toHaveCount(0);
});

test("a prompt that is only whitespace analyses to an empty, honest result", async ({ page }) => {
  await setPrompt(page, "   ");
  await analyze(page);
  await expect(page.getByTestId("graph-stats")).toHaveText(/0 nodes/);
  await page.getByTestId("tab-diagnostics").click();
  await expect(page.locator('[data-testid="diagnostic"][data-rule="input.empty"]')).toBeVisible();
});
