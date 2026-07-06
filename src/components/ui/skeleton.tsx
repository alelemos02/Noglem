import * as React from "react"
import { cn } from "@/lib/utils"

export type SkeletonProps = React.ComponentProps<"div">

function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      data-slot="skeleton"
      className={cn(
        "rounded-md bg-surface-2",
        "bg-gradient-to-r from-surface-2 via-edge/40 to-surface-2",
        "bg-[length:200%_100%] animate-shimmer",
        className
      )}
      aria-hidden="true"
      {...props}
    />
  )
}

export { Skeleton }
