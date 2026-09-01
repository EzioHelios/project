const DEFAULT_LANGUAGE = "zh"
const DEFAULT_LOCALE = "zh-CN"

export const evidenceLanguage = normalizeLanguage(
  process.env.EVIDENCE_UI_LANGUAGE ?? process.env.EVIDENCE_LANGUAGE ?? process.env.PLAYWRIGHT_UI_LANGUAGE ?? DEFAULT_LANGUAGE,
)

export const evidenceLocale = process.env.EVIDENCE_UI_LOCALE ?? process.env.EVIDENCE_LOCALE ?? localeForLanguage(evidenceLanguage)

export function withEvidenceLanguage(options = {}) {
  return {
    ...options,
    locale: options.locale ?? evidenceLocale,
    timezoneId: options.timezoneId ?? "Asia/Shanghai",
    extraHTTPHeaders: {
      "Accept-Language": `${evidenceLocale},${evidenceLanguage};q=0.9,en;q=0.5`,
      ...(options.extraHTTPHeaders ?? {}),
    },
  }
}

export async function installEvidenceLanguage(context) {
  await context.addInitScript(
    ({ language, locale }) => {
      window.localStorage.setItem("i18nextLng", language)
      window.localStorage.setItem("nexlca.ui.language", language)
      const navigatorTarget = Object.getPrototypeOf(navigator) ?? navigator
      Object.defineProperty(navigatorTarget, "language", {
        configurable: true,
        get: () => locale,
      })
      Object.defineProperty(navigatorTarget, "languages", {
        configurable: true,
        get: () => [locale, language, "en-US", "en"],
      })
    },
    { language: evidenceLanguage, locale: evidenceLocale },
  )
}

export async function assertEvidenceLanguage(page) {
  await page.waitForFunction(
    ({ language, locale }) => {
      const stored = window.localStorage.getItem("i18nextLng")
      const htmlLang = document.documentElement.lang
      const expectedBase = language.split("-")[0].toLowerCase()
      return (
        stored?.toLowerCase().startsWith(expectedBase) &&
        htmlLang?.toLowerCase().startsWith(expectedBase) &&
        navigator.language?.toLowerCase().startsWith(locale.split("-")[0].toLowerCase())
      )
    },
    { language: evidenceLanguage, locale: evidenceLocale },
    { timeout: 30_000 },
  )
}

export async function languageDiagnostics(page) {
  return page.evaluate(() => ({
    htmlLang: document.documentElement.lang,
    i18nextLng: window.localStorage.getItem("i18nextLng"),
    navigatorLanguage: navigator.language,
    navigatorLanguages: navigator.languages,
  }))
}

function normalizeLanguage(value) {
  const normalized = String(value || DEFAULT_LANGUAGE).trim().replace("_", "-").toLowerCase()
  return normalized.split("-")[0] || DEFAULT_LANGUAGE
}

function localeForLanguage(language) {
  if (language === "en") return "en-US"
  if (language === "es") return "es-ES"
  if (language === "ja") return "ja-JP"
  return DEFAULT_LOCALE
}
