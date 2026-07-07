"use client";

/**
 * AnaliseResultadoWidget — resumo da análise R1 (chips A–E + parecer geral +
 * lista expansível de itens) e o gate W2 "Iniciar ciclo com o fornecedor".
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";

export const STATUS_INFO: Record<
  string,
  { label: string; chip: string }
> = {
  A: { label: "Aprovado", chip: "bg-success-subtle text-success-text" },
  B: { label: "Aprov. c/ comentários", chip: "bg-warning-subtle text-warning-text" },
  C: { label: "Rejeitado", chip: "bg-danger-subtle text-danger-text" },
  D: { label: "Info ausente", chip: "bg-surface-3 text-fg-muted" },
  E: { label: "Adicional", chip: "bg-info-subtle text-info-text" },
};

export function AnaliseResultadoWidget() {
  const { snapshot, iniciarCiclo, setShowDataPanel } = useConversation();
  const [starting, setStarting] = useState(false);

  if (!snapshot) return null;
  const { parecer, itens } = snapshot;

  const counts: Array<{ status: string; total: number }> = [
    { status: "A", total: parecer.total_aprovados },
    { status: "B", total: parecer.total_aprovados_comentarios },
    { status: "C", total: parecer.total_rejeitados },
    { status: "D", total: parecer.total_info_ausente },
    { status: "E", total: parecer.total_itens_adicionais },
  ];

  const handleIniciar = async () => {
    setStarting(true);
    try {
      await iniciarCiclo();
    } catch {
      // erro exibido pelo provider
    } finally {
      setStarting(false);
    }
  };

  return (
    <WidgetFrame title="Resultado da análise">
      {/* Chips A–E */}
      <div className="flex flex-wrap gap-2">
        {counts.map(({ status, total }) => (
          <span
            key={status}
            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium ${STATUS_INFO[status].chip}`}
          >
            <span className="font-mono font-bold">{status}</span>
            {STATUS_INFO[status].label}
            <span className="font-mono tabular-nums">{total}</span>
          </span>
        ))}
      </div>

      {/* Parecer geral */}
      {parecer.parecer_geral && (
        <p className="mt-3 rounded-lg bg-canvas p-3 text-sm text-fg-muted">
          {parecer.parecer_geral}
        </p>
      )}

      {/* Acesso destacado à tabela completa da análise (abre o pop-up grande) */}
      <button
        onClick={() => setShowDataPanel(true)}
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
            Ver a tabela completa da análise
          </span>
        </span>
        <span className="shrink-0 text-xs text-fg-subtle">
          {itens.length} itens →
        </span>
      </button>

      {/* W2 — iniciar ciclo */}
      <div className="mt-4 flex justify-end">
        <Button onClick={handleIniciar} loading={starting} disabled={starting}>
          Iniciar ciclo com o fornecedor
        </Button>
      </div>
    </WidgetFrame>
  );
}
