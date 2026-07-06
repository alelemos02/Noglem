import * as React from "react"
import { Info, CheckCircle2, AlertTriangle, AlertCircle, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

type AlertVariant = "info" | "success" | "warning" | "danger"

const variantStyles: Record<AlertVariant, string> = {
  info: "border-info/30 bg-info-subtle [&>svg]:text-info",
  success: "border-success/30 bg-success-subtle [&>svg]:text-success",
  warning: "border-warning/30 bg-warning-subtle [&>svg]:text-warning",
  danger: "border-danger/30 bg-danger-subtle [&>svg]:text-danger",
}

const variantIcons: Record<AlertVariant, LucideIcon> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: AlertCircle,
}

export interface AlertProps extends React.ComponentProps<"div"> {
  variant?: AlertVariant
  title?: string
  icon?: LucideIcon
}

/**
 * Callout inline persistente (erro de formulário, aviso de limitação, resultado parcial).
 * Para eventos transientes (sucesso de operação, falha pontual), use toast.
 */
function Alert({
  variant = "info",
  title,
  icon,
  className,
  children,
  ...props
}: AlertProps) {
  const Icon = icon ?? variantIcons[variant]

  return (
    <div
      role="alert"
      data-slot="alert"
      className={cn(
        "flex items-start gap-3 rounded-lg border px-4 py-3 text-[13px]",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1 text-fg-muted">
        {title && <p className="font-medium text-fg">{title}</p>}
        {children && <div className={cn(title && "mt-0.5")}>{children}</div>}
      </div>
    </div>
  )
}

export { Alert }
