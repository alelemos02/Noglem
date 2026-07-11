import * as React from "react"
import { cn } from "@/lib/utils"

/* Wrapper padrão de seção da landing: âncora com offset da navbar fixa
   e container centralizado. */

type SectionProps = React.ComponentProps<"section">

function Section({ className, children, ...props }: SectionProps) {
  return (
    <section className={cn("scroll-mt-24 py-16 sm:py-24", className)} {...props}>
      <div className="container mx-auto px-4">{children}</div>
    </section>
  )
}

type SectionHeadingProps = {
  eyebrow?: string
  title: string
  description?: string
  className?: string
}

function SectionHeading({ eyebrow, title, description, className }: SectionHeadingProps) {
  return (
    <div className={cn("max-w-2xl space-y-3", className)}>
      {eyebrow && <p className="microlabel">{eyebrow}</p>}
      <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h2>
      {description && <p className="leading-relaxed text-fg-muted">{description}</p>}
    </div>
  )
}

export { Section, SectionHeading }
