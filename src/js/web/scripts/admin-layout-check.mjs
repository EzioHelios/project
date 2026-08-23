import { existsSync, readFileSync, readdirSync, statSync } from "node:fs"
import { dirname, relative, resolve } from "node:path"

const webRoot = resolve(import.meta.dirname, "..")
const appRoutesRoot = resolve(webRoot, "src/routes/_app")

function collectRouteFiles(directory, files = []) {
  for (const entry of readdirSync(directory)) {
    const file = resolve(directory, entry)
    const stats = statSync(file)
    if (stats.isDirectory()) {
      collectRouteFiles(file, files)
    } else if (entry.endsWith(".tsx")) {
      files.push(file)
    }
  }
  return files
}

function routeAncestors(file) {
  const ancestors = [file]
  let directory = dirname(file)

  while (directory.startsWith(appRoutesRoot)) {
    const layoutFile = `${directory}.tsx`
    if (existsSync(layoutFile)) ancestors.push(layoutFile)
    if (directory === appRoutesRoot) break
    directory = dirname(directory)
  }

  const appLayoutFile = `${appRoutesRoot}.tsx`
  if (existsSync(appLayoutFile)) ancestors.push(appLayoutFile)
  return [...new Set(ancestors)]
}

const scaffoldRoutes = collectRouteFiles(appRoutesRoot).filter((file) => /<AdminPageScaffold\b/.test(readFileSync(file, "utf8")))
const violations = scaffoldRoutes.filter((file) =>
  routeAncestors(file).every((candidate) => !/<PageContainer\b/.test(readFileSync(candidate, "utf8"))),
)

if (violations.length > 0) {
  console.error("Admin layout check failed: AdminPageScaffold requires a PageContainer in the current route or an ancestor route.")
  for (const file of violations) console.error(`- ${relative(webRoot, file)}`)
  process.exit(1)
}

console.log(`Admin layout check passed (${scaffoldRoutes.length} scaffold routes).`)
