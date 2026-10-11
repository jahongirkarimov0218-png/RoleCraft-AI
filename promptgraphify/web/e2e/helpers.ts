import { expect, type Page } from "@playwright/test";

export const uniqueToken = () => `zq${Math.random().toString(36).slice(2, 10)}`;

/** Replace the editor content by typing, exactly like a user would. */
export async function setPrompt(page: Page, text: string) {
  const content = page.getByTestId("editor-content");
  await content.click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.press("Delete");
  await page.keyboard.type(text);
}

export async function analyze(page: Page) {
  await page.getByTestId("analyze-button").click();
  await expect(page.getByTestId("graph-stats")).toBeVisible();
}

export async function editorText(page: Page): Promise<string> {
  // CodeMirror renders one .cm-line per line; join them like the document does.
  return (await page.locator(".cm-line").allInnerTexts()).join("\n");
}
