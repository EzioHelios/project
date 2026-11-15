import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const repositoryRoot = path.resolve(scriptDir, "../../../../..")
const args = parseArgs(process.argv.slice(2))
const manifestPath = path.resolve(repositoryRoot, args.manifest ?? "docs/manual/woheng-showcase/manual-manifest.json")
const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"))
const outputDir = path.resolve(repositoryRoot, args.outputDir ?? manifest.siteOutputDir ?? path.dirname(manifest.htmlOutput))
const baseUrl = new URL(manifest.canonicalDocsBaseUrl)
if (baseUrl.protocol !== "https:" || baseUrl.search || baseUrl.hash) throw new Error("canonicalDocsBaseUrl 必须是不含查询参数或锚点的 HTTPS 地址")
const canonicalBase = baseUrl.href.replace(/\/$/, "")
const canonicalPages = [...manifest.pages.map((page) => page.pageId), ...(manifest.canonicalExtraPageIds ?? [])]
const canonicalIds = new Set(canonicalPages)
if (canonicalIds.size !== canonicalPages.length || !canonicalIds.has("overview")) throw new Error("正式文档页面重复或缺少 overview")
const aliases = manifest.legacyPageRedirects ?? {}
for (const id of [...canonicalPages, ...Object.keys(aliases)]) {
  if (!/^[a-z0-9-]+$/.test(id)) throw new Error(`无效手册页面编号：${id}`)
}
for (const [alias, target] of Object.entries(aliases)) {
  if (canonicalIds.has(alias) || !canonicalIds.has(target)) throw new Error(`旧页面映射无效：${alias} -> ${target}`)
}

// Optional checkout validation; production builds do not require the docs repository.
if (args.canonicalRoot) {
  const root = path.resolve(repositoryRoot, args.canonicalRoot)
  const actual = (await fs.readdir(root)).filter((name) => name.endsWith(".md")).map((name) => name.slice(0, -3))
  const differences = [...actual.filter((id) => !canonicalIds.has(id)), ...canonicalPages.filter((id) => !actual.includes(id))]
  if (differences.length) throw new Error(`正式文档页面与映射不一致：${differences.join(", ")}`)
}

const targetUrl = (id) => id === "overview" ? canonicalBase : `${canonicalBase}/${id}`
const pages = canonicalPages.map((id) => ({
  pageId: id,
  href: id === "overview" ? "index.html" : `pages/${id}.html`,
  target: targetUrl(id),
  kind: "canonical-page",
}))
for (const [alias, target] of Object.entries(aliases)) {
  pages.push({ pageId: alias, href: `pages/${alias}.html`, target: targetUrl(target), kind: "retired-page-alias" })
}

// Never leave an unrecognized old body accessible, or silently discard its URL.
const knownFiles = new Set(pages.map((page) => page.href))
const oldPages = await fs.readdir(path.join(outputDir, "pages")).catch((error) => {
  if (error.code === "ENOENT") return []
  throw error
})
const unmapped = oldPages.filter((name) => name.endsWith(".html") && !knownFiles.has(`pages/${name}`))
if (unmapped.length) throw new Error(`旧手册页面缺少显式跳转映射：${unmapped.join(", ")}`)

await fs.mkdir(path.join(outputDir, "pages"), { recursive: true })
for (const page of pages) await fs.writeFile(path.join(outputDir, page.href), renderRedirect(page.target))
const audit = {
  title: `${manifest.title} 旧地址跳转审计`,
  mode: "canonical-redirect",
  canonicalBase,
  canonicalPageCount: canonicalPages.length,
  legacyAliasCount: Object.keys(aliases).length,
  generatedPageCount: pages.length,
  imagePolicy: "保留历史图片；生成器不读取、复制或更新截图。正式截图只在 canonical docs 中维护。",
  pages,
}
await fs.writeFile(path.join(outputDir, "site-map.json"), `${JSON.stringify({ title: manifest.title, mode: audit.mode, pages }, null, 2)}\n`)
await fs.writeFile(path.join(outputDir, "manual-audit.json"), `${JSON.stringify(audit, null, 2)}\n`)
process.stdout.write(`[manual:redirects] ${pages.length} pages -> ${canonicalBase}\n`)
process.stdout.write(`[manual:written] ${outputDir}\n`)

function renderRedirect(target) {
  const escaped = target.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="noindex, follow" />
  <meta http-equiv="refresh" content="0; url=${escaped}" />
  <link rel="canonical" href="${escaped}" />
  <title>能碳管理平台操作手册</title>
  <script>window.location.replace(${JSON.stringify(target)});</script>
</head>
<body>
  <h1>操作手册已迁移</h1>
  <p><a href="${escaped}">打开最新操作手册</a></p>
</body>
</html>
`
}

function parseArgs(rawArgs) {
  const parsed = {}
  for (let index = 0; index < rawArgs.length; index++) {
    const arg = rawArgs[index]
    if (!arg.startsWith("--")) continue
    const next = rawArgs[index + 1]
    parsed[arg.slice(2)] = !next || next.startsWith("--") ? "1" : next
    if (next && !next.startsWith("--")) index++
  }
  return parsed
}
