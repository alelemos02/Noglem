"use client";

/**
 * RastreabilidadeWidget — cobertura requisito -> item, invocado por comando
 * ("rastreabilidade" / "ver cobertura"). Mostra, para cada requisito aprovado,
 * qual item da análise o cobre e destaca os que precisam de revisão manual
 * (requisito sem item real / coberto só por placeholder da reconciliação).
 */

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { patecApi } from "@/lib/patec-api";
import type { RastreabilidadeResponse } from "@/lib/patec-api";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";

const STATUS_VARIANT: Record<
  string,
  "success" | "warning" | "error" | "secondary" | "info"
> = {
  A: "success",
  B: "warning",
  C: "error",
  D: "secondary",
  E: "info",
};

export function RastreabilidadeWidget() {
  const { parecerId } = useConversation();
  const [data, setData] = useState<RastreabilidadeResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    patecApi.itens
      .rastreabilidade(parecerId)
      .then(setData)
      .catch(() => setError("Não consegui carregar a rastreabilidade."));
  }, [parecerId]);

  if (error) {
    return (
      <WidgetFrame>
        <p className="text-sm text-danger-text">{error}</p>
      </WidgetFrame>
    );
  }

  if (!data) {
    return (
      <WidgetFrame>
        <p className="text-sm text-fg-subtle">Carregando rastreabilidade…</p>
      </WidgetFrame>
    );
  }

  return (
    <WidgetFrame>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-fg">
          Rastreabilidade — {data.total_requisitos} requisitos aprovados
        </span>
        <Badge variant="success">{data.cobertos} cobertos</Badge>
        {data.a_revisar > 0 && (
          <Badge variant="warning">{data.a_revisar} a revisar</Badge>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-edge text-left text-xs text-fg-subtle">
              <th className="py-1.5 pr-2">Req.</th>
              <th className="py-1.5 pr-2">Requisito</th>
              <th className="py-1.5 pr-2">Item</th>
              <th className="py-1.5">Cobertura</th>
            </tr>
          </thead>
          <tbody>
            {data.linhas.map((l) => (
              <tr
                key={l.requisito_numero}
                className={`border-b border-edge/50 ${
                  l.cobertura === "revisar" ? "bg-warning-subtle/40" : ""
                }`}
              >
                <td className="py-1.5 pr-2 align-top font-mono text-fg-muted">
                  {l.requisito_numero}
                </td>
                <td className="py-1.5 pr-2 align-top">
                  <span className="text-fg">{l.requisito_descricao}</span>
                  {l.referencia_engenharia && (
                    <span className="ml-1 text-xs text-fg-subtle">
                      ({l.referencia_engenharia})
                    </span>
                  )}
                </td>
                <td className="py-1.5 pr-2 align-top">
                  {l.item_numero != null ? (
                    <span className="flex items-center gap-1.5">
                      <span className="font-mono text-fg-muted">
                        #{l.item_numero}
                      </span>
                      {l.item_status && (
                        <Badge variant={STATUS_VARIANT[l.item_status] ?? "secondary"}>
                          {l.item_status}
                        </Badge>
                      )}
                    </span>
                  ) : (
                    <span className="text-fg-subtle">—</span>
                  )}
                </td>
                <td className="py-1.5 align-top">
                  {l.cobertura === "coberto" ? (
                    <span className="text-success-text">✓ coberto</span>
                  ) : (
                    <span className="text-warning-text">⚠ revisar</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.a_revisar > 0 && (
        <p className="mt-3 text-xs text-fg-subtle">
          Linhas destacadas são requisitos aprovados que a análise automática não
          cobriu (possível truncamento/omissão do modelo). Revise-os manualmente.
        </p>
      )}
    </WidgetFrame>
  );
}
