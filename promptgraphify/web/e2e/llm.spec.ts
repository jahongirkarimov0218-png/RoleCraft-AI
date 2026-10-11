import { expect, test } from "@playwright/test";
import { editorText, setPrompt, uniqueToken } from "./helpers";

// The backend of this run is configured (PROMPTGRAPHIFY_LLM_*) to use e2e/fake-llm.mjs, a fake OpenAI-compatible
// provider on loopback. It answers like a very simple model: every uncovered span becomes a TaskNode.
const FAKE = "http://127.0.0.1:8002";

const completions = async (request: import("@playwright/test").APIRequestContext): Promise<number> =>
  (await (await request.get(`${FAKE}/__stats`)).json()).completions;

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("analyze-button")).toBeEnabled();
});

test("the LLM layer is opt-in: toggle off by default, local badge, and no request to the provider", async ({ page, request }) => {
  const token = uniqueToken();
  await expect(page.getByTestId("llm-toggle")).not.toBeChecked();
  await expect(page.getByTestId("llm-badge")).toContainText("Local analysis only");
  const before = await completions(request);

  await setPrompt(page, `You are a bot.\n${token} zork flimflam.\nSummarize the report.`);
  await page.getByTestId("analyze-button").click();
  await expect(page.getByTestId("graph-stats")).toBeVisible();
  expect(await completions(request)).toBe(before); // nothing was sent anywhere
  await expect(page.getByTestId("graph-node").filter({ hasText: token })).toHaveCount(0); // premise: the rules left it uncovered
  await expect(page.getByTestId("analysis-notes")).toHaveCount(0);
});

test("with the toggle on, the badge names the endpoint and an LLM-proposed node is marked, quoted and highlighted", async ({ page, request }) => {
  const token = uniqueToken();
  const quote = `${token} zork flimflam.`;
  await page.getByTestId("llm-toggle").check();
  await expect(page.getByTestId("llm-badge")).toContainText("LLM layer ON: prompt text is sent to 127.0.0.1:8002 (fake-model)");
  const before = await completions(request);

  await setPrompt(page, `You are a bot.\n${quote}\nSummarize the report.`);
  await page.getByTestId("analyze-button").click();
  const node = page.getByTestId("graph-node").filter({ hasText: token });
  await expect(node).toHaveCount(1);
  expect(await completions(request)).toBe(before + 1);
  await expect(node).toContainText("LLM");

  await node.click();
  await expect(page.getByTestId("inspector-original-text")).toHaveText(quote);
  await expect(page.getByText("llm:openai-compatible")).toBeVisible();
  await expect(page.getByTestId("llm-note")).toContainText("Proposed by the LLM layer");
  expect((await page.locator(".cm-hl-primary").allInnerTexts()).join("")).toBe(quote); // the span is the quote, in the source
  expect(await editorText(page)).toContain(quote);
  await expect(page.getByTestId("analysis-notes")).toContainText("accepted 1 node(s)");

  // The provider got the key only in the Authorization header, never in the page.
  expect(JSON.stringify(await (await request.get(`${FAKE}/__stats`)).json())).toContain("Bearer e2e-not-a-real-key");
  expect(await page.content()).not.toContain("e2e-not-a-real-key");
});

test("a provider failure leaves the deterministic graph in place and says so", async ({ page }) => {
  await page.getByTestId("llm-toggle").check();
  await setPrompt(page, `You are a bot.\n__LLM_DOWN__ zork flimflam.\nSummarize the report.`);
  await page.getByTestId("analyze-button").click();
  await expect(page.getByTestId("graph-stats")).toBeVisible();
  await expect(page.getByTestId("error-banner")).toHaveCount(0);
  await expect(page.getByTestId("analysis-notes")).toContainText("layer_b: unavailable");
  await expect(page.getByTestId("analysis-notes")).toContainText("HTTP 503");
  await expect(page.getByTestId("analysis-notes")).toContainText("deterministic result is returned");
  expect(await page.getByTestId("graph-node").count()).toBe(2); // the two nodes the rules found
});

test("turning the toggle off again restores the local badge", async ({ page }) => {
  await page.getByTestId("llm-toggle").check();
  await page.getByTestId("llm-toggle").uncheck();
  await expect(page.getByTestId("llm-badge")).toContainText("Local analysis only");
});
