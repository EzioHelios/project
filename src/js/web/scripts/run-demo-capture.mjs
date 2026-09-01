import { spawn } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { listEvidencePackages, resolveBrandProfile, resolveEvidencePackage } from "./evidence/package-registry.mjs"

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const webRoot = path.resolve(scriptDir, "..")
const repositoryRoot = path.resolve(webRoot, "../../..")
const args = parseArgs(process.argv.slice(2))

if (args.list) {
  for (const item of listEvidencePackages()) {
    process.stdout.write(`${item.key}\t${item.description}\n`)
  }
  process.exit(0)
}

const packageKey = args.package ?? "woheng-showcase"
const packageConfig = resolveEvidencePackage(packageKey)
const namespace = args.namespace ?? packageConfig.defaultNamespace
const profile = args.profile ?? packageConfig.defaultProfile
const brand = args.brand ?? packageConfig.defaultBrand
const brandProfile = resolveBrandProfile(brand)
const port = process.env.EVIDENCE_FRONTEND_PORT ?? args.port ?? packageConfig.defaultPort
const baseURL = process.env.E2E_BASE_URL ?? `http://127.0.0.1:${port}`
const brandName = process.env.EVIDENCE_BRAND_NAME ?? brandProfile.displayName
const brandShortName = process.env.EVIDENCE_BRAND_SHORT_NAME ?? brandProfile.shortName
const brandLogoFullUrl = process.env.VITE_DEMO_LOGO_FULL_URL ?? brandProfile.logoFullUrl
const outputDir =
  process.env.EVIDENCE_OUTPUT_DIR ??
  packageConfig.outputDir({
    repositoryRoot,
    packageKey,
    namespace,
    profile,
    brand,
  })
const captureScript = packageConfig.captureScript

const env = {
  ...process.env,
  E2E_BASE_URL: baseURL,
  EVIDENCE_BRAND_NAME: brandName,
  EVIDENCE_BRAND_SHORT_NAME: brandShortName,
  EVIDENCE_FORBIDDEN_BRANDS: process.env.EVIDENCE_FORBIDDEN_BRANDS ?? brandProfile.forbiddenBrands,
  EVIDENCE_OUTPUT_DIR: outputDir,
  EVIDENCE_PACKAGE_KEY: packageKey,
  EVIDENCE_NAMESPACE: namespace,
  EVIDENCE_PROFILE: profile,
  EVIDENCE_ONLY: args.only && args.only !== "changed" ? args.only : (process.env.EVIDENCE_ONLY ?? ""),
  EVIDENCE_PLAN_ONLY: args["plan-only"] ? "1" : (process.env.EVIDENCE_PLAN_ONLY ?? ""),
  VITE_PORT: port,
  VITE_DEMO_BRAND_NAME: brandName,
  VITE_DEMO_BRAND_SHORT_NAME: brandShortName,
  VITE_DEMO_LOGO_FULL_URL: brandLogoFullUrl,
}

let server = null
let serverOutput = ""

try {
  if (!args["no-server"]) {
    server = startFrontendServer()
    await waitForFrontend(baseURL)
  }
  const exitCode = await runCapture(env)
  process.exitCode = exitCode
} finally {
  server?.kill("SIGTERM")
}

function startFrontendServer() {
  const child = spawn("bun", ["run", "dev", "--", "--host", "127.0.0.1", "--strictPort"], {
    cwd: webRoot,
    env,
    stdio: ["ignore", "pipe", "pipe"],
  })
  child.stdout.on("data", (chunk) => {
    serverOutput += chunk.toString()
    process.stdout.write(chunk)
  })
  child.stderr.on("data", (chunk) => {
    serverOutput += chunk.toString()
    process.stderr.write(chunk)
  })
  return child
}

async function waitForFrontend(url) {
  const deadline = Date.now() + 60_000
  while (Date.now() < deadline) {
    if (server && server.exitCode !== null) {
      throw new Error(`前端专用服务启动失败，退出码 ${server.exitCode}\n${serverOutput}`)
    }
    try {
      const response = await fetch(`${url}/login`)
      if (response.ok) return
    } catch {
      // Retry until Vite finishes cold start.
    }
    await new Promise((resolve) => setTimeout(resolve, 750))
  }
  throw new Error(`前端专用服务未在 60 秒内就绪：${url}`)
}

function runCapture(captureEnv) {
  return new Promise((resolve, reject) => {
    const child = spawn("node", [`./scripts/${captureScript}`], {
      cwd: webRoot,
      env: captureEnv,
      stdio: "inherit",
    })
    child.on("error", reject)
    child.on("exit", (code) => resolve(code ?? 1))
  })
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
