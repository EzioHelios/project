import fs from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(__dirname, "..")
const cesiumBuildRoot = path.resolve(projectRoot, "./node_modules/cesium/Build/Cesium")
const cesiumOutputRoot = path.resolve(projectRoot, "../../py/app/server/static/web/cesium")
const directories = ["Workers", "ThirdParty", "Assets", "Widgets"]

await fs.rm(cesiumOutputRoot, { recursive: true, force: true })
await fs.mkdir(cesiumOutputRoot, { recursive: true })

for (const directory of directories) {
  await fs.cp(path.join(cesiumBuildRoot, directory), path.join(cesiumOutputRoot, directory), {
    recursive: true,
  })
}
