import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { chromium, expect } from "@playwright/test"

const base = process.env.E2E_BASE_URL || "http://127.0.0.1:18101"
const out = path.resolve(process.env.E2E_ACCESS_OUTPUT || ".storage/home-layout")
const username = process.env.E2E_CUSTOMER_USERNAME
const password = process.env.E2E_CUSTOMER_PASSWORD
assert.ok(username && password, "Customer credentials required")
await fs.mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: "zh-CN" })
const page = await context.newPage()
page.setDefaultTimeout(30000)
const checks = []
const failures = []
let signedIn = false
page.on("response", (r) => {
  if (signedIn && new URL(r.url()).pathname.startsWith("/api/") && r.status() >= 400) failures.push({ path: new URL(r.url()).pathname, status: r.status() })
})
try {
  await page.goto(`${base}/login`)
  await page.getByLabel("账号", { exact: true }).fill(username)
  await page.getByLabel("密码", { exact: true }).fill(password)
  await page.getByRole("button", { name: "登录", exact: true }).click()
  await page.waitForURL("**/home")
  signedIn = true
  const functions = page.getByRole("region", { name: "业务功能", exact: true })
  const cards = functions.getByRole("link")
  await expect(cards).toHaveCount(12)
  assert.equal(new Set(await cards.evaluateAll((els) => els.map((el) => el.getAttribute("href")))).size, 12)
  for (const width of [375, 390, 430, 768, 1024, 1280, 1440, 1920]) {
    await page.setViewportSize({ width, height: 1000 })
    const result = await functions.evaluate((el) => {
      const grid = el.firstElementChild
      const boxes = [...grid.children].map((card) => card.getBoundingClientRect())
      return {
        width: window.innerWidth,
        available: el.clientWidth,
        columns: getComputedStyle(grid).gridTemplateColumns.split(" ").length,
        firstRow: boxes.filter((box) => Math.abs(box.top - boxes[0].top) < 1).length,
        horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
      }
    })
    const expected = result.available >= 1024 ? 4 : result.available >= 768 ? 3 : result.available >= 512 ? 2 : 1
    assert.equal(result.columns, expected)
    assert.equal(result.firstRow, expected)
    assert.equal(result.horizontalOverflow, false)
    if (width <= 430) assert.equal(result.columns, 1)
    if (width >= 1440) assert.equal(result.columns, 4)
    checks.push(result)
    if ([390, 1440, 1920].includes(width)) await page.screenshot({ path: path.join(out, `home-${width}.png`), fullPage: true, animations: "disabled" })
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
  const responsePromise = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/carbon/verification/projects")
  await functions.getByRole("link", { name: /核查支撑/ }).click()
  await page.waitForURL("**/carbon/verification")
  await expect(page.getByRole("heading", { name: "碳核查支撑", exact: true })).toBeVisible()
  assert.equal((await responsePromise).status(), 200)
  await page.screenshot({ path: path.join(out, "verification-access.png"), fullPage: true, animations: "disabled" })
  assert.deepEqual(failures, [])
  await fs.writeFile(path.join(out, "result.json"), JSON.stringify({ status: "passed", cardCount: 12, checks, failures, verification: "passed" }, null, 2))
  console.log(JSON.stringify({ status: "passed", checks, verification: "passed" }))
} finally {
  await browser.close()
}
