import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const webRoot = path.resolve(scriptDir, "../..")
const repositoryRoot = path.resolve(webRoot, "../../..")
const args = parseArgs(process.argv.slice(2))

const manifestPath = path.resolve(repositoryRoot, args.manifest ?? "docs/manual/woheng-showcase/manual-manifest.json")
const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"))
const outputDir = path.resolve(repositoryRoot, args.outputDir ?? manifest.siteOutputDir ?? path.dirname(manifest.htmlOutput))
const screenshotRoot = path.resolve(repositoryRoot, args.screenshots ?? manifest.defaultScreenshotRoot ?? "")
const pagesRoot = path.resolve(repositoryRoot, manifest.pagesRoot)
const screenshotIndex = await buildScreenshotIndex(screenshotRoot)
const evidencePlan = await readEvidencePlan(manifest.sourceEvidencePlan)
const audit = buildAudit(manifest, screenshotIndex, evidencePlan)
const screenshotAssets = await copyScreenshots(audit.rows)
const pageRecords = []

await fs.mkdir(outputDir, { recursive: true })
await fs.rm(path.join(outputDir, "pages"), { recursive: true, force: true })
await fs.mkdir(path.join(outputDir, "pages"), { recursive: true })

for (const [index, page] of (manifest.pages ?? []).entries()) {
  const sourcePath = path.join(pagesRoot, page.source)
  const markdown = await fs.readFile(sourcePath, "utf8")
  const filename = index === 0 ? "index.html" : `pages/${page.pageId}.html`
  const targetPath = path.join(outputDir, filename)
  const html = renderPage({
    manifest,
    currentPage: page,
    currentIndex: index,
    markdown,
    audit,
    screenshotAssets,
    evidencePlan,
    relativePrefix: index === 0 ? "" : "../",
  })
  await fs.writeFile(targetPath, html)
  pageRecords.push({ ...page, href: filename })
}

await fs.writeFile(path.join(outputDir, "site-map.json"), `${JSON.stringify({ title: manifest.title, pages: pageRecords }, null, 2)}\n`)
await fs.writeFile(path.join(outputDir, "manual-audit.json"), `${JSON.stringify(audit, null, 2)}\n`)
process.stdout.write(`[manual:written] ${outputDir}/index.html\n`)
process.stdout.write(`[manual:pages] ${pageRecords.length}\n`)
process.stdout.write(`[manual:audit] total=${audit.totalEvidence} screenshots=${audit.availableScreenshots} missing=${audit.missingScreenshots}\n`)

async function readEvidencePlan(planPath) {
  if (!planPath) return { items: [], byId: new Map() }
  const fullPath = path.resolve(repositoryRoot, planPath)
  const data = JSON.parse(await fs.readFile(fullPath, "utf8").catch(() => "{}"))
  const items = []
  for (const section of data.sections ?? []) {
    for (const item of section.items ?? []) items.push({ ...item, section: section.section })
  }
  return { items, byId: new Map(items.map((item) => [item.evidenceId, item])) }
}

function buildAudit(_manualManifest, screenshots, plan) {
  const rows = []
  for (const item of plan.items) {
    const screenshot = path.basename(item.plannedFilename ?? "")
    const match = resolveScreenshot({ evidenceId: item.evidenceId, screenshot }, screenshots)
    rows.push({
      section: item.section,
      title: item.title,
      route: item.route,
      evidenceId: item.evidenceId,
      screenshot,
      sourcePath: match ?? "",
      status: match ? "ready" : "missing-screenshot",
      mustVisibleContents: item.mustVisibleContents ?? [],
      focus: item.focus ?? "",
      expectedEvidenceLevel: item.expectedEvidenceLevel ?? "",
    })
  }
  return {
    title: `${manifest.title} 截图审计`,
    generatedAt: new Date().toISOString(),
    screenshotRoot: path.relative(repositoryRoot, screenshotRoot),
    totalEvidence: rows.length,
    availableScreenshots: rows.filter((row) => row.status === "ready").length,
    missingScreenshots: rows.filter((row) => row.status !== "ready").length,
    rows,
  }
}

async function copyScreenshots(rows) {
  const assets = new Map()
  const targetDir = path.join(outputDir, "assets", "screenshots")
  await fs.rm(targetDir, { recursive: true, force: true })
  await fs.mkdir(targetDir, { recursive: true })
  for (const row of rows) {
    if (!row.sourcePath) continue
    const filename = `${row.evidenceId}-${slugify(row.title)}${path.extname(row.sourcePath)}`
    const targetPath = path.join(targetDir, filename)
    await fs.copyFile(row.sourcePath, targetPath)
    assets.set(row.evidenceId, `assets/screenshots/${filename}`)
  }
  return assets
}

async function buildScreenshotIndex(root) {
  const index = new Map()
  if (!root) return index
  const files = await listFiles(root).catch(() => [])
  for (const file of files.filter((item) => /\.(png|jpe?g|webp|gif|svg)$/i.test(item))) {
    const basename = path.basename(file)
    index.set(basename, file)
    const idMatch = basename.match(/(EV-[A-Z]+-\d+|EVD-[A-Z0-9-]+)/)
    if (idMatch && !index.has(idMatch[1])) index.set(idMatch[1], file)
  }
  return index
}

async function listFiles(root) {
  const entries = await fs.readdir(root, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const fullPath = path.join(root, entry.name)
    if (entry.isDirectory()) files.push(...(await listFiles(fullPath)))
    else files.push(fullPath)
  }
  return files
}

function resolveScreenshot(step, screenshots) {
  return screenshots.get(step.screenshot) ?? screenshots.get(step.evidenceId) ?? null
}

function renderPage({ manifest: manualManifest, currentPage, currentIndex, markdown, audit: manualAudit, screenshotAssets: assets, evidencePlan: plan, relativePrefix }) {
  const pages = manualManifest.pages ?? []
  const prev = pages[currentIndex - 1]
  const next = pages[currentIndex + 1]
  const nav = pages.map((page, index) => renderNavItem(page, index, currentIndex, relativePrefix)).join("")
  const body = renderMarkdown(markdown, { assets, plan, audit: manualAudit, relativePrefix })
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(currentPage.title)} - ${escapeHtml(manualManifest.title)}</title>
  <link rel="stylesheet" href="${relativePrefix}styles.css" />
</head>
<body>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-name">${escapeHtml(manualManifest.brand?.name ?? manualManifest.title)}</div>
      <div class="brand-subtitle">操作手册</div>
    </div>
    <nav>${nav}</nav>
  </aside>
  <main class="page">
    <header class="page-header">
      <div class="eyebrow">${escapeHtml(manualManifest.brand?.company ?? "")}</div>
      <h1>${escapeHtml(currentPage.title)}</h1>
      <div class="page-meta">操作手册 · 生成时间 ${escapeHtml(new Date().toLocaleString("zh-CN", { hour12: false }))}</div>
    </header>
    <article class="content">${body}</article>
    <nav class="pager">
      ${prev ? `<a href="${pageHref(prev, currentIndex - 1, relativePrefix)}">上一页：${escapeHtml(prev.title)}</a>` : "<span></span>"}
      ${next ? `<a href="${pageHref(next, currentIndex + 1, relativePrefix)}">下一页：${escapeHtml(next.title)}</a>` : "<span></span>"}
    </nav>
  </main>
</body>
</html>
`
}

function renderNavItem(page, index, currentIndex, relativePrefix) {
  const href = pageHref(page, index, relativePrefix)
  return `<a class="${index === currentIndex ? "active" : ""}" href="${href}">${String(index + 1).padStart(2, "0")} ${escapeHtml(page.title)}</a>`
}

function pageHref(page, index, relativePrefix) {
  return index === 0 ? `${relativePrefix}index.html` : `${relativePrefix}pages/${escapeAttribute(page.pageId)}.html`
}

function renderMarkdown(source, context) {
  const html = []
  let listOpen = false
  let codeOpen = false
  for (const line of source.split(/\r?\n/)) {
    if (line.startsWith("```")) {
      if (codeOpen) {
        html.push("</code></pre>")
        codeOpen = false
      } else {
        if (listOpen) {
          html.push("</ul>")
          listOpen = false
        }
        html.push("<pre><code>")
        codeOpen = true
      }
      continue
    }
    if (codeOpen) {
      html.push(`${escapeHtml(line)}\n`)
      continue
    }
    const evidence = /^{{evidence:([^}]+)}}$/.exec(line.trim())
    if (evidence) {
      if (listOpen) {
        html.push("</ul>")
        listOpen = false
      }
      html.push(renderEvidence(evidence[1].trim(), context))
      continue
    }
    if (line.trim() === "{{evidence-index}}") {
      if (listOpen) {
        html.push("</ul>")
        listOpen = false
      }
      html.push(renderEvidenceIndex(context.audit))
      continue
    }
    if (/^\s*$/.test(line)) {
      if (listOpen) {
        html.push("</ul>")
        listOpen = false
      }
      continue
    }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line)
    if (heading) {
      if (listOpen) {
        html.push("</ul>")
        listOpen = false
      }
      const level = Math.min(heading[1].length + 1, 4)
      html.push(`<h${level}>${escapeHtml(heading[2])}</h${level}>`)
      continue
    }
    const ordered = /^\s*\d+\.\s+(.+)$/.exec(line)
    const bullet = /^\s*[-*]\s+(.+)$/.exec(line)
    if (ordered || bullet) {
      if (!listOpen) {
        html.push("<ul>")
        listOpen = true
      }
      html.push(`<li>${inlineMarkdown((ordered ?? bullet)[1])}</li>`)
      continue
    }
    if (listOpen) {
      html.push("</ul>")
      listOpen = false
    }
    html.push(`<p>${inlineMarkdown(line)}</p>`)
  }
  if (listOpen) html.push("</ul>")
  if (codeOpen) html.push("</code></pre>")
  return html.join("\n")
}

function renderEvidence(evidenceId, { assets, plan, relativePrefix }) {
  const item = plan.byId.get(evidenceId)
  const image = assets.get(evidenceId)
  const meta = item
    ? `<div class="evidence-meta"><span>${escapeHtml(evidenceId)}</span><span>${escapeHtml(item.route ?? "")}</span><span>${escapeHtml(item.section ?? "")}</span></div>`
    : `<div class="evidence-meta"><span>${escapeHtml(evidenceId)}</span></div>`
  if (image) {
    return `<figure class="evidence">${meta}<img src="${relativePrefix}${escapeAttribute(image)}" alt="${escapeAttribute(item?.title ?? evidenceId)}" /><figcaption>${escapeHtml(item?.title ?? evidenceId)}</figcaption></figure>`
  }
  return `<figure class="evidence missing">${meta}<div class="missing-box">截图待补充：${escapeHtml(item?.title ?? evidenceId)}</div><figcaption>${escapeHtml(item?.focus ?? "按截图脚本补拍后重新生成手册。")}</figcaption></figure>`
}

function renderEvidenceIndex(audit) {
  const rows = audit.rows
    .map(
      (row) => `<tr>
  <td>${escapeHtml(row.evidenceId)}</td>
  <td>${escapeHtml(row.section)}</td>
  <td>${escapeHtml(row.title)}</td>
  <td><code>${escapeHtml(row.route)}</code></td>
</tr>`,
    )
    .join("")
  return `<table class="evidence-index"><thead><tr><th>截图ID</th><th>功能章节</th><th>页面标题</th><th>页面路由</th></tr></thead><tbody>${rows}</tbody></table>`
}

function inlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/「([^」]+)」/g, "「<strong>$1</strong>」")
}

function slugify(value) {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[^\p{Letter}\p{Number}]+/gu, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase()
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("'", "&#39;")
}

function parseArgs(rawArgs) {
  const parsed = {}
  for (let index = 0; index < rawArgs.length; index += 1) {
    const arg = rawArgs[index]
    if (!arg.startsWith("--")) continue
    const key = arg.slice(2)
    const next = rawArgs[index + 1]
    if (!next || next.startsWith("--")) {
      parsed[key] = "1"
    } else {
      parsed[key] = next
      index += 1
    }
  }
  return parsed
}
