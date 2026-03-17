"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ProcessamentoBadge, ParecerGeralBadge } from "./status-badge";
import { ExportButton } from "./export-button";
import { KeyboardHelp } from "./keyboard-help";
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
    filters,
    setFilters,
    deleteParecer,
  } = useWorkspace();

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
    if (!confirm("Tem certeza que deseja excluir este parecer?")) return;
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
      <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-border bg-surface px-4">
        {/* Left: navigation + identity */}
        <div className="flex items-center gap-3">
          <Link href="/dashboard/parecer-tecnico">
            <Button variant="ghost" size="sm" className="h-8 px-2 text-sm">
              ← Voltar
            </Button>
          </Link>
          <div className="hidden items-center gap-2 sm:flex">
            <h1 className="text-sm font-bold text-text-primary">Parecer {parecer.numero_parecer}</h1>
            <span className="text-xs text-text-tertiary">|</span>
            <span className="text-xs text-text-secondary">{parecer.projeto}</span>
            <span className="text-xs text-text-tertiary">-</span>
            <span className="text-xs text-text-secondary">{parecer.fornecedor}</span>
          </div>
          <ProcessamentoBadge status={parecer.status_processamento} />
          {parecer.parecer_geral && (
            <ParecerGeralBadge status={parecer.parecer_geral} />
          )}
        </div>

        {/* Center: status distribution bar */}
        {hasResults && total > 0 && (
          <div className="hidden items-center gap-3 md:flex">
            <div className="flex h-2.5 w-48 overflow-hidden rounded-full bg-surface-hover">
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
            <span className="text-xs font-mono text-text-secondary">
              {total} itens
            </span>

            {/* Quick filter chips */}
            <div className="flex gap-1">
              {statusCounts.C > 0 && (
                <button
                  onClick={() => toggleFilter("status", "C")}
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
                    filters.status === "C"
                      ? "bg-red-600 text-white"
                      : "border border-red-700/50 text-red-400 hover:bg-red-900/30"
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
                      ? "bg-gray-600 text-white"
                      : "border border-border text-text-secondary hover:bg-surface-hover"
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
                className="h-8 px-2 text-xs text-text-tertiary hover:text-text-primary"
                onClick={() => setShowDocs(!showDocs)}
                title="Documentos carregados"
              >
                <span className="font-mono tabular-nums">
                  {engDocs.length + fornDocs.length} docs
                </span>
              </Button>
              {showDocs && (
                <div className="absolute right-0 top-full z-50 mt-1 w-80 rounded-lg border border-border bg-surface p-4 shadow-lg">
                  <p className="mb-2 text-xs font-bold text-text-primary">
                    Documentos Carregados
                  </p>
                  {engDocs.length > 0 && (
                    <div className="mb-3">
                      <p className="mb-1 text-xs font-semibold text-text-secondary">
                        Engenharia ({engDocs.length})
                      </p>
                      {engDocs.map((d) => (
                        <p key={d.id} className="truncate font-mono text-xs text-text-primary" title={d.nome_arquivo}>
                          {d.nome_arquivo}
                        </p>
                      ))}
                    </div>
                  )}
                  {fornDocs.length > 0 && (
                    <div>
                      <p className="mb-1 text-xs font-semibold text-text-secondary">
                        Fornecedor ({fornDocs.length})
                      </p>
                      {fornDocs.map((d) => (
                        <p key={d.id} className="truncate font-mono text-xs text-text-primary" title={d.nome_arquivo}>
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
            className="h-8 w-8 p-0 text-text-tertiary hover:text-text-primary"
            onClick={() => setShowHelp(true)}
            title="Atalhos de teclado (?)"
          >
            ?
          </Button>
          {hasResults && <ExportButton parecerId={parecer.id} />}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 text-xs text-text-tertiary hover:text-error-text"
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
