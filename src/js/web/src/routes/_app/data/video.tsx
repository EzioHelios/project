import { createFileRoute } from "@tanstack/react-router"
import { VideoPage } from "@/components/platform/data-admin-pages"

export const Route = createFileRoute("/_app/data/video")({
  component: VideoPage,
})
