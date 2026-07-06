import * as React from "react"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

export interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  action?: React.ReactNode
  size?: "sm" | "md"
  className?: string
}

function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  size = "md",
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-edge text-center",
        size === "md" ? "px-6 py-14" : "px-4 py-8",
        className
      )}
    >
      <Icon
        className={cn(
          "text-fg-subtle",
          size === "md" ? "h-6 w-6" : "h-5 w-5"
        )}
        aria-hidden="true"
      />
      <h3 className="mt-3 text-sm font-semibold text-fg">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-fg-muted">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export { EmptyState }
