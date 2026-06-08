import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(__dirname, "..")
const sourceIndexPath = path.join(projectRoot, "index.html")
const manifestPath = path.resolve(projectRoot, "../../py/app/server/static/web/manifest.json")
const outputIndexPath = path.resolve(projectRoot, "../../py/app/server/static/web/index.html")
const assetBase = "/static/web/"

function toAssetUrl(file) {
  return `${assetBase}${file}`.replace(/\/{2,}/g, "/").replace(":/", "://")
}

const sourceHtml = await fs.readFile(sourceIndexPath, "utf8")
const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"))
const entry = manifest["src/main.tsx"]

if (!entry?.file) {
  throw new Error("Vite manifest entry 'src/main.tsx' not found")
}

const cssLinks = (entry.css ?? [])
  .map((cssFile) => `    <link rel="stylesheet" href="${toAssetUrl(cssFile)}" />`)
  .join("\n")

const builtHtml = sourceHtml
  .replace(
    /<script type="module" src="\/src\/main\.tsx"><\/script>/,
    `${cssLinks ? `${cssLinks}\n` : ""}    <script type="module" src="${toAssetUrl(entry.file)}"></script>`,
  )
  .replace(/href="\/(favicon[^"]*|manifest\.json|robots\.txt)/g, `href="${assetBase}$1`)

await fs.writeFile(outputIndexPath, builtHtml)
