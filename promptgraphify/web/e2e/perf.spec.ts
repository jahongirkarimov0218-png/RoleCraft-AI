import { writeFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { syntheticPrompt } from "./synthetic";

// Responsiveness on large graphs, in the real browser against the real backend. Headless Chromium paints in software,
// so absolute frame times are pessimistic; the thresholds are loose and exist to catch regressions, not to promise speed.
// The measured numbers are printed and attached to the test report; docs/PERFORMANCE.md quotes a run.

async function loadPrompt(page: Page, text: string) {
  await page.goto("/");
  await expect(page.getByTestId("analyze-button")).toBeEnabled();
  await page.getByTestId("editor-content").click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.press("Delete");
  await page.keyboard.insertText(text); // one input event: typing 9,000 characters key by key would measure Playwright
}

/** Frame durations (ms) of `frames` animation frames, sampled in the page while `during` runs. */
async function frameTimes(page: Page, frames: number, during: () => Promise<void>): Promise<number[]> {
  const sampler = page.evaluate(
    (n) =>
      new Promise<number[]>((resolve) => {
        const times: number[] = [];
        let last = performance.now();
        const tick = (t: number) => {
          times.push(t - last);
          last = t;
          if (times.length < n) requestAnimationFrame(tick);
          else resolve(times);
        };
        requestAnimationFrame(tick);
      }),
    frames,
  );
  await during();
  return sampler;
}

const stats = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  const q = (p: number) => s[Math.min(s.length - 1, Math.floor(p * s.length))];
  return { avg: +(xs.reduce((a, b) => a + b, 0) / xs.length).toFixed(1), p95: +q(0.95).toFixed(1), max: +s[s.length - 1].toFixed(1), frames: xs.length };
};

for (const units of [150, 600]) {
  test(`responsiveness with a ${units}-unit prompt`, async ({ page }, info) => {
    test.setTimeout(180_000);
    const text = syntheticPrompt(units);
    await loadPrompt(page, text);
    const result: Record<string, unknown> = { units, chars: text.length };

    // 1. Analyze -> graph on screen (request, layout, first paint of the graph)
    const t0 = Date.now();
    const response = page.waitForResponse((r) => r.url().includes("/api/analyze") && r.request().method() === "POST");
    await page.getByTestId("analyze-button").click();
    const api = await response;
    const tApi = Date.now() - t0;
    await expect(page.getByTestId("graph-stats")).toBeVisible();
    await expect(page.getByTestId("graph-node").first()).toBeVisible();
    result.analyzeToResponseMs = tApi;
    result.analyzeToGraphMs = Date.now() - t0;
    const stat = await page.getByTestId("graph-stats").innerText();
    const nodes = Number(/(\d+) nodes/.exec(stat)![1]);
    result.nodes = nodes;
    result.responseKB = Math.round((await api.body()).length / 1024);
    expect(nodes).toBeGreaterThan(units * 0.9);
    await page.waitForTimeout(600); // let fit-view finish
    result.renderedNodesInDom = await page.getByTestId("graph-node").count(); // only visible ones are rendered

    // 2. Select a node -> inspector
    const target = page.getByTestId("graph-node").nth(2);
    const t1 = Date.now();
    await target.click();
    await expect(page.getByTestId("inspector")).toBeVisible();
    result.selectNodeMs = Date.now() - t1;

    // 3. Search: how long seven keystrokes take (the input must stay responsive) and when the graph has caught up
    await page.getByTestId("search").click();
    const t2 = Date.now();
    await page.keyboard.type("invoice", { delay: 0 });
    result.typeSevenKeysMs = Date.now() - t2;
    await expect(page.getByTestId("search")).toHaveValue("invoice");
    await page.waitForFunction(() => document.querySelector('[data-testid="graph-node"].opacity-25') !== null);
    result.searchAppliedMs = Date.now() - t2;
    await page.getByTestId("search").fill("");

    // 4. Zoom and pan frame times
    const box = (await page.getByTestId("graph-canvas").boundingBox())!;
    const cx = box.x + box.width / 2;
    const cy = box.y + box.height / 2;
    await page.mouse.move(cx, cy);
    const zoom = await frameTimes(page, 60, async () => {
      for (let i = 0; i < 20; i++) {
        await page.mouse.wheel(0, i < 10 ? -120 : 120);
        await page.waitForTimeout(16);
      }
    });
    const pan = await frameTimes(page, 60, async () => {
      await page.mouse.move(cx, cy);
      await page.mouse.down();
      for (let i = 0; i < 30; i++) await page.mouse.move(cx + i * 6, cy + i * 3);
      await page.mouse.up();
    });
    result.zoomFrames = stats(zoom);
    result.panFrames = stats(pan);

    // 5. Fit view and the DAG tab
    const t3 = Date.now();
    await page.getByTestId("fit-view").click();
    await page.waitForTimeout(250);
    result.fitViewMs = Date.now() - t3 - 250;
    const t4 = Date.now();
    await page.getByTestId("tab-dag").click();
    await expect(page.getByTestId("dag-panel")).toBeVisible();
    await expect(page.getByTestId("graph-node").first()).toBeVisible();
    result.switchToDagMs = Date.now() - t4;

    console.log("PERF " + JSON.stringify(result));
    writeFileSync(info.outputPath(`perf-${units}.json`), JSON.stringify(result, null, 2));
    await info.attach(`perf-${units}`, { body: JSON.stringify(result, null, 2), contentType: "application/json" });

    // Loose guards: a regression to seconds-per-interaction fails; ordinary noise does not.
    expect(result.analyzeToGraphMs as number).toBeLessThan(units === 150 ? 10_000 : 30_000);
    expect(result.selectNodeMs as number).toBeLessThan(1_500);
    expect(result.typeSevenKeysMs as number).toBeLessThan(3_000);
    expect(result.searchAppliedMs as number).toBeLessThan(6_000);
    expect(stats(zoom).avg).toBeLessThan(120);
    expect(stats(pan).avg).toBeLessThan(120);
  });
}
