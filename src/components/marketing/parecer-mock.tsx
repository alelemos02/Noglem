import { FileText } from "lucide-react"
import { Badge } from "@/components/ui/badge"

/* Mock decorativo do hero: trecho de parecer com desvio apontado e
   referência de origem. Dados 100% fictícios. */

function ParecerMock() {
  return (
    <div aria-hidden="true" className="relative w-full max-w-[560px] animate-fade-in-up">
      <div className="absolute -inset-8 -z-10 bg-accent-subtle opacity-40 blur-3xl" />

      <div className="overflow-hidden rounded-lg border border-edge bg-surface-1 shadow-lg">
        <div className="flex items-center justify-between gap-3 border-b border-edge px-4 py-3">
          <span className="microlabel">Parecer técnico · PT-2210-INS-001 · Rev. B</span>
          <Badge variant="secondary">Em análise</Badge>
        </div>

        <div className="space-y-4 px-4 py-4">
          <p className="font-mono text-sm tabular-nums text-fg">
            4.2 · Transmissor de pressão — TAG PIT-2201A
          </p>

          <div className="space-y-2 rounded-r-sm border-l-2 border-danger bg-danger-subtle px-3 py-2.5">
            <Badge variant="error">Desvio</Badge>
            <p className="text-[13px] leading-relaxed text-fg">
              Faixa calibrada ofertada de{" "}
              <span className="font-mono tabular-nums">0–25 bar</span> não atende ao requisito
              de <span className="font-mono tabular-nums">0–40 bar</span> da folha de dados.
            </p>
            <p className="flex items-center gap-1.5 font-mono text-xs text-fg-subtle">
              <FileText className="size-3.5 shrink-0" />
              FD-2210-INS-014 — pág. 12 · Proposta do fornecedor — pág. 87
            </p>
          </div>

          <div className="space-y-2 rounded-r-sm border-l-2 border-success bg-success-subtle px-3 py-2.5">
            <Badge variant="success">Conforme</Badge>
            <p className="text-[13px] leading-relaxed text-fg">
              Material do corpo em aço inox 316L, conforme especificação do projeto.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-edge px-4 py-3">
          <span className="text-xs text-fg-subtle">Aguardando aprovação do engenheiro</span>
          <div className="flex items-center gap-2">
            <span className="inline-flex h-7 items-center rounded-md border border-edge bg-surface-2 px-2.5 text-xs text-fg-muted">
              Solicitar ajuste
            </span>
            <span className="inline-flex h-7 items-center rounded-md bg-accent px-2.5 text-xs font-medium text-accent-fg">
              Aprovar
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export { ParecerMock }
