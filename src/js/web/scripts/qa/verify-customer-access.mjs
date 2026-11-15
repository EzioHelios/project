import assert from "node:assert/strict"
import fs from "node:fs/promises"
import path from "node:path"
import { chromium, expect } from "@playwright/test"

const base = process.env.E2E_BASE_URL || "http://127.0.0.1:18101"
const username = process.env.E2E_CUSTOMER_USERNAME
const password = process.env.E2E_CUSTOMER_PASSWORD
assert.ok(username && password, "Provide E2E_CUSTOMER_USERNAME and E2E_CUSTOMER_PASSWORD")
const out = path.resolve(process.env.E2E_ACCESS_OUTPUT || ".storage/customer-access")
await fs.mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "zh-CN" })
const page = await context.newPage()
page.setDefaultTimeout(20000)
let activeTeamId = null
let track = false
let currentRoute = ""
const failures = []
const checks = []
const diagnostics = []
page.on("response", (r) => { if (new URL(r.url()).pathname.startsWith("/api/")) diagnostics.push({path: new URL(r.url()).pathname, status:r.status()}) })
page.on("console", (m) => { if(diagnostics.length < 300) diagnostics.push({console: m.text()}) })
page.on("response", (response) => {
  if (track && new URL(response.url()).pathname.startsWith("/api/") && response.status() >= 400) failures.push({ route: currentRoute, path: new URL(response.url()).pathname, status: response.status() })
})
let csrfToken
async function api(url, method = "GET", data) {
  const headers = { "Content-Type": "application/json" }
  if (activeTeamId) headers["X-Team-Id"] = activeTeamId
  if (csrfToken) headers["X-XSRF-TOKEN"] = csrfToken
  const response = await context.request.fetch(`${base}${url}`, { method, headers, data })
  return { status: response.status(), body: await response.json().catch(() => null) }
}

const routes = ["/energy/consumption", "/energy/intensity", "/energy/analysis", "/energy/benchmark", "/energy/flow", "/energy/balance", "/energy/budget", "/carbon/organization/records", "/carbon/product-footprint", "/carbon/supply-chain", "/carbon/verification", "/carbon/assets/overview"]
try {
  await page.goto(`${base}/login`)
  await page.getByLabel("账号", { exact: true }).fill(username)
  await page.getByLabel("密码", { exact: true }).fill(password)
  await page.getByRole("button", { name: "登录", exact: true }).click()
  await page.waitForURL("**/home")
  csrfToken = await page.evaluate(() => window.__LITESTAR_CSRF__)
  const profile = await api("/api/me")
  assert.equal(profile.status, 200)
  assert.equal(profile.body.isSuperuser, false)
  const permissions = await api("/api/me/permissions")
  assert.equal(permissions.status, 200)
  assert.equal(permissions.body.isSuperuser, false)
  const response = await api("/api/teams?limit=200")
  assert.equal(response.status, 200)
  const teams = response.body.items ?? response.body.data?.items ?? response.body
  assert.deepEqual(teams.map((t) => t.slug).sort(), ["woheng-huzhou-production-base", "woheng-taizhou-production-base"])
  checks.push({ name: "identity-and-tenants", passed: true, username, tenants: teams.map((t) => t.name), permissionCount: permissions.body.permissions.length })
  for (const team of teams) {
    activeTeamId = team.id
    await page.evaluate(({ team, user }) => localStorage.setItem("auth-storage", JSON.stringify({ state: { isAuthenticated: true, currentTeam: team, user }, version: 0 })), { team, user: profile.body })
    await page.goto(`${base}/home`)
    await expect(page.getByRole("link", { name: /查看明细/ })).toBeVisible()
    const homeLinks = await page.locator("main a[href]").evaluateAll((nodes) => nodes.map((n) => n.getAttribute("href")))
    for (const route of routes) assert.ok(homeLinks.includes(route), `Home missing ${route}`)
    const links = await page.locator("a[href]").evaluateAll((nodes) => nodes.map((n) => n.getAttribute("href")))
    assert.ok(!links.some((link) => /^\/(admin|auth|microgrid|bigscreen|mobile|tasks)(\/|$)/.test(link)), "Excluded links present")
    await page.screenshot({ path: path.join(out, `${team.slug}-home.png`) })
    for (const route of [...routes, "/profile", "/data/company", "/data/monitor-area", "/data/terminals", "/data/energy-consumption", "/data/energy-types", "/data/energy-unit-conversions", "/data/energy-benchmark", "/data/energy-budget", "/data/production-products", "/data/production-output", "/data/product-prices", "/data/product-resource-bindings", "/data/commute", "/data/inbound", "/data/outbound", "/data/material-handling", "/data/meter", "/carbon-mgmt/sources", "/carbon-mgmt/activities", "/carbon-mgmt/factors", "/carbon-mgmt/calculation-factors", "/carbon-mgmt/category/1.1", "/carbon-mgmt/category/2.1", "/carbon-mgmt/category/3.3", "/carbon/organization/reports", "/carbon/organization/boundary"]) {
      track = true
      currentRoute = route
      await page.goto(`${base}${route}`)
      await page.waitForLoadState("networkidle", { timeout: 20000 })
      await page.evaluate(() => document.fonts.ready)
      assert.equal(new URL(page.url()).pathname, route, `Unexpected navigation for ${route}`)
      await expect(page.locator("h1").first()).toBeVisible()
      await expect(page.getByText("无权访问", { exact: true })).toHaveCount(0)
      await expect(page.getByText("Something went wrong", { exact: true })).toHaveCount(0)
      checks.push({ name: "page", tenant: team.slug, route, passed: true })
      track = false
    }
    for (const [method, endpoint] of [
      ["GET", "/api/admin/users"], ["GET", "/api/admin/teams"], ["GET", "/api/system/tasks"],
      ["GET", "/api/microgrid/overview"], ["GET", "/api/vision/dashboard"], ["GET", "/api/bigscreen/overview"],
      ["GET", "/api/energy-carbon/alerts"], ["GET", "/api/mobile/work-orders"], ["POST", "/api/teams"],
      ["POST", "/api/ghg-inventory/reports/permission-probe/1/publish"],
    ]) {
      const result = await api(endpoint, method, method === "POST" ? {} : undefined)
      assert.equal(result.status, 403, `${method} ${endpoint}: ${result.status}`)
      checks.push({ name: "denied-api", tenant: team.slug, method, endpoint, status: result.status })
    }
    const own = activeTeamId
    activeTeamId = "00000000-0000-7000-8000-000000000001"
    assert.equal((await api("/api/energy/interval-facts")).status, 403)
    activeTeamId = own
    for (const route of ["/admin/users", "/microgrid/overview", "/bigscreen/vision", "/mobile/energy"]) {
      await page.goto(`${base}${route}`)
      await expect(page.getByText("无权访问", { exact: true })).toBeVisible()
      assert.equal(new URL(page.url()).pathname, "/forbidden")
      checks.push({ name: "denied-page", tenant: team.slug, route, passed: true })
    }
  }
  assert.deepEqual(failures, [], "Allowed pages must not request forbidden APIs")
  await fs.writeFile(path.join(out, "acceptance.json"), JSON.stringify({ status: "passed", base, checks, failures }, null, 2))
  console.log(`Customer access verified: ${checks.length} checks`)
} catch (error) {
  await fs.writeFile(path.join(out, "acceptance.json"), JSON.stringify({ status: "failed", base, checks, failures, diagnostics, error: error.message }, null, 2))
  await page.screenshot({ path: path.join(out, "failure.png") }).catch(() => {})
  throw error
} finally {
  await browser.close()
}
