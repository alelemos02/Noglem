"use client";

import { useState, useEffect } from "react";
import { patecApi, type EstimativaCustoResponse } from "@/lib/patec-api";

export function EstimativaCusto({ parecerId }: { parecerId: string }) {
  const [estimativa, setEstimativa] = useState<EstimativaCustoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(true);

  useEffect(() => {
    patecApi.estimativa.getCusto(parecerId)
      .then(setEstimativa)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [parecerId]);

  if (loading || !estimativa) return null;

  return (
    <div className="rounded-lg border border-info/30 bg-info-muted p-4">
      <button onClick={() => setCollapsed(!collapsed)} className="flex w-full items-center justify-between text-sm font-medium text-info-text">
        Estimativa de custo
        <span className="text-xs">{collapsed ? "▼" : "▲"}</span>
      </button>
      {!collapsed && (
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-text-secondary">
          <span>Caracteres:</span><span>{estimativa.total_caracteres.toLocaleString()}</span>
          <span>Tokens entrada:</span><span>{estimativa.tokens_estimados_entrada.toLocaleString()}</span>
          <span>Tokens saída:</span><span>{estimativa.tokens_estimados_saida.toLocaleString()}</span>
          <span>Chamadas API:</span><span>{estimativa.num_chamadas_api}</span>
          <span>Modelo:</span><span>{estimativa.modelo}</span>
          <span>Custo USD:</span><span className="font-semibold">${estimativa.custo_estimado_usd.toFixed(4)}</span>
          <span>Custo BRL:</span><span className="font-semibold">R${estimativa.custo_estimado_brl.toFixed(4)}</span>
          {estimativa.aviso && <><span className="col-span-2 mt-1 text-warning-text">{estimativa.aviso}</span></>}
        </div>
      )}
    </div>
  );
}
