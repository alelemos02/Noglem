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

/* ---------- Variant styles (JulIA Design System) ---------- */

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-accent text-white border-accent/20",
  success: "bg-success-muted text-success-text border-success/20",
  warning: "bg-warning-muted text-warning-text border-warning/20",
  error: "bg-error-muted text-error-text border-error/20",
  info: "bg-info-muted text-info-text border-info/20",
  secondary: "bg-secondary text-secondary-foreground border-border",
  destructive: "bg-error-muted text-error-text border-error/20",
  outline: "border-border text-foreground bg-transparent",
  ghost: "bg-transparent text-muted-foreground border-transparent",
  link: "text-accent-text underline-offset-4 border-transparent",
}

const dotColors: Record<BadgeVariant, string> = {
  default: "bg-white",
  success: "bg-success",
  warning: "bg-warning",
  error: "bg-error",
  info: "bg-info",
  secondary: "bg-text-tertiary",
  destructive: "bg-error",
  outline: "bg-text-tertiary",
  ghost: "bg-text-tertiary",
  link: "bg-accent-text",
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
        "rounded-md border px-2 py-0.5",
        "text-xs font-medium font-heading tracking-wide",
        "w-fit whitespace-nowrap shrink-0",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className={cn("h-1.5 w-1.5 rounded-full", dotColors[variant])}
          aria-hidden="true"
        />
      )}
      {children}
    </Comp>
  )
}

export { Badge }
