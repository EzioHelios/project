import { describe, expect, it } from "vitest"

import { resolveHumanVerificationSubmission } from "@/lib/human-verification"

describe("resolveHumanVerificationSubmission", () => {
  it("prefers the hidden altcha payload from the form", () => {
    document.body.innerHTML = `
      <form>
        <input type="hidden" name="altcha" value="payload-from-widget" />
      </form>
    `

    const form = document.querySelector("form") as HTMLFormElement | null
    expect(resolveHumanVerificationSubmission(form, null, "altcha-sentinel")).toEqual({
      provider: "altcha-sentinel",
      payload: "payload-from-widget",
    })
  })

  it("falls back to the in-memory verification state", () => {
    expect(
      resolveHumanVerificationSubmission(null, { provider: "altcha-sentinel", payload: "payload-from-state" }, "altcha-sentinel"),
    ).toEqual({
      provider: "altcha-sentinel",
      payload: "payload-from-state",
    })
  })
})
