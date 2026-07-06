"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ProcessamentoBadge, ParecerGeralBadge } from "./status-badge";
import { ExportButton } from "./export-button";
import { KeyboardHelp } from "./keyboard-help";
import { useConfirm } from "@/components/ui/confirm-dialog";
import {
  useWorkspace,
  STATUS_BG_COLORS,
  STATUS_LABELS,
} from "./workspace-context";

export function WorkspaceTopbar() {
  const {
    parecer,
    statusCounts,
    itens,
    documentos,
    hasResults,
    analyzing,
    showSetupOverride,
    setShowSetupOverride,
    showCiclo,
    setShowCiclo,
    filters,
    setFilters,
    deleteParecer,
  } = useWorkspace();

  const confirmDialog = useConfirm();
  const [deleting, setDeleting] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [showDocs, setShowDocs] = useState(false);
  const docsRef = useRef<HTMLDivElement>(null);

  const engDocs = documentos.filter((d) => d.tipo === "engenharia");
  const fornDocs = documentos.filter((d) => d.tipo === "fornecedor");

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (docsRef.current && !docsRef.current.contains(e.target as Node)) {
        setShowDocs(false);
      }
    }
    if (showDocs) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showDocs]);

  if (!parecer) return null;

  const total = itens.length;

  const handleDelete = async () => {
    const ok = await confirmDialog({
      title: "Excluir parecer?",
      description: "O parecer e todas as suas análises serão removidos permanentemente.",
      confirmLabel: "Excluir parecer",
      variant: "danger",
    });
    if (!ok) return;
    setDeleting(true);
    try {
      await deleteParecer();
    } catch {
      setDeleting(false);
    }
  };

  const toggleFilter = (key: string, value: string) => {
    setFilters({ [key]: filters[key as keyof typeof filters] === value ? "" : value });
  };

  return (
    <>
      <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-edge bg-surface-1 px-4">
        {/* Left: navigation + identity */}
        <div className="flex items-center gap-3">
          <Link href="/dashboard/parecer-tecnico">
            <Button variant="ghost" size="sm" className="h-8 px-2 text-sm">
              ← Voltar
            </Button>
          </Link>
          <div className="hidden items-center gap-2 sm:flex">
            <h1 className="text-sm font-bold text-fg">Parecer {parecer.numero_parecer}</h1>
            <span className="text-xs text-fg-subtle">|</span>
            <span className="text-xs text-fg-muted">{parecer.projeto}</span>
            <span className="text-xs text-fg-subtle">-</span>
            <span className="text-xs text-fg-muted">{parecer.fornecedor}</span>
          </div>
          <ProcessamentoBadge status={parecer.status_processamento} />
          {parecer.parecer_geral && (
            <ParecerGeralBadge status={parecer.parecer_geral} />
          )}
        </div>

        {/* Center: status distribution bar */}
        {hasResults && total > 0 && (
          <div className="hidden items-center gap-3 md:flex">
            <div className="flex h-2.5 w-48 overflow-hidden rounded-full bg-surface-2">
              {(["A", "B", "C", "D", "E"] as const).map((status) => {
                const count = statusCounts[status] || 0;
                if (count === 0) return null;
                const pct = (count / total) * 100;
                return (
                  <div
                    key={status}
                    className={`${STATUS_BG_COLORS[status]} transition-all duration-300`}
                    style={{ width: `${pct}%` }}
                    title={`${STATUS_LABELS[status]}: ${count}`}
                  />
                );
              })}
            </div>
            <span className="text-xs font-mono text-fg-muted">
              {total} itens
            </span>

            {/* Quick filter chips */}
            <div className="flex gap-1">
              {statusCounts.C > 0 && (
                <button
                  onClick={() => toggleFilter("status", "C")}
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
                    filters.status === "C"
                      ? "bg-danger text-white"
                      : "border border-danger/35 text-danger hover:bg-danger-subtle"
                  }`}
                >
                  {statusCounts.C} Rejeitados
                </button>
              )}
              {statusCounts.D > 0 && (
                <button
                  onClick={() => toggleFilter("status", "D")}
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
                    filters.status === "D"
                      ? "bg-fg-subtle text-white"
                      : "border border-edge text-fg-muted hover:bg-surface-2"
                  }`}
                >
                  {statusCounts.D} Info Ausente
                </button>
              )}
            </div>
          </div>
        )}

        {/* Right: actions */}
        <div className="flex items-center gap-1.5">
          {/* Document numbers popover */}
          {documentos.length > 0 && (
            <div className="relative" ref={docsRef}>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 px-2 text-xs text-fg-subtle hover:text-fg"
                onClick={() => setShowDocs(!showDocs)}
                title="Documentos carregados"
              >
                <span className="font-mono tabular-nums">
                  {engDocs.length + fornDocs.length} docs
                </span>
              </Button>
              {showDocs && (
                <div className="absolute right-0 top-full z-50 mt-1 w-80 rounded-lg border border-edge bg-surface-1 p-4 shadow-lg">
                  <p className="mb-2 text-xs font-bold text-fg">
                    Documentos Carregados
                  </p>
                  {engDocs.length > 0 && (
                    <div className="mb-3">
                      <p className="mb-1 text-xs font-semibold text-fg-muted">
                        Engenharia ({engDocs.length})
                      </p>
                      {engDocs.map((d) => (
                        <p key={d.id} className="truncate font-mono text-xs text-fg" title={d.nome_arquivo}>
                          {d.nome_arquivo}
                        </p>
                      ))}
                    </div>
                  )}
                  {fornDocs.length > 0 && (
                    <div>
                      <p className="mb-1 text-xs font-semibold text-fg-muted">
                        Fornecedor ({fornDocs.length})
                      </p>
                      {fornDocs.map((d) => (
                        <p key={d.id} className="truncate font-mono text-xs text-fg" title={d.nome_arquivo}>
                          {d.nome_arquivo}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 text-fg-subtle hover:text-fg"
            onClick={() => setShowHelp(true)}
            title="Atalhos de teclado (?)"
          >
            ?
          </Button>
          {hasResults && !analyzing && !showCiclo && (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2 text-xs text-fg-muted hover:text-fg"
              onClick={() => setShowSetupOverride(!showSetupOverride)}
              title={showSetupOverride ? "Voltar aos resultados" : "Modificar documentos ou reanalisar"}
            >
              {showSetupOverride ? "← Resultados" : "Reanalisar"}
            </Button>
          )}
          {hasResults && !analyzing && (
            <Button
              variant={showCiclo ? "secondary" : "ghost"}
              size="sm"
              className="h-8 px-2 text-xs"
              onClick={() => { setShowCiclo(!showCiclo); setShowSetupOverride(false); }}
              title="Ciclo iterativo de avaliação"
            >
              {showCiclo ? "← Parecer" : "Ciclo"}
            </Button>
          )}
          {hasResults && !showSetupOverride && !showCiclo && <ExportButton parecerId={parecer.id} />}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 text-xs text-fg-subtle hover:text-danger-text"
            onClick={handleDelete}
            disabled={deleting}
          >
            {deleting ? "..." : "Excluir"}
          </Button>
        </div>
      </header>

      <KeyboardHelp open={showHelp} onOpenChange={setShowHelp} />
    </>
  );
}
