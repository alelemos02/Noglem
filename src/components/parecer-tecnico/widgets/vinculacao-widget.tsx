"use client";

/**
 * VinculacaoWidget — revisão da vinculação sugerida pela LLM (bloco 23 → W3),
 * inline na conversa. Adaptado de vinculacao-review.tsx.
 */

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  patecApi,
  type RodadaDetalheResponse,
  type VinculoResponse,
} from "@/lib/patec-api";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";

const CONFIANCA_VARIANT: Record<string, "success" | "warning" | "error"> = {
  ALTA: "success",
  MEDIA: "warning",
  BAIXA: "error",
};

export function VinculacaoWidget({ rodadaId }: { rodadaId: string }) {
  const { parecerId, snapshot, corrigirVinculo, confirmarVinculacao } =
    useConversation();
  const [detalhe, setDetalhe] = useState<RodadaDetalheResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirmando, setConfirmando] = useState(false);

  const itensAbertos =
    snapshot?.itens.filter((i) => i.estado === "PENDENTE_FORNECEDOR") ?? [];

  const load = useCallback(async () => {
    try {
      const d = await patecApi.ciclo.detalharRodada(parecerId, rodadaId);
      setDetalhe(d);
    } catch {
      // erro transitório; o widget re-renderiza no próximo refresh
    } finally {
      setLoading(false);
    }
  }, [parecerId, rodadaId]);

  useEffect(() => {
    // fetch-on-mount: todo setState do load ocorre após await
     
    void load();
  }, [load]);

  const corrigir = async (vinculo: VinculoResponse, itemNumero: number) => {
    try {
      await corrigirVinculo(rodadaId, vinculo.id, { item_numero: itemNumero });
      await load();
    } catch {
      // erro exibido pelo provider
    }
  };

  const remover = async (vinculo: VinculoResponse) => {
    try {
      await corrigirVinculo(rodadaId, vinculo.id, { remover: true });
      await load();
    } catch {
      // erro exibido pelo provider
    }
  };

  const confirmar = async () => {
    setConfirmando(true);
    try {
      await confirmarVinculacao(rodadaId);
    } catch {
      // erro exibido pelo provider
    } finally {
      setConfirmando(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  if (!detalhe) return null;

  return (
    <WidgetFrame
      title={`Vinculação sugerida — ${detalhe.vinculos.length} vínculo(s)`}
    >
      {detalhe.vinculos.length === 0 ? (
        <p className="text-sm text-fg-muted">
          Não encontrei correspondências na resposta. Verifique o material
          enviado — você pode remover esta rodada e tentar de novo.
        </p>
      ) : (
        <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
          {detalhe.vinculos.map((v) => (
            <div
              key={v.id}
              className="rounded-lg border border-edge bg-canvas p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs font-bold text-fg-subtle">
                  → Item #{v.item_numero}
                </span>
                <span className="truncate text-xs text-fg-muted">
                  {v.item_descricao.slice(0, 80)}
                </span>
                {v.confianca && (
                  <Badge
                    variant={CONFIANCA_VARIANT[v.confianca]}
                    className="text-[10px]"
                    dot
                  >
                    Confiança {v.confianca}
                  </Badge>
                )}
                {v.metodo && v.metodo !== "LLM" && (
                  <Badge variant="secondary" className="text-[10px]">
                    {v.metodo === "MANUAL" ? "Corrigido" : "Determinístico"}
                  </Badge>
                )}
              </div>
              {v.trecho ? (
                <p className="mt-2 rounded bg-surface-1 px-2 py-1.5 text-xs text-fg">
                  “{v.trecho}”
                </p>
              ) : (
                <p className="mt-2 text-xs italic text-fg-subtle">
                  Proposta revisada completa (sem trecho específico)
                </p>
              )}
              <div className="mt-2 flex items-center gap-2">
                <label className="text-[11px] text-fg-subtle">
                  Reapontar para:
                </label>
                <select
                  className="rounded-md border border-edge bg-surface-1 px-2 py-1 text-xs text-fg outline-none focus:border-accent"
                  value={v.item_numero}
                  onChange={(e) => {
                    const numero = parseInt(e.target.value, 10);
                    if (numero !== v.item_numero) corrigir(v, numero);
                  }}
                >
                  {[
                    v.item_numero,
                    ...itensAbertos
                      .map((i) => i.numero)
                      .filter((n) => n !== v.item_numero),
                  ].map((n) => (
                    <option key={n} value={n}>
                      Item #{n}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => remover(v)}
                  className="ml-auto rounded px-1.5 py-0.5 text-xs text-danger/80 hover:bg-danger-subtle hover:text-danger"
                >
                  Remover vínculo
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 flex justify-end">
        <Button
          onClick={confirmar}
          disabled={detalhe.vinculos.length === 0 || confirmando}
          loading={confirmando}
        >
          Confirmar vínculos e avaliar
        </Button>
      </div>
    </WidgetFrame>
  );
}
