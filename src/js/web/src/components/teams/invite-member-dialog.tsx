import { zodResolver } from "@hookform/resolvers/zod"
import { useQueryClient } from "@tanstack/react-query"
import { ShieldCheck, User, UserPlus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import * as z from "zod"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { createTeamInvitation, type TeamRoles } from "@/lib/generated/api"

const inviteSchema = z.object({
  email: z.string().email("请输入有效邮箱地址"),
  role: z.enum(["MEMBER", "ADMIN"] as const),
})

type InviteFormData = z.infer<typeof inviteSchema>

interface InviteMemberDialogProps {
  teamId: string
}

export function InviteMemberDialog({ teamId }: InviteMemberDialogProps) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()

  const form = useForm<InviteFormData>({
    resolver: zodResolver(inviteSchema),
    defaultValues: {
      email: "",
      role: "MEMBER",
    },
  })

  const onSubmit = async (data: InviteFormData) => {
    try {
      await createTeamInvitation({
        path: { team_id: teamId },
        body: {
          email: data.email,
          role: data.role as TeamRoles,
        },
      })
      await queryClient.invalidateQueries({
        queryKey: ["team", teamId],
      })
      await queryClient.invalidateQueries({
        queryKey: ["teamInvitations", teamId],
      })
      setOpen(false)
      form.reset()
    } catch (error) {
      console.error("Failed to send invitation:", error)
      form.setError("root", {
        message: "邀请发送失败，该用户可能已在邀请列表中。",
      })
    }
  }

  const roleOptions = [
    {
      value: "MEMBER" as const,
      label: "成员",
      description: "查看并参与团队协作",
      icon: User,
    },
    {
      value: "ADMIN" as const,
      label: "管理员",
      description: "邀请成员并维护团队设置",
      icon: ShieldCheck,
    },
  ]

  const selectedRole = roleOptions.find((opt) => opt.value === form.watch("role"))

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <UserPlus className="mr-2 h-4 w-4" />
          邀请成员
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>邀请团队成员</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>邮箱地址</FormLabel>
                  <FormControl>
                    <Input {...field} type="email" placeholder="colleague@company.com" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="role"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>角色</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="选择角色">
                          {selectedRole && (
                            <span className="flex items-center gap-2">
                              <selectedRole.icon className="h-4 w-4 text-muted-foreground" />
                              {selectedRole.label}
                            </span>
                          )}
                        </SelectValue>
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {roleOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value} className="py-3">
                          <div className="flex items-start gap-3">
                            <option.icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                            <div className="flex flex-col">
                              <span className="font-medium">{option.label}</span>
                              <span className="text-xs text-muted-foreground">{option.description}</span>
                            </div>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            {form.formState.errors.root && (
              <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3">
                <p className="text-destructive text-sm">{form.formState.errors.root.message}</p>
              </div>
            )}
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                取消
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? "发送中..." : "发送邀请"}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
