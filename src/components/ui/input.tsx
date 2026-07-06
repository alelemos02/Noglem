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
        "h-9 w-full min-w-0 rounded-md px-3 text-sm font-sans",
        "bg-surface-2 border border-edge text-fg",
        "placeholder:text-fg-subtle",
        "transition-colors",
        "hover:border-edge-strong",
        "focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        "file:text-fg file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium",
        error && "border-danger focus:border-danger focus:ring-danger",
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
          className="text-sm font-medium text-fg-muted"
        >
          {label}
        </label>
      )}

      {inputElement}

      {error && (
        <p
          id={`${inputId}-error`}
          className="text-xs text-danger-text"
          role="alert"
        >
          {error}
        </p>
      )}

      {!error && hint && (
        <p id={`${inputId}-hint`} className="text-xs text-fg-subtle">
          {hint}
        </p>
      )}
    </div>
  )
}

export { Input }
