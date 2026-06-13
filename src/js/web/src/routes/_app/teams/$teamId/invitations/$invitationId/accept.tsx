import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate, useParams } from "@tanstack/react-router"
import { CheckCircle, Users, XCircle } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import { AdminPanel } from "@/components/admin-ui"
import { Icons } from "@/components/icons"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { PageContainer } from "@/components/ui/page-layout"
import { acceptTeamInvitation, getTeam, rejectTeamInvitation } from "@/lib/generated/api"

export const Route = createFileRoute("/_app/teams/$teamId/invitations/$invitationId/accept")({
  component: AcceptInvitationPage,
})

function AcceptInvitationPage() {
  const navigate = useNavigate()
  const { teamId, invitationId } = useParams({
    from: "/_app/teams/$teamId/invitations/$invitationId/accept",
  })
  const [status, setStatus] = useState<"pending" | "accepting" | "declining" | "accepted" | "declined" | "error">("pending")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const { data: team, isLoading: isTeamLoading } = useQuery({
    queryKey: ["team", teamId],
    queryFn: async () => {
      const response = await getTeam({ path: { team_id: teamId } })
      return response.data
    },
  })

  const acceptMutation = useMutation({
    mutationFn: async () => {
      const response = await acceptTeamInvitation({
        path: { team_id: teamId, invitation_id: invitationId },
      })
      if (response.error) {
        throw new Error(response.error.detail || "接受邀请失败")
      }
      return response.data
    },
    onMutate: () => {
      setStatus("accepting")
      setErrorMessage(null)
    },
    onSuccess: () => {
      setStatus("accepted")
      toast.success("已加入团队")
      setTimeout(() => {
        navigate({ to: "/teams/$teamId", params: { teamId } })
      }, 1500)
    },
    onError: (error: Error) => {
      setStatus("error")
      setErrorMessage(error.message)
      toast.error("接受邀请失败", {
        description: error.message,
      })
    },
  })

  const declineMutation = useMutation({
    mutationFn: async () => {
      const response = await rejectTeamInvitation({
        path: { team_id: teamId, invitation_id: invitationId },
      })
      if (response.error) {
        throw new Error(response.error.detail || "拒绝邀请失败")
      }
      return response.data
    },
    onMutate: () => {
      setStatus("declining")
      setErrorMessage(null)
    },
    onSuccess: () => {
      setStatus("declined")
      toast.success("已拒绝邀请")
      setTimeout(() => {
        navigate({ to: "/teams" })
      }, 1500)
    },
    onError: (error: Error) => {
      setStatus("error")
      setErrorMessage(error.message)
      toast.error("拒绝邀请失败", {
        description: error.message,
      })
    },
  })

  const isPending = status === "pending"
  const isProcessing = status === "accepting" || status === "declining"
  const isComplete = status === "accepted" || status === "declined"

  return (
    <PageContainer className="flex flex-1 items-center justify-center">
      <AdminPanel title={status === "accepted" ? "已加入团队" : status === "declined" ? "已拒绝邀请" : "团队邀请"} className="w-full max-w-md">
        <div className="space-y-5 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-md border border-border/70 bg-muted/40">
            {status === "accepted" ? (
              <CheckCircle className="h-6 w-6 text-success" />
            ) : status === "declined" ? (
              <XCircle className="h-6 w-6 text-muted-foreground" />
            ) : (
              <Users className="h-6 w-6 text-primary" />
            )}
          </div>
          <div className="text-muted-foreground text-sm">
            {status === "accepted" ? (
              "正在跳转到团队详情。"
            ) : status === "declined" ? (
              "你不会加入该团队。"
            ) : isTeamLoading ? (
              "正在加载邀请信息。"
            ) : team ? (
              <>你被邀请加入 {team.name}</>
            ) : (
              "你收到了一条团队邀请。"
            )}
          </div>

          {status === "error" && errorMessage && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          )}

          {isProcessing && (
            <div className="flex flex-col items-center space-y-3 py-4">
              <Icons.spinner className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">{status === "accepting" ? "正在加入团队" : "正在拒绝邀请"}</p>
            </div>
          )}

          {isComplete && (
            <div className="flex flex-col items-center space-y-3 py-4">
              <Icons.spinner className="h-6 w-6 animate-spin text-muted-foreground" />
              <p className="text-sm text-muted-foreground">正在跳转</p>
            </div>
          )}

          {(isPending || status === "error") && (
            <div className="flex flex-col gap-2">
              <Button className="w-full" onClick={() => acceptMutation.mutate()} disabled={isProcessing}>
                接受邀请
              </Button>
              <Button variant="outline" className="w-full" onClick={() => declineMutation.mutate()} disabled={isProcessing}>
                拒绝
              </Button>
            </div>
          )}
        </div>
      </AdminPanel>
    </PageContainer>
  )
}
