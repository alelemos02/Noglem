"use client";

/**
 * ConversationScreen — a tela do caso: header mínimo + PhaseLine + Thread + InputBar.
 */

import Link from "next/link";
import { Spinner } from "@/components/ui/spinner";
import { useConversation } from "./conversation-provider";
import { PhaseLine } from "./phase-line";
import { Thread } from "./thread";
import { InputBar } from "./input-bar";
import { DataPanel } from "./data-panel";
import { CicloTablePanel } from "./widgets/ciclo-table-panel";

export function ConversationScreen() {
  const { snapshot, loading, notFound } = useConversation();

  if (loading) {
    return (
      <div className="flex h-full min-h-[60vh] items-center justify-center bg-canvas">
        <div className="flex items-center gap-3 text-fg-subtle">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent font-sans text-sm font-bold text-accent-fg">
            J
          </div>
          <Spinner size="sm" />
          <span className="text-sm">JulIA está abrindo o caso...</span>
        </div>
      </div>
    );
  }

  if (notFound || !snapshot) {
    return (
      <div className="flex h-full min-h-[60vh] flex-col items-center justify-center gap-3 bg-canvas">
        <p className="text-lg text-fg-muted">Parecer não encontrado</p>
        <p className="text-sm text-fg-subtle">
          Este caso pode ter sido excluído ou o link está incorreto.
        </p>
        <Link
          href="/dashboard/parecer-tecnico"
          className="mt-2 text-sm text-accent hover:underline"
        >
          ← Voltar para a lista
        </Link>
      </div>
    );
  }

  const { parecer } = snapshot;

  return (
    <div className="flex h-full flex-col bg-canvas">
      {/* Header mínimo */}
      <header className="border-b border-edge">
        <div className="mx-auto w-full max-w-4xl px-4 pb-2 pt-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <Link
                href="/dashboard/parecer-tecnico"
                className="shrink-0 text-sm text-fg-subtle transition-colors hover:text-fg"
                title="Voltar para a lista"
              >
                ←
              </Link>
              <h1 className="truncate font-sans text-sm font-semibold text-fg">
                {parecer.numero_parecer}
              </h1>
              <span className="truncate text-xs text-fg-subtle">
                {parecer.projeto} · {parecer.fornecedor}
              </span>
            </div>
          </div>
          <div className="mt-3">
            <PhaseLine fase={parecer.fase_caso} />
          </div>
        </div>
      </header>

      <Thread />
      <InputBar />
      <DataPanel />
      <CicloTablePanel />
    </div>
  );
}
