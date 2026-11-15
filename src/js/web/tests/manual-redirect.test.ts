// @vitest-environment node
import { spawnSync } from "node:child_process"
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import path from "node:path"
import { afterEach, describe, expect, it } from "vitest"

const repository = path.resolve(process.cwd(), "../../..")
const script = path.join(repository, "src/js/web/scripts/manual/build-manual-site.mjs")
const manifest = JSON.parse(readFileSync(path.join(repository, "docs/manual/woheng-showcase/manual-manifest.json"), "utf8"))
const directories: string[] = []

function fixture() {
  const root = mkdtempSync(path.join(tmpdir(), "manual-redirect-"))
  directories.push(root)
  const config = path.join(root, "manifest.json")
  const output = path.join(root, "site")
  writeFileSync(config, JSON.stringify(manifest))
  return { root, config, output, run: () => spawnSync(process.execPath, [script, "--manifest", config, "--outputDir", output], { encoding: "utf8" }) }
}

afterEach(() => {
  for (const directory of directories.splice(0)) rmSync(directory, { recursive: true, force: true })
})

describe("legacy manual canonical bridge", () => {
  it("replaces old bodies with 30 canonical targets and three explicit retired-page aliases", () => {
    const test = fixture()
    mkdirSync(path.join(test.output, "pages"), { recursive: true })
    writeFileSync(path.join(test.output, "pages/ghg-maintenance.html"), "old form instructions")
    expect(test.run().status).toBe(0)
    const audit = JSON.parse(readFileSync(path.join(test.output, "manual-audit.json"), "utf8"))
    expect(audit).toMatchObject({ mode: "canonical-redirect", canonicalPageCount: 30, legacyAliasCount: 3, generatedPageCount: 33 })
    for (const page of audit.pages) {
      const html = readFileSync(path.join(test.output, page.href), "utf8")
      expect(html).toContain(`<link rel="canonical" href="${page.target}"`)
      expect(html).toContain(`window.location.replace(${JSON.stringify(page.target)})`)
      expect(html).toContain(`content="0; url=${page.target}"`)
      expect(html).not.toContain("old form instructions")
      expect(html).not.toContain("<img")
      if (page.kind === "retired-page-alias") expect(page.target).toBe(manifest.canonicalDocsBaseUrl)
    }
  })

  it("leaves historical screenshots untouched and does not require screenshot sources", () => {
    const test = fixture()
    const assets = path.join(test.output, "assets/screenshots")
    mkdirSync(assets, { recursive: true })
    const oldImage = path.join(assets, "historical.png")
    writeFileSync(oldImage, "historical asset")
    expect(test.run().status).toBe(0)
    expect(readFileSync(oldImage, "utf8")).toBe("historical asset")
  })

  it("fails before writing if an old page lacks an explicit mapping", () => {
    const test = fixture()
    mkdirSync(path.join(test.output, "pages"), { recursive: true })
    writeFileSync(path.join(test.output, "index.html"), "original index")
    writeFileSync(path.join(test.output, "pages/unknown-page.html"), "old body")
    const result = test.run()
    expect(result.status).not.toBe(0)
    expect(result.stderr).toContain("旧手册页面缺少显式跳转映射")
    expect(readFileSync(path.join(test.output, "index.html"), "utf8")).toBe("original index")
  })
})
