import type { HumanVerificationSubmission } from "@/lib/auth"

export function resolveHumanVerificationSubmission(
  form: HTMLFormElement | null,
  current: HumanVerificationSubmission | null,
  provider: string,
): HumanVerificationSubmission | null {
  const formPayload = form ? formDataValue(form, "altcha") : null
  if (formPayload) {
    return {
      provider,
      payload: formPayload,
    }
  }

  return current
}

function formDataValue(form: HTMLFormElement, key: string): string | null {
  const value = new FormData(form).get(key)
  return typeof value === "string" && value.trim().length > 0 ? value : null
}
