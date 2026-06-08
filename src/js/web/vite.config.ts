import path from "node:path"
import fs from "node:fs/promises"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import react from "@vitejs/plugin-react"
import litestar from "litestar-vite-plugin"
import { defineConfig, type Plugin } from "vite"

function ensureTrailingSlash(value: string) {
  return value.endsWith("/") ? value : `${value}/`
}

function createManualChunks(id: string) {
  if (id.includes("node_modules/cesium/")) return "cesium-engine"
  if (id.includes("node_modules/maplibre-gl/")) return "maplibre-engine"
  if (id.includes("node_modules/echarts/") || id.includes("node_modules/echarts-for-react/")) return "charts"
  if (id.includes("node_modules/@tanstack/")) return "tanstack-vendor"
  if (id.includes("node_modules/@radix-ui/")) return "radix-vendor"
  if (id.includes("node_modules/framer-motion/")) return "motion-vendor"
  if (id.includes("node_modules/lucide-react/")) return "icons"
}

const baseUrl = process.env.ASSET_URL ?? (process.env.NODE_ENV === "development" ? "/" : "/static/web/")
const normalizedBaseUrl = ensureTrailingSlash(baseUrl)
const cesiumBaseUrl = `${normalizedBaseUrl}cesium/`
const cesiumBuildRoot = path.resolve(__dirname, "./node_modules/cesium/Build/Cesium")
function createCesiumDevServerPlugin(): Plugin {
  return {
    name: "bigscreen-cesium-dev-server",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const requestUrl = req.url?.split("?")[0]
        if (!requestUrl?.startsWith("/cesium/")) {
          return next()
        }

        const relativePath = requestUrl.slice("/cesium/".length)
        const filePath = path.resolve(cesiumBuildRoot, relativePath)
        if (!filePath.startsWith(cesiumBuildRoot)) {
          res.statusCode = 403
          res.end("Forbidden")
          return
        }

        try {
          const stat = await fs.stat(filePath)
          if (!stat.isFile()) {
            return next()
          }

          const ext = path.extname(filePath)
          const contentTypeMap: Record<string, string> = {
            ".js": "application/javascript",
            ".mjs": "application/javascript",
            ".json": "application/json",
            ".wasm": "application/wasm",
            ".css": "text/css",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".xml": "application/xml",
            ".ktx2": "application/octet-stream",
            ".bin": "application/octet-stream",
          }

          const buffer = await fs.readFile(filePath)
          res.statusCode = 200
          res.setHeader("Content-Type", contentTypeMap[ext] ?? "application/octet-stream")
          res.end(buffer)
        } catch {
          next()
        }
      })
    },
  }
}

export default defineConfig({
  clearScreen: false,
  base: normalizedBaseUrl,
  define: {
    CESIUM_BASE_URL: JSON.stringify(cesiumBaseUrl),
  },
  publicDir: "public",
  server: {
    allowedHosts: ["host.docker.internal"],
    cors: true,
    port: Number(process.env.VITE_PORT ?? 18101),
    proxy: {
      "/api": {
        changeOrigin: true,
        target: process.env.APP_URL ?? "http://localhost:18100",
      },
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../../py/app/server/static/web"),
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: createManualChunks,
      },
    },
  },
  plugins: [
    tanstackRouter({ target: "react", autoCodeSplitting: true }),
    tailwindcss(),
    react(),
    createCesiumDevServerPlugin(),
    litestar({
      input: ["src/main.tsx", "src/styles.css"],
      bundleDir: path.resolve(__dirname, "../../py/app/server/static/web"),
      hotFile: path.resolve(__dirname, "../../py/app/server/static/web/hot"),
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
