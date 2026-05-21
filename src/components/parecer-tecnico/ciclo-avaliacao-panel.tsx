"use client";

import { useState, useEffect, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  patecApi,
  type CicloResumoResponse,
  type ItemRevisaoResponse,
  type RodadaAvaliacaoResponse,
} from "@/lib/patec-api";
import { useWorkspace } from "./workspace-context";

// ── helpers ──────────────────────────────────────────────────────────────────

const ESTADO_LABELS: Record<string, string> = {
  ABERTO: "Aberto",
  PENDENTE_FORNECEDOR: "Pendente Fornecedor",
  EM_REAVALIACAO: "Em Reavaliação",
  RESOLVIDO: "Resolvido",
  ESCALONADO: "Escalado",
};

const STATUS_GLOBAL_LABELS: Record<string, string> = {
  EM_ANALISE: "Em Análise",
  AGUARDANDO_FORNECEDOR: "Aguardando Fornecedor",
  EM_REAVALIACAO: "Em Reavaliação",
  CONCLUIDO: "Concluído",
};

const VEREDITO_LABELS: Record<string, string> = {
  ATENDE: "Atende",
  PARCIAL: "Parcial",
  NAO_ATENDE: "Não Atende",
};

function veredito_variant(v: string | null): "success" | "warning" | "error" | "secondary" {
  if (v === "ATENDE") return "success";
  if (v === "PARCIAL") return "warning";
  if (v === "NAO_ATENDE") return "error";
  return "secondary";
}

function origem_label(o: string) {
  if (o === "PROPOSTA_INICIAL") return "Proposta inicial";
  if (o === "RESPOSTA_FORNECEDOR") return "Resposta do fornecedor";
  if (o === "COMENTARIO_ENGENHARIA") return "Comentário de engenharia";
  return o;
}

function fmt_date(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

// ── sub-components ────────────────────────────────────────────────────────────

function HistoricoTimeline({ parecerId, itemId, onClose }: {
  parecerId: string;
  itemId: string;
  onClose: () => void;
}) {
  const [rodadas, setRodadas] = useState<RodadaAvaliacaoResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    patecApi.ciclo.historico(parecerId, itemId)
      .then(setRodadas)
      .finally(() => setLoading(false));
  }, [parecerId, itemId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-lg border border-border bg-bg-secondary shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <h3 className="text-sm font-bold text-text-primary">Histórico de Rodadas</h3>
          <button
            onClick={onClose}
            className="text-xs text-text-tertiary hover:text-text-primary"
          >
            Fechar
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          ) : rodadas.length === 0 ? (
            <p className="text-sm text-text-tertiary">Nenhuma rodada registrada.</p>
          ) : (
            <ol className="relative border-l border-border pl-6 space-y-6">
              {rodadas.map((r) => (
                <li key={r.id} className="relative">
                  <span className="absolute -left-[1.35rem] top-1 h-3 w-3 rounded-full border-2 border-accent bg-bg-secondary" />
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-bold text-text-primary">
                        Rodada {r.numero_rodada} — {origem_label(r.origem)}
                      </span>
                      {r.classificacao_ia && (
                        <Badge variant="secondary" className="text-[10px]">
                          {r.classificacao_ia}
                        </Badge>
                      )}
                      {r.veredito_ia && (
                        <Badge variant={veredito_variant(r.veredito_ia)} className="text-[10px]">
                          IA: {VEREDITO_LABELS[r.veredito_ia] ?? r.veredito_ia}
                        </Badge>
                      )}
                      {r.decisao_humana && (
                        <Badge variant={veredito_variant(r.decisao_humana)} dot className="text-[10px]">
                          Eng.: {VEREDITO_LABELS[r.decisao_humana] ?? r.decisao_humana}
                        </Badge>
                      )}
                    </div>
                    <p className="text-[11px] text-text-tertiary">{fmt_date(r.criado_em)}</p>
                    {r.conteudo && (
                      <p className="rounded bg-bg-primary px-2 py-1 text-xs text-text-secondary">
                        {r.conteudo}
                      </p>
                    )}
                    {r.justificativa_ia && (
                      <p className="text-xs text-text-secondary">
                        <span className="font-semibold">Justificativa IA: </span>
                        {r.justificativa_ia}
                      </p>
                    )}
                    {r.acao_requerida && (
                      <p className="text-xs text-warning">
                        <span className="font-semibold">Ação requerida: </span>
                        {r.acao_requerida}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}

function ItemRevisaoCard({
  item,
  parecerId,
  onDecidido,
}: {
  item: ItemRevisaoResponse;
  parecerId: string;
  onDecidido: () => void;
}) {
  const [deciding, setDeciding] = useState(false);
  const [escalando, setEscalando] = useState(false);
  const [showHistorico, setShowHistorico] = useState(false);
  const [error, setError] = useState("");
  const r = item.ultima_rodada;

  const decidir = async (decisao: "ATENDE" | "NAO_ATENDE" | "PARCIAL") => {
    setDeciding(true);
    setError("");
    try {
      await patecApi.ciclo.decidir(parecerId, item.id, decisao);
      onDecidido();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao registrar decisão");
    } finally {
      setDeciding(false);
    }
  };

  const escalonar = async () => {
    if (!confirm(`Escalonar item ${item.numero}? Esta ação retira o item do ciclo de pendências.`)) return;
    setEscalando(true);
    setError("");
    try {
      await patecApi.ciclo.escalonar(parecerId, item.id);
      onDecidido();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao escalonar");
    } finally {
      setEscalando(false);
    }
  };

  return (
    <>
      {showHistorico && (
        <HistoricoTimeline
          parecerId={parecerId}
          itemId={item.id}
          onClose={() => setShowHistorico(false)}
        />
      )}
      <div className="rounded-lg border border-border bg-surface p-4 space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-bold text-text-tertiary">
              #{item.numero}
            </span>
            {item.categoria && (
              <Badge variant="secondary" className="text-[10px]">{item.categoria}</Badge>
            )}
            {item.prioridade && (
              <Badge
                variant={item.prioridade === "ALTA" ? "error" : item.prioridade === "MEDIA" ? "warning" : "secondary"}
                className="text-[10px]"
              >
                {item.prioridade}
              </Badge>
            )}
          </div>
          <button
            onClick={() => setShowHistorico(true)}
            className="shrink-0 text-[11px] text-accent hover:underline"
          >
            Ver histórico
          </button>
        </div>

        {/* Requisito */}
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-text-tertiary">
            Requisito
          </p>
          <p className="text-xs text-text-primary">{item.descricao_requisito}</p>
          {item.valor_requerido && (
            <p className="mt-0.5 text-[11px] text-text-secondary">
              Valor requerido: {item.valor_requerido}
            </p>
          )}
        </div>

        {r && (
          <>
            {/* Pendência */}
            {r.acao_requerida && (
              <div className="rounded border border-warning/30 bg-warning-muted px-3 py-2">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-warning">
                  Pendência apontada
                </p>
                <p className="text-xs text-text-primary">{r.acao_requerida}</p>
              </div>
            )}

            {/* Resposta do fornecedor */}
            {r.conteudo && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-text-tertiary">
                  Resposta do Fornecedor
                </p>
                <p className="rounded bg-bg-primary px-3 py-2 text-xs text-text-primary">
                  {r.conteudo}
                </p>
              </div>
            )}

            {/* Veredito IA */}
            {r.veredito_ia && (
              <div className="rounded border border-border bg-bg-secondary px-3 py-2 space-y-1">
                <div className="flex items-center gap-2">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-text-tertiary">
                    Veredito da IA
                  </p>
                  <Badge variant={veredito_variant(r.veredito_ia)} className="text-[10px]">
                    {VEREDITO_LABELS[r.veredito_ia] ?? r.veredito_ia}
                  </Badge>
                </div>
                {r.justificativa_ia && (
                  <p className="text-xs text-text-secondary">{r.justificativa_ia}</p>
                )}
              </div>
            )}
          </>
        )}

        {/* Decision buttons */}
        {error && (
          <p className="text-xs text-error">{error}</p>
        )}
        <div className="flex flex-wrap gap-2 pt-1">
          <Button
            size="sm"
            variant="secondary"
            className="text-xs border-success/50 text-success hover:bg-success/10"
            onClick={() => decidir("ATENDE")}
            disabled={deciding || escalando}
          >
            {deciding ? "..." : "Confirmar: Atende"}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            className="text-xs border-warning/50 text-warning hover:bg-warning/10"
            onClick={() => decidir("PARCIAL")}
            disabled={deciding || escalando}
          >
            Confirmar: Parcial
          </Button>
          <Button
            size="sm"
            variant="secondary"
            className="text-xs border-error/50 text-error hover:bg-error/10"
            onClick={() => decidir("NAO_ATENDE")}
            disabled={deciding || escalando}
          >
            Confirmar: Não Atende
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto text-xs text-text-tertiary"
            onClick={escalonar}
            disabled={deciding || escalando}
          >
            {escalando ? "..." : "Escalonar"}
          </Button>
        </div>
      </div>
    </>
  );
}

// ── main panel ────────────────────────────────────────────────────────────────

export function CicloAvaliacaoPanel() {
  const { parecer, refreshAll } = useWorkspace();
  const [resumo, setResumo] = useState<CicloResumoResponse | null>(null);
  const [itens, setItens] = useState<ItemRevisaoResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloadingCarta, setDownloadingCarta] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!parecer) return;
    setLoading(true);
    setError("");
    try {
      const [res, its] = await Promise.all([
        patecApi.ciclo.resumo(parecer.id),
        patecApi.ciclo.itensEmReavaliacao(parecer.id),
      ]);
      setResumo(res);
      setItens(its);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar ciclo");
    } finally {
      setLoading(false);
    }
  }, [parecer]);

  useEffect(() => { load(); }, [load]);

  const handleDecidido = useCallback(async () => {
    await Promise.all([load(), refreshAll()]);
  }, [load, refreshAll]);

  const handleDownloadCarta = async () => {
    if (!parecer) return;
    setDownloadingCarta(true);
    try {
      const { blob, filename } = await patecApi.ciclo.downloadCarta(parecer.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao baixar carta");
    } finally {
      setDownloadingCarta(false);
    }
  };

  if (!parecer) return null;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-text-primary">Ciclo de Avaliação</h2>
          <p className="text-xs text-text-tertiary">
            Rodada {resumo?.rodada_atual ?? "—"} · Validação das respostas do fornecedor
          </p>
        </div>
        {resumo?.status_global && (
          <Badge
            variant={resumo.status_global === "CONCLUIDO" ? "success" : resumo.status_global === "AGUARDANDO_FORNECEDOR" ? "warning" : "info"}
            className="text-xs"
          >
            {STATUS_GLOBAL_LABELS[resumo.status_global] ?? resumo.status_global}
          </Badge>
        )}
      </div>

      {/* Resumo dos estados */}
      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : error ? (
        <p className="text-sm text-error">{error}</p>
      ) : resumo && (
        <>
          <div className="rounded-lg border border-border bg-surface p-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              {(["ABERTO", "PENDENTE_FORNECEDOR", "EM_REAVALIACAO", "RESOLVIDO", "ESCALONADO"] as const).map((estado) => {
                const count = resumo.contagem_por_estado.find((c) => c.estado === estado)?.total ?? 0;
                return (
                  <div key={estado} className="text-center">
                    <p className="font-mono text-xl font-bold tabular-nums text-text-primary">{count}</p>
                    <p className="text-[10px] text-text-tertiary">{ESTADO_LABELS[estado]}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Ações globais */}
          <div className="flex flex-wrap gap-3">
            {resumo.tem_pendentes && (
              <Button
                size="sm"
                onClick={handleDownloadCarta}
                loading={downloadingCarta}
              >
                Exportar Carta de Pendências (R{resumo.rodada_atual})
              </Button>
            )}
            {resumo.status_global === "CONCLUIDO" && (
              <div className="flex items-center gap-2 rounded-lg border border-success/30 bg-success-muted px-4 py-2">
                <span className="text-sm font-semibold text-success">
                  Ciclo concluído — todos os itens resolvidos ou escalados.
                </span>
              </div>
            )}
          </div>

          {/* Itens em reavaliação */}
          {itens.length > 0 ? (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-text-primary">
                Aguardando sua decisão ({itens.length})
              </h3>
              {itens.map((item) => (
                <ItemRevisaoCard
                  key={item.id}
                  item={item}
                  parecerId={parecer.id}
                  onDecidido={handleDecidido}
                />
              ))}
            </div>
          ) : resumo.tem_em_reavaliacao ? (
            <p className="text-sm text-text-tertiary">Carregando itens...</p>
          ) : resumo.tem_pendentes ? (
            <div className="rounded-lg border border-border bg-surface p-6 text-center">
              <p className="text-sm text-text-secondary">
                Nenhum item aguarda decisão agora.
              </p>
              <p className="mt-1 text-xs text-text-tertiary">
                Exporte a carta de pendências e aguarde as respostas do fornecedor.
              </p>
            </div>
          ) : resumo.status_global !== "CONCLUIDO" ? (
            <div className="rounded-lg border border-border bg-surface p-6 text-center">
              <p className="text-sm text-text-tertiary">
                Nenhuma ação pendente neste momento.
              </p>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
