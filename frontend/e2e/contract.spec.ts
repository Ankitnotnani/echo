import { expect, test } from "@playwright/test";

test("chat UI follows the data-testid contract", async ({ page }) => {
  await page.goto("/");
  const input = page.getByTestId("chat-input");
  await input.fill(`Contract check ${Date.now()}: reply with one short sentence.`);
  await page.getByTestId("send-button").click();
  await expect(input).toHaveValue("");

  const reply = page.getByTestId("assistant-message").first();
  await expect(reply).toBeVisible({ timeout: 90_000 });
  await expect(reply.getByTestId("meta-source")).toHaveText(/^(LIVE_INFERENCE|LLM_CACHE)$/);
  await expect(reply.getByTestId("meta-model")).not.toBeEmpty();
  await expect(reply.getByTestId("meta-latency")).toHaveText(/^\d+ ms$/);
  await expect(reply.getByTestId("meta-input-tokens")).toHaveText(/^\d+$/);
  await expect(reply.getByTestId("meta-output-tokens")).toHaveText(/^\d+$/);
});

test("a new session starts on each page load", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("assistant-message")).toHaveCount(0);
});
