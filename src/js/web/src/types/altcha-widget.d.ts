import type * as React from "react"

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "altcha-widget": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        challenge?: string
        challengeurl?: string
        hidefooter?: boolean
        hidelogo?: boolean
        floating?: boolean
        display?: string
        type?: string
      }
    }
  }
}
