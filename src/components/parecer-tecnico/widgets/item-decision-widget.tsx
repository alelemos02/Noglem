"use client";

/**
 * ItemDecisionWidget — passo de decisão W4. Em vez do antigo carrossel "um item
 * por vez", é um GATEWAY: a JulIA avisa quantos itens o fornecedor respondeu e o
 * engenheiro abre a TABELA completa (CicloTablePanel) para revisar e decidir tudo
 * de uma vez. HistoricoInline continua aqui (usado pelo items-browser).
 */

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { patecApi, type RodadaAvaliacaoResponse } from "@/lib/patec-api";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";

const VEREDITO_LABELS: Record<string, string> = {
  ATENDE: "Atende",
  PARCIAL: "Parcial",
  NAO_ATENDE: "Não atende",
};

const DECISAO_LABELS: Record<string, string> = {
  ACEITAR: "Aceitar",
  ESCLARECER: "Esclarecer",
  REJEITAR: "Rejeitar",
  REPROVAR_CASO: "Reprovar caso",
};

function vereditoVariant(
  v: string | null
): "success" | "warning" | "error" | "secondary" {
  if (v === "ATENDE") return "success";
  if (v === "PARCIAL") return "warning";
  if (v === "NAO_ATENDE") return "error";
  return "secondary";
}

export function HistoricoInline({ itemId }: { itemId: string }) {
  const { parecerId } = useConversation();
  const [rodadas, setRodadas] = useState<RodadaAvaliacaoResponse[] | null>(null);

  useEffect(() => {
    patecApi.ciclo
      .historico(parecerId, itemId)
      .then(setRodadas)
      .catch(() => setRodadas([]));
  }, [parecerId, itemId]);

  if (!rodadas) {
    return <p className="text-xs text-fg-subtle">Carregando histórico...</p>;
  }
  if (rodadas.length === 0) {
    return <p className="text-xs text-fg-subtle">Nenhuma rodada registrada.</p>;
  }

  return (
    <ol className="relative space-y-4 border-l border-edge pl-5">
      {rodadas.map((r) => (
        <li key={r.id} className="relative">
          <span className="absolute -left-[1.4rem] top-1 h-2.5 w-2.5 rounded-full border-2 border-accent bg-surface-1" />
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-bold text-fg">
                Rodada {r.numero_rodada}
              </span>
              {r.veredito_ia && (
                <Badge variant={vereditoVariant(r.veredito_ia)} className="text-[10px]">
                  LLM: {VEREDITO_LABELS[r.veredito_ia] ?? r.veredito_ia}
                </Badge>
              )}
              {r.decisao_humana && (
                <Badge
                  variant={vereditoVariant(
                    r.decisao_humana === "ACEITAR"
                      ? "ATENDE"
                      : r.decisao_humana === "ESCLARECER"
                        ? "PARCIAL"
                        : "NAO_ATENDE"
                  )}
                  dot
                  className="text-[10px]"
                >
                  Eng.: {DECISAO_LABELS[r.decisao_humana] ?? r.decisao_humana}
                </Badge>
              )}
            </div>
            {r.conteudo && (
              <p className="rounded bg-canvas px-2 py-1 text-xs text-fg-muted">
                {r.conteudo}
              </p>
            )}
            {r.justificativa_ia && (
              <p className="text-xs text-fg-subtle">{r.justificativa_ia}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function ItemDecisionWidget() {
  const { snapshot, setShowCicloPanel } = useConversation();
  const total = snapshot?.itensReavaliacao.length ?? 0;
  if (total === 0) return null;

  return (
    <WidgetFrame>
      <p className="text-sm text-fg-muted">
        O fornecedor respondeu{" "}
        <strong className="text-fg">
          {total} {total === 1 ? "item" : "itens"}
        </strong>
        . Revise a resposta e a minha avaliação de cada um na tabela e dê a palavra
        final.
      </p>
      <button
        onClick={() => setShowCicloPanel(true)}
        className="mt-3 flex w-full items-center justify-between gap-3 rounded-lg border border-edge bg-canvas px-4 py-3 text-left transition-colors hover:border-accent hover:bg-surface-2"
      >
        <span className="flex items-center gap-2.5">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            className="shrink-0 text-accent"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M3 9h18M3 15h18M9 3v18" />
          </svg>
          <span className="text-sm font-medium text-fg">
            Ver respostas e decidir
          </span>
        </span>
        <span className="shrink-0 text-xs text-fg-subtle">
          {total} pendente{total === 1 ? "" : "s"} →
        </span>
      </button>
    </WidgetFrame>
  );
}
