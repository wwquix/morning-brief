import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: { browserName: "chromium", headless: true, reducedMotion: "reduce" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
    { name: "narrow", use: { viewport: { width: 320, height: 740 } } }
  ]
});
