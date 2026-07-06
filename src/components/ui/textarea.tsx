import * as React from "react"
import { cn } from "@/lib/utils"

export interface TextareaProps extends React.ComponentProps<"textarea"> {
  label?: string
  error?: string
  hint?: string
}

function Textarea({
  label,
  error,
  hint,
  className,
  id,
  ...props
}: TextareaProps) {
  const textareaId = id ?? label?.toLowerCase().replace(/\s+/g, "-")

  const textareaElement = (
    <textarea
      id={textareaId}
      data-slot="textarea"
      className={cn(
        "w-full min-w-0 rounded-md px-3 py-2 text-sm font-sans",
        "bg-surface-2 border border-edge text-fg",
        "placeholder:text-fg-subtle",
        "transition-colors",
        "hover:border-edge-strong",
        "focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        error && "border-danger focus:border-danger focus:ring-danger",
        className
      )}
      aria-invalid={!!error}
      aria-describedby={
        error
          ? `${textareaId}-error`
          : hint
            ? `${textareaId}-hint`
            : undefined
      }
      {...props}
    />
  )

  if (!label && !error && !hint) {
    return textareaElement
  }

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label
          htmlFor={textareaId}
          className="text-sm font-medium text-fg-muted"
        >
          {label}
        </label>
      )}

      {textareaElement}

      {error && (
        <p
          id={`${textareaId}-error`}
          className="text-xs text-danger-text"
          role="alert"
        >
          {error}
        </p>
      )}

      {!error && hint && (
        <p id={`${textareaId}-hint`} className="text-xs text-fg-subtle">
          {hint}
        </p>
      )}
    </div>
  )
}

export { Textarea }
