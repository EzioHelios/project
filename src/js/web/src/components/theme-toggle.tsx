import { Check, MonitorCog, Moon, Sun } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { useTheme } from "@/lib/theme-context"

export function ThemeToggle() {
  const { preference, resolvedTheme, setPreference } = useTheme()
  const options = [
    { value: "system" as const, label: "跟随系统", icon: MonitorCog },
    { value: "light" as const, label: "浅色模式", icon: Sun },
    { value: "dark" as const, label: "深色模式", icon: Moon },
  ]

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-sidebar-foreground/72 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          aria-label={`外观设置：${preference === "system" ? "跟随系统" : resolvedTheme === "dark" ? "深色" : "浅色"}`}
        >
          {preference === "system" ? <MonitorCog className="size-4" /> : resolvedTheme === "dark" ? <Moon className="size-4" /> : <Sun className="size-4" />}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-40">
        <DropdownMenuLabel>界面外观</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {options.map((option) => (
          <DropdownMenuItem key={option.value} onClick={() => setPreference(option.value)} className="gap-2">
            <option.icon className="size-4" />
            <span>{option.label}</span>
            {preference === option.value ? <Check className="ml-auto size-4 text-primary" /> : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
