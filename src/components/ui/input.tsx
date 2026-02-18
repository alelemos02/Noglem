import * as React from "react"
import { cn } from "@/lib/utils"

export interface InputProps extends React.ComponentProps<"input"> {
  label?: string
  error?: string
  hint?: string
}

function Input({
  label,
  error,
  hint,
  className,
  id,
  type,
  ...props
}: InputProps) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-")

  const inputElement = (
    <input
      type={type}
      id={inputId}
      data-slot="input"
      className={cn(
        "h-10 w-full min-w-0 rounded-md px-3 text-sm font-body",
        "bg-surface border border-border text-text-primary",
        "placeholder:text-text-tertiary",
        "transition-colors",
        "hover:border-border-hover",
        "focus:outline-none focus:border-border-focus focus:ring-1 focus:ring-accent",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        "file:text-foreground file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium",
        error && "border-error focus:border-error focus:ring-error",
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
  )

  if (!label && !error && !hint) {
    return inputElement
  }

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

      {inputElement}

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

export { Input }
