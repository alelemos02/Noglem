import * as React from "react"
import { Slot } from "radix-ui"
import { cn } from "@/lib/utils"

/* ---------- Types ---------- */

type BadgeVariant =
  | "default" | "success" | "warning" | "error" | "info"
  | "secondary" | "destructive" | "outline" | "ghost" | "link"

export interface BadgeProps extends React.ComponentProps<"span"> {
  variant?: BadgeVariant
  dot?: boolean
  asChild?: boolean
}

/* ---------- Variant styles (JulIA Design System v3) ----------
   Chip técnico: mono, uppercase, tracking — assinatura da identidade. */

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-accent-subtle text-accent border-accent/35",
  success: "bg-success-subtle text-success border-success/35",
  warning: "bg-warning-subtle text-warning border-warning/35",
  error: "bg-danger-subtle text-danger border-danger/35",
  info: "bg-info-subtle text-info border-info/35",
  secondary: "bg-surface-2 text-fg-muted border-edge-strong",
  destructive: "bg-danger-subtle text-danger border-danger/35",
  outline: "border-edge-strong text-fg-muted bg-transparent",
  ghost: "bg-transparent text-fg-subtle border-transparent",
  link: "text-accent underline-offset-4 border-transparent",
}

const dotColors: Record<BadgeVariant, string> = {
  default: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  error: "bg-danger",
  info: "bg-info",
  secondary: "bg-fg-subtle",
  destructive: "bg-danger",
  outline: "bg-fg-subtle",
  ghost: "bg-fg-subtle",
  link: "bg-accent",
}

/* ---------- Component ---------- */

function Badge({
  variant = "default",
  dot = false,
  className,
  children,
  asChild = false,
  ...props
}: BadgeProps) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      data-variant={variant}
      className={cn(
        "inline-flex items-center gap-1.5",
        "rounded-sm border px-2 py-0.5",
        "font-mono text-[10px] font-medium uppercase tracking-[0.09em]",
        "w-fit whitespace-nowrap shrink-0",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className={cn("h-[5px] w-[5px] rounded-full", dotColors[variant])}
          aria-hidden="true"
        />
      )}
      {children}
    </Comp>
  )
}

export { Badge }
