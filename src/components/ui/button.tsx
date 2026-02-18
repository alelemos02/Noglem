import * as React from "react"
import { Slot } from "radix-ui"
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

/* ---------- Variant styles (JulIA Design System) ---------- */

const variantStyles: Record<ButtonVariant, string> = {
  default:
    "bg-accent text-text-inverse hover:bg-accent-hover active:bg-accent-active shadow-sm",
  primary:
    "bg-accent text-text-inverse hover:bg-accent-hover active:bg-accent-active shadow-sm",
  secondary:
    "bg-surface border border-border text-text-primary hover:bg-surface-hover hover:border-border-hover active:bg-surface-active",
  outline:
    "bg-surface border border-border text-text-primary hover:bg-surface-hover hover:border-border-hover active:bg-surface-active",
  ghost:
    "bg-transparent text-text-secondary hover:bg-surface-hover hover:text-text-primary active:bg-surface-active",
  danger:
    "bg-error text-white hover:brightness-110 active:brightness-90 shadow-sm",
  destructive:
    "bg-error text-white hover:brightness-110 active:brightness-90 shadow-sm",
  link: "text-accent-text underline-offset-4 hover:underline bg-transparent",
}

const sizeStyles: Record<ButtonSize, string> = {
  default: "h-10 px-4 text-sm gap-2",
  md: "h-10 px-4 text-sm gap-2",
  sm: "h-8 px-3 text-sm gap-1.5",
  lg: "h-12 px-6 text-base gap-2.5",
  icon: "size-9",
  "icon-xs": "size-6 rounded-md [&_svg:not([class*='size-'])]:size-3",
  "icon-sm": "size-8",
  "icon-lg": "size-10",
}

/* ---------- Spinner ---------- */

function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("animate-spin h-4 w-4", className)}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
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
        "inline-flex items-center justify-center whitespace-nowrap font-heading font-medium",
        "rounded-md transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg-primary",
        "disabled:opacity-50 disabled:pointer-events-none",
        "[&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 [&_svg]:shrink-0 shrink-0",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {loading && <Spinner />}
      {children}
    </Comp>
  )
}

export { Button }
