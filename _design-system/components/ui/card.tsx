import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

/* ---------- Card Root ---------- */

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean
}

const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ interactive = false, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'rounded-lg border border-border bg-surface',
          'transition-colors duration-fast',
          interactive && [
            'cursor-pointer',
            'hover:border-border-hover hover:bg-surface-hover',
            'active:bg-surface-active',
          ],
          className
        )}
        {...props}
      />
    )
  }
)
Card.displayName = 'Card'

/* ---------- Card Header ---------- */

const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('flex flex-col gap-1.5 p-4 pb-0', className)}
      {...props}
    />
  )
)
CardHeader.displayName = 'CardHeader'

/* ---------- Card Content ---------- */

const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('p-4', className)} {...props} />
  )
)
CardContent.displayName = 'CardContent'

/* ---------- Card Footer ---------- */

const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex items-center p-4 pt-0 border-t border-border mt-auto',
        className
      )}
      {...props}
    />
  )
)
CardFooter.displayName = 'CardFooter'

export { Card, CardHeader, CardContent, CardFooter }
