import * as React from "react"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { tools, getStatusBadgeProps } from "@/lib/tools-registry"
import { cn } from "@/lib/utils"

export interface PageHeaderProps {
  /** id da ferramenta no tools-registry — resolve título, descrição e badge de status */
  tool?: string
  /** override manual (páginas fora do registry, ex: convites) */
  title?: string
  description?: string
  backHref?: string
  backLabel?: string
  actions?: React.ReactNode
  className?: string
}

/**
 * Header padrão de página do dashboard.
 * O nome canônico vem do registry — o mesmo exibido na navegação.
 */
function PageHeader({
  tool,
  title,
  description,
  backHref,
  backLabel = "Voltar",
  actions,
  className,
}: PageHeaderProps) {
  const registryTool = tool ? tools.find((t) => t.id === tool) : undefined
  const badge = registryTool ? getStatusBadgeProps(registryTool.status) : null
  const resolvedTitle = title ?? registryTool?.title
  const resolvedDescription = description ?? registryTool?.description

  return (
    <header className={cn("mb-8", className)}>
      {backHref && (
        <Link
          href={backHref}
          className="microlabel mb-3 inline-flex items-center gap-1.5 transition-colors hover:text-fg-muted"
        >
          <ArrowLeft className="h-3 w-3" aria-hidden="true" />
          {backLabel}
        </Link>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-fg">
          {resolvedTitle}
        </h1>
        {badge && (
          <Badge variant={badge.variant} dot={badge.dot}>
            {badge.label}
          </Badge>
        )}
        {actions && (
          <div className="ml-auto flex items-center gap-2">{actions}</div>
        )}
      </div>
      {resolvedDescription && (
        <p className="mt-1.5 max-w-2xl text-[13px] text-fg-muted">
          {resolvedDescription}
        </p>
      )}
    </header>
  )
}

export { PageHeader }
