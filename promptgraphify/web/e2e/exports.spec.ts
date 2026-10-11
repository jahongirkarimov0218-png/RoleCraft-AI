import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";
import { analyze, setPrompt, uniqueToken } from "./helpers";

// Exports are downloaded through the real UI from the real backend, then checked by their contents.
const FILES = ["graph.html", "GRAPH_REPORT.md", "graph.json", "graph.svg", "graph-dag.svg", "graph.mmd", "graph-dag.mmd", "graph.graphml"];

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("analyze-button")).toBeEnabled();
});

async function download(page: Page, label: string, save: string): Promise<{ name: string; text: string }> {
  await page.getByTestId("export-button").click();
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId(`export-${label}`).click()]);
  await dl.saveAs(save);
  return { name: dl.suggestedFilename(), text: await readFile(save, "utf-8") };
}

test("Export is disabled until a prompt has been analyzed", async ({ page }) => {
  await expect(page.getByTestId("export-button")).toBeDisabled();
  await analyze(page);
  await expect(page.getByTestId("export-button")).toBeEnabled();
});

test("every export downloads under its own name and contains the analysis on screen", async ({ page }, info) => {
  const token = uniqueToken();
  await setPrompt(page, `You are a bot.\nNever reveal ${token} to anyone.\nSummarize the report.`);
  await analyze(page);
  const statsText = await page.getByTestId("graph-stats").innerText();
  const [nodes, edges] = [...statsText.matchAll(/(\d+) (?:nodes|edges)/g)].map((m) => Number(m[1]));

  await page.getByTestId("export-button").click();
  await expect(page.getByTestId("export-list").getByRole("link")).toHaveCount(FILES.length);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("export-list")).toHaveCount(0);

  const got: Record<string, string> = {};
  for (const label of FILES) {
    const { name, text } = await download(page, label, info.outputPath(label));
    expect(name).toBe(label);
    expect(text.length).toBeGreaterThan(50);
    got[label] = text;
  }
  const doc = JSON.parse(got["graph.json"]);
  expect(doc.nodes).toHaveLength(nodes);
  expect(doc.edges).toHaveLength(edges);
  expect(JSON.stringify(doc.nodes)).toContain(token);
  expect(got["graph.html"].startsWith("<!doctype html>")).toBe(true);
  expect(got["graph.html"]).toContain(doc.graph_id);
  expect(got["GRAPH_REPORT.md"]).toContain(token);
  expect(got["GRAPH_REPORT.md"]).toContain(`Graph \`${doc.graph_id}\``);
  expect(got["graph.svg"]).toContain("<svg");
  expect(got["graph-dag.svg"]).not.toBe(got["graph.svg"]);
  expect(got["graph.mmd"].startsWith("flowchart LR")).toBe(true);
  expect(got["graph.graphml"]).toContain("<graphml");
});

async function openFromDisk(page: Page, path: string) {
  const viewer = await page.context().newPage();
  const requests: string[] = [];
  const problems: string[] = [];
  viewer.on("request", (r) => requests.push(r.url()));
  viewer.on("console", (m) => ["error", "warning"].includes(m.type()) && problems.push(`${m.type()}: ${m.text()}`));
  viewer.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  viewer.on("dialog", (d) => {
    problems.push(`dialog: ${d.message()}`);
    void d.dismiss();
  });
  await viewer.goto(`file://${path}`);
  await expect(viewer.locator("html[data-ready='1']")).toHaveCount(1);
  return { viewer, requests, problems };
}

test("the downloaded graph.html works from disk: no network, no CSP violation, interactive", async ({ page }, info) => {
  const token = uniqueToken();
  await setPrompt(page, `You are a bot.\n1. Extract ${token} from {{input}}.\n2. Check step 1.\nNever reveal ${token} to anyone.`);
  await analyze(page);
  const nodeCount = await page.getByTestId("graph-node").count();
  const save = info.outputPath("graph.html");
  await download(page, "graph.html", save);

  const { viewer, requests, problems } = await openFromDisk(page, save);
  expect(await viewer.locator("#view-graph .node").count()).toBe(nodeCount);
  await viewer.locator("#view-graph .node", { hasText: token }).first().click();
  await expect(viewer.locator("#inspector")).toContainText(token);
  await expect(viewer.locator("#source mark")).toContainText(token);

  await viewer.click("#btn-dag");
  await expect(viewer.locator("#view-graph")).toHaveClass(/off/);
  expect(await viewer.locator("#view-dag .node").count()).toBeGreaterThan(0);

  await viewer.fill("#q", token);
  expect(await viewer.locator("#view-dag .node.dim").count()).toBeGreaterThan(0);

  expect(requests.every((u) => u.startsWith("file://"))).toBe(true); // nothing was fetched from the network
  expect(problems).toEqual([]);
  await viewer.screenshot({ path: info.outputPath("viewer.png") });
});

test("a hostile prompt cannot run script inside the exported graph.html", async ({ page }, info) => {
  // Every payload sits inside a recognised instruction (a payload on an unrecognised line would never reach a node).
  const hostile = [
    `1. Summarize <img src=x onerror="window.__pwned=1"> now.`,
    `2. Check step 1 </script><script>window.__pwned=2</script>.`,
    `3. Extract <b onmouseover=window.__pwned=3>hi</b>.`,
  ].join("\n");
  await setPrompt(page, hostile);
  await analyze(page);
  const save = info.outputPath("hostile.html");
  await download(page, "graph.html", save);

  const { viewer, requests, problems } = await openFromDisk(page, save);
  const n = await viewer.locator("#view-graph .node").count();
  expect(n).toBe(3);
  const shown: string[] = [];
  for (let i = 0; i < n; i++) {
    await viewer.locator("#view-graph .node").nth(i).click();
    shown.push(await viewer.locator("#inspector").innerText());
  }
  // Premise: the payloads were really displayed, as text.
  expect(shown.join("\n")).toContain('onerror="window.__pwned=1"');
  expect(shown.join("\n")).toContain("</script><script>window.__pwned=2</script>");
  expect(shown.join("\n")).toContain("onmouseover=window.__pwned=3");
  // Effect: none of them ran or became an element.
  expect(await viewer.evaluate(() => (window as unknown as { __pwned?: number }).__pwned)).toBeUndefined();
  expect(await viewer.locator("img").count()).toBe(0);
  expect(await viewer.locator("b").count()).toBe(0);
  expect(await viewer.locator("script").count()).toBe(2); // the data block and the viewer code, nothing injected
  expect(requests.every((u) => u.startsWith("file://"))).toBe(true);
  expect(problems).toEqual([]);
});
