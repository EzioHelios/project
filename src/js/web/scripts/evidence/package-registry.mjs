import path from "node:path"

const brandProfiles = {
  woheng: {
    displayName: "沃衡汽车能碳管理平台",
    shortName: "沃衡汽车",
    logoFullUrl: "/brand/logo-woheng.svg",
    forbiddenBrands: "中汽信科,奇瑞,Chery,安方,祥泰,华东绿色仓储",
  },
  chery: {
    displayName: "奇瑞绿能综合能碳管理平台",
    shortName: "奇瑞绿能",
    logoFullUrl: "",
    forbiddenBrands: "中汽信科,安方,祥泰,华东绿色仓储",
  },
  generic: {
    displayName: "能碳管理平台",
    shortName: "能碳",
    logoFullUrl: "",
    forbiddenBrands: "中汽信科,奇瑞,Chery,安方,祥泰,华东绿色仓储",
  },
}

export const evidencePackages = {
  "woheng-showcase": {
    key: "woheng-showcase",
    description: "沃衡汽车统一演示包截图取证，覆盖泰州生产基地与湖州生产基地。",
    captureScript: "capture-woheng-showcase-evidence.mjs",
    defaultNamespace: "woheng",
    defaultProfile: "full",
    defaultBrand: "woheng",
    defaultPort: "18111",
    outputDir: ({ repositoryRoot, packageKey, namespace, profile }) =>
      path.join(repositoryRoot, "outputs", `${packageKey}-${namespace}-${profile}-evidence`),
  },
  "chery-org-carbon-tender": {
    key: "chery-org-carbon-tender",
    description: "奇瑞技术标组织碳专项截图取证，保留技术评分功能编号映射。",
    captureScript: "capture-org-carbon-tender-evidence.mjs",
    defaultNamespace: "chery",
    defaultProfile: "tender",
    defaultBrand: "chery",
    defaultPort: "18111",
    outputDir: ({ repositoryRoot }) => path.join(repositoryRoot, "outputs", "chery-bid-feature-decomposition-20260823", "screenshots"),
  },
}

export function listEvidencePackages() {
  return Object.values(evidencePackages)
}

export function resolveEvidencePackage(packageKey) {
  const config = evidencePackages[packageKey]
  if (!config) {
    const known = Object.keys(evidencePackages).join(", ")
    throw new Error(`Unknown evidence package: ${packageKey}. Known packages: ${known}`)
  }
  return config
}

export function resolveBrandProfile(brandKey) {
  return brandProfiles[brandKey] ?? brandProfiles.generic
}
