import { ReactQueryDevtools } from "@tanstack/react-query-devtools"

export default function LayoutAddition() {
  if (!import.meta.env.DEV) {
    return null
  }

  return <ReactQueryDevtools buttonPosition="bottom-right" />
}
