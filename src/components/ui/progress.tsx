"use client"

import * as React from "react"
import { Progress as ProgressPrimitive } from "radix-ui"
import { cn } from "@/lib/utils"

export interface ProgressProps {
  value?: number
  max?: number
  /** Barra animada sem percentual conhecido */
  indeterminate?: boolean
  label?: string
  className?: string
}

function Progress({
  value = 0,
  max = 100,
  indeterminate = false,
  label,
  className,
}: ProgressProps) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0

  return (
    <div className={className}>
      {label && (
        <div className="mb-2 flex items-baseline justify-between gap-4">
          <span className="min-w-0 truncate text-[13px] font-medium text-fg">
            {label}
          </span>
          {!indeterminate && (
            <span className="shrink-0 font-mono text-xs tabular-nums text-fg-muted">
              {Math.round(pct)}%
            </span>
          )}
        </div>
      )}
      <ProgressPrimitive.Root
        value={indeterminate ? undefined : value}
        max={max}
        className="h-1 w-full overflow-hidden rounded-sm bg-surface-3"
      >
        <ProgressPrimitive.Indicator
          className={cn(
            "h-full rounded-sm bg-accent",
            indeterminate
              ? "w-full bg-gradient-to-r from-accent/25 via-accent to-accent/25 bg-[length:200%_100%] animate-shimmer"
              : "transition-transform duration-300 ease-out"
          )}
          style={
            indeterminate
              ? undefined
              : { transform: `translateX(-${100 - pct}%)` }
          }
        />
      </ProgressPrimitive.Root>
    </div>
  )
}

export { Progress }
