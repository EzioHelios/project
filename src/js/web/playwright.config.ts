import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "./test-results/e2e-artifacts",
  reporter: [["list"], ["json", { outputFile: "./test-results/e2e-results.json" }]],
  use: {
    baseURL: "http://127.0.0.1:18101",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "bun run dev --host 127.0.0.1",
    url: "http://127.0.0.1:18101",
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
