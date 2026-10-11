import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

// The Mermaid export is validated by the real Mermaid parser (a dev-only dependency), not by regexes.
const PROMPTS: Record<string, string> = {
  simple: "# Task\nYou are a support bot.\n1. Extract the ticket id from {{ticket}}.\n2. Check step 1.\n3. Summarize step 2.\n\n## Rules\n- Never promise a refund.\n- Keep every answer under 50 words.\n",
  hostile: [
    `1. Summarize </script><script>window.__pwned=2</script> now.`,
    `2. Check step 1 "onmouseover="alert(1)" <img src=x onerror="window.__pwned=1">.`,
    "3. Extract `a``b` | pipe | [link](javascript:alert(1)) <b>bold</b> ]]> & --> %% {x} (y) [z].",
    "4. Summarize step 3 \u202eevil: colon; semicolon; #hash.",
  ].join("\n"),
  cycle: "1. Check step 2.\n2. Check step 1.\n",
  undefinedTool: "1. Look up the order with the search_orders tool.\n",
  oneLine: "You are a helpful assistant.\n",
  quotes: `1. Say "hello" and 'bye' then extract {{a}}.\n2. Check step 1 and send it with the notify tool.\n`,
};

async function exportMermaid(request: APIRequestContext, text: string, view: "graph" | "dag"): Promise<string> {
  const res = await request.post("/api/analyze", { data: { files: [{ path: "p.md", text }] } });
  expect(res.ok()).toBe(true);
  const { graph_id } = await res.json();
  const out = await request.get(`/api/graph/${graph_id}/export/mermaid?view=${view}`);
  expect(out.ok()).toBe(true);
  return out.text();
}

async function withMermaid(page: Page) {
  await page.goto("about:blank");
  await page.addScriptTag({ path: "node_modules/mermaid/dist/mermaid.min.js" });
  await page.evaluate(() => (window as any).mermaid.initialize({ startOnLoad: false, securityLevel: "strict" }));
}

const parse = (page: Page, text: string) =>
  page.evaluate(async (t) => {
    try {
      return { ok: Boolean(await (window as any).mermaid.parse(t)) };
    } catch (e) {
      return { ok: false, error: String((e as Error).message ?? e).slice(0, 200) };
    }
  }, text);

test("the parser rejects invalid Mermaid (so a pass below means something)", async ({ page }) => {
  await withMermaid(page);
  expect((await parse(page, 'flowchart LR\n  a["unterminated\n  a --> ')).ok).toBe(false);
  expect((await parse(page, "flowchart LR\n  a[x] --> b[y]\n")).ok).toBe(true);
});

for (const view of ["graph", "dag"] as const) {
  for (const [name, text] of Object.entries(PROMPTS)) {
    test(`Mermaid (${view} view) of "${name}" is accepted by the official parser and renders without script`, async ({ page, request }) => {
      const mmd = await exportMermaid(request, text, view);
      await withMermaid(page);
      const parsed = await parse(page, mmd);
      expect(parsed, mmd).toEqual({ ok: true });
      const svg = await page.evaluate(async (t) => (await (window as any).mermaid.render("g" + Math.random().toString(36).slice(2), t)).svg, mmd);
      expect(svg).toContain("<svg");
      // Structural check on the parsed (inert) DOM: payload text may appear escaped, but never as an element or handler.
      const unsafe = await page.evaluate((markup) => {
        const doc = new DOMParser().parseFromString(markup, "text/html");
        const elements = doc.querySelectorAll("script, img, iframe, object, embed, link, form, a[href^='javascript']");
        const handlers = [...doc.querySelectorAll("*")].flatMap((el) => el.getAttributeNames().filter((n) => n.startsWith("on")));
        return { elements: elements.length, handlers };
      }, svg);
      expect(unsafe).toEqual({ elements: 0, handlers: [] });
      expect(await page.evaluate(() => (window as any).__pwned)).toBeUndefined();
    });
  }
}
