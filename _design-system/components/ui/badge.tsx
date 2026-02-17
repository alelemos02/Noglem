import { type HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
  dot?: boolean
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-surface-hover text-text-secondary border-border',
  success: 'bg-success-muted text-success-text border-success/20',
  warning: 'bg-warning-muted text-warning-text border-warning/20',
  error: 'bg-error-muted text-error-text border-error/20',
  info: 'bg-info-muted text-info-text border-info/20',
}

const dotColors: Record<BadgeVariant, string> = {
  default: 'bg-text-tertiary',
  success: 'bg-success',
  warning: 'bg-warning',
  error: 'bg-error',
  info: 'bg-info',
}

function Badge({
  variant = 'default',
  dot = false,
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5',
        'rounded-md border px-2 py-0.5',
        'text-xs font-medium font-heading tracking-wide',
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className={cn('h-1.5 w-1.5 rounded-full', dotColors[variant])}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  )
}

Badge.displayName = 'Badge'
export { Badge }
