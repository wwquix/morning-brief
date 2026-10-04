import { expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

for (const fixture of ["populated", "offline", "missing-tasks", "fallback"]) {
  test(`${fixture} opens as a portable file without network or clipped text`, async ({ page }) => {
    const errors = [];
    const external = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route(/^https?:/, (route) => {
      external.push(route.request().url());
      return route.abort();
    });
    await page.goto(pathToFileURL(resolve(`../output/test-fixtures/${fixture}.html`)).href);
    await expect(page.locator("h1")).toBeVisible();
    // Make lazy images load before checking portability.
    for (const img of await page.locator("img").all()) {
      await img.scrollIntoViewIfNeeded();
      await expect(img).toHaveJSProperty("complete", true);
      expect(await img.evaluate((el) => el.naturalWidth)).toBeGreaterThan(0);
      expect(await img.getAttribute("src")).toMatch(/^data:image\//);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    // The card's decorative pseudo-element intentionally scales beyond its edges.
    // Check text containers and their bounds rather than the background's scroll size.
    const clipped = await page.locator(".module-card-content, li, dd, strong").evaluateAll((elements) =>
      elements.filter((el) => el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1)
        .map((el) => el.textContent.slice(0, 50))
    );
    expect(clipped).toEqual([]);
    expect(await page.locator(".module-card-content").evaluateAll((elements) => elements.every((el) => {
      const text = el.getBoundingClientRect();
      const card = el.parentElement.getBoundingClientRect();
      return text.left >= card.left - 1 && text.right <= card.right + 1
        && text.top >= card.top - 1 && text.bottom <= card.bottom + 1;
    }))).toBe(true);
    expect(await page.evaluate(() => window.__injected)).toBeUndefined();
    expect(errors).toEqual([]);
    expect(external).toEqual([]);
    if (fixture === "populated") {
      await expect(page.locator(".cat-gallery img")).toHaveCount(3);
      await page.locator('a[href="#tasks"]').click();
      await expect(page).toHaveURL(/#tasks$/);
      await expect(page.locator("#tasks")).toBeInViewport();
      await page.locator('a[href="#cats-details"]').click();
      await expect(page.locator("#cats-details")).toBeInViewport();
      await expect(page.locator("#tasks")).not.toContainText("Уже выполнено");
    }
    if (fixture === "missing-tasks") {
      await expect(page.locator("#tasks")).toContainText("Не удалось прочитать tasks.md");
      await expect(page.locator("#tasks")).not.toContainText("Свободный день");
    }
  });
}
