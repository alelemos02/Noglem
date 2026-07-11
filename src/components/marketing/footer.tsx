import { Wordmark } from "@/components/marketing/nav"
import { site } from "@/lib/site"

function MarketingFooter() {
  const registrations = [
    site.cnpj && `CNPJ ${site.cnpj}`,
    site.crea && `CREA-SP ${site.crea}`,
  ].filter(Boolean)

  return (
    <footer className="border-t border-edge py-10">
      <div className="container mx-auto px-4">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-start">
          <div className="space-y-1.5">
            <Wordmark />
            <p className="text-sm text-fg-muted">{site.legalName}</p>
            {registrations.length > 0 && (
              <p className="font-mono text-xs tabular-nums text-fg-subtle">
                {registrations.join(" · ")}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1.5 text-sm sm:items-end">
            <a
              href={`mailto:${site.demoEmail}`}
              className="text-fg-muted transition-colors hover:text-fg"
            >
              {site.demoEmail}
            </a>
            <a
              href={site.linkedinUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-fg-muted transition-colors hover:text-fg"
            >
              LinkedIn
            </a>
          </div>
        </div>
        <p className="mt-8 text-xs text-fg-subtle">
          © {new Date().getFullYear()} {site.legalName}. Todos os direitos reservados.
        </p>
      </div>
    </footer>
  )
}

export { MarketingFooter }
