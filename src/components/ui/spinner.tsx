import * as React from "react"
import { cn } from "@/lib/utils"

type SpinnerSize = "xs" | "sm" | "md" | "lg"

const sizeStyles: Record<SpinnerSize, string> = {
  xs: "h-3 w-3",
  sm: "h-4 w-4",
  md: "h-5 w-5",
  lg: "h-7 w-7",
}

export interface SpinnerProps {
  size?: SpinnerSize
  className?: string
}

function Spinner({ size = "sm", className }: SpinnerProps) {
  return (
    <svg
      className={cn("animate-spin", sizeStyles[size], className)}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
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

export interface LoadingBlockProps {
  label?: string
  className?: string
}

/** Bloco de carregamento centralizado — substitui os Loader2/divs ad-hoc das páginas. */
function LoadingBlock({ label, className }: LoadingBlockProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 py-16",
        className
      )}
      role="status"
    >
      <Spinner size="lg" className="text-accent" />
      {label && <p className="text-sm text-fg-muted">{label}</p>}
    </div>
  )
}

export { Spinner, LoadingBlock }
