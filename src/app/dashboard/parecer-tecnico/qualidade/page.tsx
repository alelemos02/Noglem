"use client";

/**
 * Dashboard de qualidade — visão do DONO da ferramenta (não do usuário final).
 * Métricas do desempenho da IA ao longo de todos os pareceres. Protegido no
 * backend por require_owner (em produção, só e-mails de OWNER_EMAILS).
 */

import { useEffect, useState } from "react";
import { patecApi, type QualidadeResponse } from "@/lib/patec-api";
import { PageHeader } from "@/components/ui/page-header";
import { Alert } from "@/components/ui/alert";
import { LoadingBlock } from "@/components/ui/spinner";

const STATUS_LABELS: Record<string, string> = {
  A: "Aprovado",
  B: "Aprov. c/ com.",
  C: "Rejeitado",
  D: "Info ausente",
  E: "Adicional",
};
const STATUS_BAR: Record<string, string> = {
  A: "bg-success",
  B: "bg-warning",
  C: "bg-danger",
  D: "bg-fg-subtle",
  E: "bg-info",
};

function Tile({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-lg border border-edge bg-surface-1 p-4">
      <div className="text-xs uppercase tracking-wide text-fg-subtle">{label}</div>
      <div className="mt-1 font-mono text-2xl font-semibold tabular-nums text-fg">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-fg-subtle">{hint}</div>}
    </div>
  );
}

function Signal({
  label,
  itens,
  taxa,
  hint,
}: {
  label: string;
  itens: number;
  taxa?: number;
  hint: string;
}) {
  const atencao = itens > 0;
  return (
    <div
      className={`rounded-lg border p-4 ${
        atencao ? "border-warning/40 bg-warning-subtle/30" : "border-edge bg-surface-1"
      }`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium text-fg">{label}</span>
        <span className="font-mono text-lg font-semibold tabular-nums text-fg">
          {itens}
          {taxa != null && (
            <span className="ml-1 text-xs text-fg-subtle">
              ({(taxa * 100).toFixed(1)}%)
            </span>
          )}
        </span>
      </div>
      <div className="mt-1 text-xs text-fg-subtle">{hint}</div>
    </div>
  );
}

export default function QualidadePage() {
  const [data, setData] = useState<QualidadeResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    patecApi.admin
      .qualidade()
      .then(setData)
      .catch((e) =>
        setError(
          e instanceof Error && /403|restrito/i.test(e.message)
            ? "Acesso restrito ao dono da ferramenta."
            : "Não consegui carregar as métricas."
        )
      );
  }, []);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader
        title="Dashboard de qualidade"
        description="Visão do dono — desempenho da IA em todos os pareceres. Não é exposto ao usuário final."
        backHref="/dashboard/parecer-tecnico"
        backLabel="Pareceres"
        className="mb-0"
      />

      {error && <Alert variant="danger">{error}</Alert>}

      {!error && !data && <LoadingBlock label="Carregando métricas..." />}

      {data && (
        <div className="space-y-8">
          {/* Volume */}
          <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Tile label="Pareceres" value={data.pareceres.total} hint={`${data.pareceres.analisados} analisados`} />
            <Tile label="Itens" value={data.itens.total} />
            <Tile label="Itens / parecer" value={data.itens.media_por_parecer} />
            <Tile
              label="Correção manual"
              value={`${(data.qualidade.correcao_manual.taxa * 100).toFixed(1)}%`}
              hint={`${data.qualidade.correcao_manual.itens} itens`}
            />
          </section>

          {/* Sinais de qualidade */}
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-fg-muted">
              Sinais de qualidade
            </h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Signal
                label="Correção manual"
                itens={data.qualidade.correcao_manual.itens}
                taxa={data.qualidade.correcao_manual.taxa}
                hint="Itens que o engenheiro sobrescreveu após a IA — se alto, a IA erra muito."
              />
              <Signal
                label="Requisitos não cobertos"
                itens={data.qualidade.requisitos_nao_cobertos.itens}
                taxa={data.qualidade.requisitos_nao_cobertos.taxa}
                hint="Requisito aprovado que a IA não cobriu (reconciliação injetou 'D')."
              />
              <Signal
                label="Correções do verificador Pro"
                itens={data.qualidade.verificador_correcoes}
                hint="Itens reclassificados pela segunda IA (verificação cruzada)."
              />
              <Signal
                label="Alertas de consistência"
                itens={data.qualidade.consistencia_flags}
                hint="Termo do requisito achado no fornecedor, mas item classificado como desvio."
              />
            </div>
          </section>

          {/* Distribuição de status */}
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-fg-muted">
              Distribuição de status ({data.itens.total} itens)
            </h2>
            <div className="space-y-1.5">
              {(["A", "B", "C", "D", "E"] as const).map((s) => {
                const n = data.itens.por_status[s] ?? 0;
                const pct = data.itens.total ? (n / data.itens.total) * 100 : 0;
                return (
                  <div key={s} className="flex items-center gap-3 text-sm">
                    <span className="w-28 shrink-0 text-fg-muted">{STATUS_LABELS[s]}</span>
                    <div className="h-3 flex-1 overflow-hidden rounded-sm bg-surface-2">
                      <div
                        className={`h-full rounded-sm ${STATUS_BAR[s]}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="w-16 shrink-0 text-right font-mono tabular-nums text-fg-subtle">
                      {n} · {pct.toFixed(0)}%
                    </span>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Por disciplina / desfecho */}
          <section className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-fg-muted">
                Por disciplina
              </h2>
              <ul className="space-y-1 text-sm">
                {Object.entries(data.pareceres.por_disciplina).map(([k, v]) => (
                  <li key={k} className="flex justify-between">
                    <span className="capitalize text-fg-muted">{k}</span>
                    <span className="font-mono tabular-nums text-fg-subtle">{v}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-fg-muted">
                Por desfecho
              </h2>
              <ul className="space-y-1 text-sm">
                {Object.entries(data.pareceres.por_desfecho).map(([k, v]) => (
                  <li key={k} className="flex justify-between">
                    <span className="text-fg-muted">{k}</span>
                    <span className="font-mono tabular-nums text-fg-subtle">{v}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
