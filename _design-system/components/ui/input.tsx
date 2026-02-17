import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, className, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="text-sm font-medium font-heading text-text-secondary"
          >
            {label}
          </label>
        )}

        <input
          ref={ref}
          id={inputId}
          className={cn(
            // base
            'h-10 w-full rounded-md px-3 text-sm font-body',
            'bg-surface border border-border text-text-primary',
            'placeholder:text-text-tertiary',
            // transitions
            'transition-colors duration-fast',
            // hover
            'hover:border-border-hover',
            // focus
            'focus:outline-none focus:border-border-focus focus:ring-1 focus:ring-accent',
            // disabled
            'disabled:opacity-50 disabled:cursor-not-allowed',
            // error state
            error && 'border-error focus:border-error focus:ring-error',
            className
          )}
          aria-invalid={!!error}
          aria-describedby={
            error
              ? `${inputId}-error`
              : hint
                ? `${inputId}-hint`
                : undefined
          }
          {...props}
        />

        {error && (
          <p
            id={`${inputId}-error`}
            className="text-xs text-error-text"
            role="alert"
          >
            {error}
          </p>
        )}

        {!error && hint && (
          <p id={`${inputId}-hint`} className="text-xs text-text-tertiary">
            {hint}
          </p>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'
export { Input }
