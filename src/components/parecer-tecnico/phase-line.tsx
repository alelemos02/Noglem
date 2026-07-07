"use client";

/**
 * PhaseLine — indicador sutil de fase do caso: linha fina com 6 segmentos.
 * Substitui o antigo case-stepper sem roubar atenção da conversa.
 */

import type { FaseCaso } from "@/lib/patec-api";

const FASES: Array<{ id: FaseCaso; label: string; shortLabel: string }> = [
  { id: "SETUP", label: "Setup", shortLabel: "Setup" },
  { id: "REQUISITOS", label: "Requisitos", shortLabel: "Req." },
  { id: "ANALISE", label: "Análise", shortLabel: "Análise" },
  {
    id: "CICLO_FORNECEDOR",
    label: "Ciclo Fornecedor",
    shortLabel: "Ciclo",
  },
  {
    id: "VERIFICACAO_FINAL",
    label: "Verificação Final",
    shortLabel: "Verif.",
  },
  { id: "FECHADO", label: "Fechado", shortLabel: "Fechado" },
];

export function PhaseLine({ fase }: { fase: FaseCaso }) {
  const currentIdx = FASES.findIndex((f) => f.id === fase);

  return (
    <div
      className="grid grid-cols-6 gap-1"
      title={FASES[currentIdx]?.label}
      aria-label={`Fase atual: ${FASES[currentIdx]?.label ?? fase}`}
    >
      {FASES.map((f, idx) => (
        <div
          key={f.id}
          title={f.label}
          className="min-w-0"
        >
          <div
            className={`h-[3px] rounded-full transition-colors ${
              idx < currentIdx
                ? "bg-accent/40"
                : idx === currentIdx
                  ? "bg-accent"
                  : "bg-edge"
            }`}
          />
          <div
            className={`mt-1 truncate text-center text-[10px] font-medium leading-none transition-colors ${
              idx === currentIdx
                ? "text-accent"
                : idx < currentIdx
                  ? "text-fg-muted"
                  : "text-fg-subtle"
            }`}
          >
            <span className="md:hidden">{f.shortLabel}</span>
            <span className="hidden md:inline">{f.label}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

export function faseLabel(fase: FaseCaso): string {
  return FASES.find((f) => f.id === fase)?.label ?? fase;
}
