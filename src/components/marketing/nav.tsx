import Link from "next/link"
import { Button } from "@/components/ui/button"
import { site } from "@/lib/site"
import { cn } from "@/lib/utils"

/* Marca pública da plataforma — não usar o Logo Jul/IA fora do login. */
function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("font-sans text-lg font-semibold tracking-tight text-fg", className)}>
      {site.name}
    </span>
  )
}

function MarketingNav() {
  return (
    <header className="fixed inset-x-0 top-0 z-(--z-fixed) border-b border-edge bg-canvas/80 backdrop-blur">
      <div className="container mx-auto flex h-16 items-center justify-between gap-4 px-4">
        <Link href="/" aria-label="Noglem — página inicial">
          <Wordmark />
        </Link>

        <nav className="hidden items-center gap-6 md:flex" aria-label="Navegação principal">
          {site.navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm text-fg-muted transition-colors hover:text-fg"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Button variant="ghost" asChild className="hidden sm:inline-flex">
            <Link href="/sign-in">Entrar</Link>
          </Button>
          <Button asChild>
            <a href={site.demoHref}>Agendar demonstração</a>
          </Button>
        </div>
      </div>
    </header>
  )
}

export { MarketingNav, Wordmark }
