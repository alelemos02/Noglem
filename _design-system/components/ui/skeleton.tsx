import { type HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {}

function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        'rounded-md bg-surface-hover',
        'bg-gradient-to-r from-surface-hover via-border/30 to-surface-hover',
        'bg-[length:200%_100%] animate-shimmer',
        className
      )}
      aria-hidden="true"
      {...props}
    />
  )
}

Skeleton.displayName = 'Skeleton'
export { Skeleton }
