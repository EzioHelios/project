import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { chromium, expect } from "@playwright/test"

const base = process.env.E2E_BASE_URL || "http://127.0.0.1:18101"
const out = path.resolve(process.env.E2E_ACCESS_OUTPUT || ".storage/customer-bigscreen")
const username = process.env.E2E_CUSTOMER_USERNAME
const password = process.env.E2E_CUSTOMER_PASSWORD
assert.ok(username && password, "Customer credentials required")
await fs.mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, locale: "zh-CN" })
const page = await context.newPage()
page.setDefaultTimeout(30000)
const errors = []
const checks = []
page.on("response", (r) => {
  if (new URL(r.url()).pathname.startsWith("/api/") && r.status() >= 400) errors.push({ url: r.url(), status: r.status() })
})
try {
  await page.goto(`${base}/login`)
  await page.getByLabel("账号", { exact: true }).fill(username)
  await page.getByLabel("密码", { exact: true }).fill(password)
  await page.getByRole("button", { name: "登录", exact: true }).click()
  await page.waitForURL("**/home")
  await page.getByRole("button", { name: "态势大屏", exact: true }).click()
  await page.getByRole("link", { name: "态势总览", exact: true }).click()
  await expect(page.getByRole("dialog")).toContainText("虚拟基地和演示数据")
  await page.screenshot({ path: path.join(out, "custom-demo-notice.png"), animations: "disabled" })
  await page.getByRole("button", { name: "了解，进入大屏" }).click()
  const picker = page.getByRole("combobox", { name: "切换租户" })
  await expect(picker).toBeEnabled()
  await expect(picker.locator("option")).toHaveCount(2)
  const options = await picker.locator("option").evaluateAll((els) => els.filter((e) => e.value).map((e) => ({ id: e.value, name: e.textContent })))
  assert.deepEqual(options.map((t) => t.name).sort(), ["沃衡汽车泰州生产基地", "沃衡汽车湖州生产基地"].sort())
  for (const [index, team] of options.entries()) {
    await picker.selectOption(team.id)
    await expect(page.getByRole("heading", { level: 1 })).toContainText(team.name)
    for (const [slug, label] of [["overview", "态势总览"], ["monitor", "运行监测"], ["power", "电量监控"], ["carbon", "碳排管理"]]) {
      await page.getByRole("link", { name: label, exact: true }).click()
      await page.waitForURL(`**/bigscreen/${slug}`)
      await expect(page.getByRole("dialog")).toHaveCount(0)
      await expect(page.locator('[data-scene-status="ready"]')).toBeVisible({ timeout: 120000 })
      await expect(page.getByText(/正在读取仓库|正在加载|加载中/)).toHaveCount(0, { timeout: 60000 })
      await page.evaluate(() => document.fonts.ready)
      await page.waitForFunction(() => [...document.querySelectorAll('canvas')].length > 0)
      await page.screenshot({ path: path.join(out, `base-${index + 1}-${slug}.png`), animations: "disabled" })
      checks.push({ tenant: team.name, page: slug, passed: true })
    }
    const response = await context.request.get(`${base}/api/bigscreen/meta`, { headers: { "X-Team-Id": team.id } })
    assert.equal(response.status(), 200)
    assert.equal((await response.json()).data.is_demo, true)
  }
  await page.reload()
  await expect(page.getByRole("button", { name: "定制演示", exact: true })).toBeVisible()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await page.getByRole("button", { name: "定制演示", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await page.screenshot({ path: path.join(out, "custom-demo-notice.png"), animations: "disabled" })
  await page.getByRole("button", { name: "了解，进入大屏" }).click()
  const forbidden = await context.request.get(`${base}/api/bigscreen/meta`, { headers: { "X-Team-Id": "00000000-0000-7000-8000-000000000001" } })
  assert.equal(forbidden.status(), 403)
  await page.goto(`${base}/bigscreen/vision`)
  await expect(page.getByText("无权访问", { exact: true })).toBeVisible()
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(out, "acceptance.json"), JSON.stringify({ status: "passed", checks, errors, notice: "first-entry, refresh, switch, reopen verified", crossTenantStatus: 403 }, null, 2))
  console.log(`Customer bigscreen passed: ${checks.length} pages`)
} catch (error) {
  await fs.writeFile(path.join(out, "acceptance.json"), JSON.stringify({ status: "failed", error: error.message, checks, errors }, null, 2))
  await page.screenshot({ path: path.join(out, "failure.png") })
  throw error
} finally {
  await browser.close()
}
