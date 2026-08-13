import { readdirSync, readFileSync, statSync } from "node:fs"
import { relative, resolve } from "node:path"

const root = resolve(import.meta.dirname, "..")
const scanRoots = ["src/components", "src/routes/_app"].map((path) => resolve(root, path))
const standaloneScanFiles = ["src/styles.css", "src/components/microgrid/scada/scada.css"].map((path) =>
  resolve(root, path),
)
const jsonMode = process.argv.includes("--json")

const isAdminSurfaceFile = (file) =>
  file === "src/styles.css" ||
  file.startsWith("src/routes/_app/") ||
  ["src/components/admin-ui/", "src/components/carbon/", "src/components/microgrid/"].some((prefix) =>
    file.startsWith(prefix),
  )

const checks = [
  {
    id: "legacy-admin-toolbar-api",
    label: "AdminTableToolbar still uses search/filters/children",
    test: (source) =>
      Array.from(source.matchAll(/<AdminTableToolbar\b[\s\S]*?(?:\/>|<\/AdminTableToolbar>)/g)).some((match) => {
        const block = match[0]
        const openingTag = block.slice(0, Math.max(block.indexOf(">"), 0))
        return /\b(search|filters)=/.test(openingTag)
      }),
  },
  {
    id: "legacy-page-header",
    label: "Authenticated page still renders PageHeader",
    test: (source) => /<PageHeader\b/.test(source),
  },
  {
    id: "naked-card",
    label: "Imports ui/card; verify it should not be AdminPanel/AdminDataTable",
    test: (source) => /from ["']@\/components\/ui\/card["']/.test(source) || /<Card\b/.test(source),
  },
  {
    id: "visible-description-prop",
    label: "Admin/Chart header may still render explanatory description/meta/eyebrow",
    test: (source) => /<(AdminPageHeader|AdminPanel|ChartPanel)\b[^>]*\b(description|eyebrow|meta)=/.test(source),
  },
  {
    id: "chart-local-hex",
    label: "Chart option may still define local hex colors",
    test: (source) => /(color|itemStyle|lineStyle|areaStyle|axisLine|splitLine)[\s\S]{0,180}#[0-9a-fA-F]{3,8}/.test(source),
  },
  {
    id: "tabs-without-scaffold",
    label: "Tabs page may need AdminPageScaffold order",
    test: (source) => /<Tabs\b/.test(source) && /<ContextBar\b/.test(source) && !/<AdminPageScaffold\b/.test(source),
  },
  {
    id: "local-filter-card",
    label: "Local filter PageSection/Card-like surface may need ContextBar/AdminPageScaffold",
    test: (source) => /<PageSection\b[^>]*className=["'][^"']*(rounded|border|bg-card)[^"']*["'][\s\S]{0,1200}<(Input|Select|Button)\b/.test(source),
  },
  {
    id: "raw-json-render",
    label: "TSX renders JSON.stringify; verify it is not product-facing raw object output",
    test: (source) => /<[^>]*>\s*\{?\s*JSON\.stringify\(/.test(source) || /\{JSON\.stringify\([^)]*\)\}/.test(source),
  },
  {
    id: "admin-surface-gradient",
    label: "Admin surface still uses a decorative CSS or Tailwind gradient",
    test: (source, file) =>
      isAdminSurfaceFile(file) &&
      /(?:linear|radial|conic)-gradient|\bbg-(?:gradient|linear|radial|conic)(?:-|\b)/.test(source),
  },
]

function collectFiles(dir, files = []) {
  for (const entry of readdirSync(dir)) {
    const fullPath = resolve(dir, entry)
    const stats = statSync(fullPath)
    if (stats.isDirectory()) {
      collectFiles(fullPath, files)
    } else if (/\.(tsx|ts)$/.test(entry)) {
      files.push(fullPath)
    }
  }
  return files
}

const report = Object.fromEntries(checks.map((check) => [check.id, { ...check, files: [] }]))

for (const file of [...scanRoots.flatMap((dir) => collectFiles(dir)), ...standaloneScanFiles]) {
  const source = readFileSync(file, "utf8")
  const repositoryPath = relative(root, file)
  for (const check of checks) {
    if (check.test(source, repositoryPath)) {
      report[check.id].files.push(repositoryPath)
    }
  }
}

const result = Object.values(report).map(({ id, label, files }) => ({
  id,
  label,
  count: files.length,
  files,
}))

if (jsonMode) {
  console.log(JSON.stringify(result, null, 2))
} else {
  console.log("# Admin visual audit\n")
  for (const item of result) {
    console.log(`## ${item.id} (${item.count})`)
    console.log(item.label)
    if (item.files.length === 0) {
      console.log("- none")
    } else {
      for (const file of item.files) {
        console.log(`- ${file}`)
      }
    }
    console.log("")
  }
}
