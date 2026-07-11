import type { Metadata } from "next"
import { ExternalLink } from "lucide-react"
import { MarketingNav } from "@/components/marketing/nav"
import { MarketingFooter } from "@/components/marketing/footer"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { site } from "@/lib/site"

export const metadata: Metadata = {
  title: "Segurança",
  description:
    "Como a Noglem protege documentos de projeto: compromissos dos provedores de IA, isolamento por workspace, criptografia e NDA contratual — com link para cada fonte oficial.",
}

const layers = [
  {
    layer: "OpenAI API",
    commitment:
      "Dados enviados via API não são usados para treinar modelos por padrão. Retenção limitada a até 30 dias para monitoramento de abuso, depois excluídos. Criptografia AES-256 em repouso e TLS 1.2+ em trânsito. Auditoria SOC 2 Type 2.",
    sourceLabel: "openai.com/enterprise-privacy",
    sourceUrl: "https://openai.com/enterprise-privacy",
  },
  {
    layer: "Google Gemini API (tier pago)",
    commitment:
      "Nos serviços pagos, o Google não usa prompts nem respostas para melhorar seus produtos.",
    sourceLabel: "ai.google.dev/gemini-api/terms",
    sourceUrl: "https://ai.google.dev/gemini-api/terms",
  },
  {
    layer: "Noglem",
    commitment:
      "Workspaces isolados por projeto e cliente, controle de acesso, registro de atividade, NDA contratual.",
    sourceLabel: "Contrato de serviço",
    sourceUrl: null,
  },
]

export default function SegurancaPage() {
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <MarketingNav />

      <main className="flex-1 pt-16">
        <section className="py-16 sm:py-20">
          <div className="container mx-auto max-w-4xl px-4">
            <p className="microlabel">Segurança</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
              Segurança e confidencialidade
            </h1>
            <p className="mt-5 max-w-3xl leading-relaxed text-fg-muted">
              A Noglem processa documentos através das APIs corporativas de provedores que
              publicam compromissos formais de proteção de dados. Abaixo, o que cada camada
              garante, com link para a fonte oficial.
            </p>

            <div className="mt-10 overflow-x-auto rounded-lg border border-edge">
              <Table className="min-w-[640px]">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[180px]">Camada</TableHead>
                    <TableHead>Compromisso</TableHead>
                    <TableHead className="w-[220px]">Fonte</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {layers.map((row) => (
                    <TableRow key={row.layer}>
                      <TableCell className="align-top font-medium text-fg">
                        {row.layer}
                      </TableCell>
                      <TableCell className="align-top leading-relaxed text-fg-muted">
                        {row.commitment}
                      </TableCell>
                      <TableCell className="align-top">
                        {row.sourceUrl ? (
                          <a
                            href={row.sourceUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 font-mono text-xs text-accent hover:underline"
                          >
                            {row.sourceLabel}
                            <ExternalLink className="size-3 shrink-0" aria-hidden="true" />
                          </a>
                        ) : (
                          <span className="font-mono text-xs text-fg-muted">
                            {row.sourceLabel}
                          </span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <div className="mt-10 max-w-3xl space-y-4 leading-relaxed text-fg-muted">
              <p>
                Distinguimos duas garantias que costumam ser confundidas:{" "}
                <strong className="font-semibold text-fg">
                  não usar seus dados para treinamento
                </strong>{" "}
                e{" "}
                <strong className="font-semibold text-fg">não armazenar seus dados</strong>. A
                primeira é compromisso contratual dos provedores que usamos. A segunda tem
                janelas técnicas de retenção (até 30 dias, para monitoramento de abuso)
                definidas nos termos de cada provedor, linkados acima.
              </p>
            </div>

            <p className="mt-8 font-mono text-xs text-fg-subtle">
              Termos verificados em julho de 2026.
            </p>

            <p className="mt-12 border-t border-edge pt-8 text-sm text-fg-muted">
              Dúvidas sobre segurança ou compliance?{" "}
              <a href={`mailto:${site.demoEmail}`} className="text-accent hover:underline">
                Fale com a gente
              </a>
              .
            </p>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </div>
  )
}
