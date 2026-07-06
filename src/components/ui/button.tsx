import * as React from "react"
import { Slot } from "radix-ui"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

/* ---------- Types ---------- */

type ButtonVariant =
  | "default" | "primary"
  | "secondary" | "outline"
  | "ghost"
  | "danger" | "destructive"
  | "link"

type ButtonSize =
  | "default" | "md"
  | "sm" | "lg"
  | "icon" | "icon-xs" | "icon-sm" | "icon-lg"

export interface ButtonProps extends React.ComponentProps<"button"> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  asChild?: boolean
}

/* ---------- Variant styles (JulIA Design System v3) ---------- */

const variantStyles: Record<ButtonVariant, string> = {
  default:
    "bg-accent text-accent-fg hover:bg-accent-hover active:bg-accent-active shadow-sm",
  primary:
    "bg-accent text-accent-fg hover:bg-accent-hover active:bg-accent-active shadow-sm",
  secondary:
    "bg-surface-2 border border-edge text-fg hover:bg-surface-3 hover:border-edge-strong active:bg-surface-3",
  outline:
    "bg-surface-2 border border-edge text-fg hover:bg-surface-3 hover:border-edge-strong active:bg-surface-3",
  ghost:
    "bg-transparent text-fg-muted hover:bg-surface-2 hover:text-fg active:bg-surface-3",
  danger:
    "bg-danger text-fg-inverse hover:brightness-110 active:brightness-90 shadow-sm",
  destructive:
    "bg-danger text-fg-inverse hover:brightness-110 active:brightness-90 shadow-sm",
  link: "text-accent underline-offset-4 hover:underline bg-transparent",
}

const sizeStyles: Record<ButtonSize, string> = {
  default: "h-9 px-4 text-sm gap-2",
  md: "h-9 px-4 text-sm gap-2",
  sm: "h-8 px-3 text-[13px] gap-1.5",
  lg: "h-10 px-5 text-sm gap-2.5",
  icon: "size-9",
  "icon-xs": "size-6 rounded-md [&_svg:not([class*='size-'])]:size-3",
  "icon-sm": "size-8",
  "icon-lg": "size-10",
}

/* ---------- Component ---------- */

function Button({
  variant = "default",
  size = "default",
  loading = false,
  disabled,
  className,
  children,
  asChild = false,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      disabled={disabled || loading}
      className={cn(
        // base
        "inline-flex items-center justify-center whitespace-nowrap font-sans font-medium",
        "rounded-md transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas",
        "disabled:opacity-50 disabled:pointer-events-none",
        "[&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 [&_svg]:shrink-0 shrink-0",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </Comp>
  )
}

export { Button }
