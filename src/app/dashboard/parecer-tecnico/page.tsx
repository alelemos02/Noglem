"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { patecApi, type ParecerResponse } from "@/lib/patec-api";
import { ProcessamentoBadge, ParecerGeralBadge } from "@/components/parecer-tecnico/status-badge";

const STATUS_BAR_COLORS: Record<string, string> = {
  A: "bg-green-500",
  B: "bg-yellow-500",
  C: "bg-red-500",
  D: "bg-gray-500",
  E: "bg-blue-500",
};

const PARECER_BORDER_COLORS: Record<string, string> = {
  APROVADO: "border-l-green-500",
  APROVADO_COM_COMENTARIOS: "border-l-yellow-500",
  REJEITADO: "border-l-red-500",
};

const SEGMENTS = [
  { key: "concluidos", label: "Concluídos", color: "bg-green-500", filter: (p: ParecerResponse) => p.status_processamento === "concluido" },
  { key: "processando", label: "Processando", color: "bg-blue-500", filter: (p: ParecerResponse) => p.status_processamento === "processando" },
  { key: "pendentes", label: "Pendentes", color: "bg-yellow-500", filter: (p: ParecerResponse) => p.status_processamento === "pendente" },
  { key: "erro", label: "Erro", color: "bg-red-500", filter: (p: ParecerResponse) => p.status_processamento === "erro" },
] as const;

export default function ParecerTecnicoPage() {
  const [pareceres, setPareceres] = useState<ParecerResponse[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [deletingSelected, setDeletingSelected] = useState(false);
  const [error, setError] = useState("");

  const loadPareceres = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await patecApi.pareceres.list({ projeto: search || undefined });
      setPareceres(data.items);
      setSelectedIds((prev) => {
        const next = new Set<string>();
        for (const item of data.items) {
          if (prev.has(item.id)) next.add(item.id);
        }
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar pareceres");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { loadPareceres(); }, [loadPareceres]);

  useEffect(() => {
    const handleFocus = () => loadPareceres();
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [loadPareceres]);

  const selectedCount = selectedIds.size;

  const toggleSelectOne = (id: string, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  };

  const handleDeleteSelected = async () => {
    if (selectedCount === 0) return;
    if (!confirm(`Excluir ${selectedCount} parecer(es) selecionado(s)?`)) return;
    setDeletingSelected(true);
    setError("");
    const ids = Array.from(selectedIds);
    const results = await Promise.allSettled(ids.map((id) => patecApi.pareceres.delete(id)));
    const failed = results.filter((r) => r.status === "rejected").length;
    if (failed > 0) setError(`${failed} parecer(es) não puderam ser excluídos.`);
    if (ids.length - failed > 0) await loadPareceres();
    setSelectedIds(new Set());
    setDeletingSelected(false);
  };

  const total = pareceres.length;
  const counts = SEGMENTS.map((seg) => ({
    ...seg,
    count: pareceres.filter(seg.filter).length,
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-heading text-2xl font-bold text-text-primary">
          Parecer Técnico
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          Análise e comparação de documentação da engenharia versus documentos dos fornecedores
        </p>
      </div>

      {/* Summary bar */}
      {total > 0 && (
        <div className="space-y-2">
          <div className="flex h-3 overflow-hidden rounded-full bg-surface">
            {counts.map((seg) =>
              seg.count > 0 ? (
                <div
                  key={seg.key}
                  className={`${seg.color} transition-all duration-300`}
                  style={{ width: `${(seg.count / total) * 100}%` }}
                  title={`${seg.label}: ${seg.count}`}
                />
              ) : null
            )}
          </div>
          <div className="flex flex-wrap gap-4">
            {counts.map((seg) =>
              seg.count > 0 ? (
                <div key={seg.key} className="flex items-center gap-1.5">
                  <div className={`h-2.5 w-2.5 rounded-full ${seg.color}`} />
                  <span className="text-xs text-text-secondary">
                    {seg.label}: <span className="font-semibold">{seg.count}</span>
                  </span>
                </div>
              ) : null
            )}
            <span className="text-xs text-text-tertiary">Total: {total}</span>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between gap-4">
        <Input
          placeholder="Buscar por projeto..."
          className="max-w-sm"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="flex items-center gap-2">
          {selectedCount > 0 && (
            <Button
              variant="danger"
              onClick={handleDeleteSelected}
              disabled={deletingSelected}
            >
              {deletingSelected ? "Excluindo..." : `Excluir (${selectedCount})`}
            </Button>
          )}
          <Link href="/dashboard/parecer-tecnico/novo">
            <Button variant="primary">Novo Parecer</Button>
          </Link>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-error-muted p-3 text-sm text-error-text">
          {error}
          <Button variant="ghost" size="sm" className="ml-2" onClick={loadPareceres}>
            Tentar novamente
          </Button>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="py-12 text-center text-text-tertiary">Carregando...</div>
      ) : pareceres.length === 0 ? (
        <div className="py-12 text-center text-text-tertiary">
          Nenhum parecer encontrado
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {pareceres.map((p) => {
            const borderColor = (p.parecer_geral && PARECER_BORDER_COLORS[p.parecer_geral]) || "border-l-border";
            const itemCounts = [
              { status: "A", count: p.total_aprovados },
              { status: "B", count: p.total_aprovados_comentarios },
              { status: "C", count: p.total_rejeitados },
              { status: "D", count: p.total_info_ausente },
              { status: "E", count: p.total_itens_adicionais },
            ];
            const selected = selectedIds.has(p.id);

            return (
              <div
                key={p.id}
                className={`group relative rounded-lg border border-l-4 bg-surface p-4 transition-all hover:shadow-md hover:border-border-hover ${borderColor} ${
                  selected ? "ring-2 ring-info" : ""
                }`}
              >
                <div className="absolute top-3 right-3">
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={(e) => toggleSelectOne(p.id, e.target.checked)}
                    className="rounded border-border opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100"
                    style={selected ? { opacity: 1 } : undefined}
                  />
                </div>

                <Link href={`/dashboard/parecer-tecnico/${p.id}`} className="block space-y-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-info-text">{p.numero_parecer}</span>
                      <ProcessamentoBadge status={p.status_processamento} />
                    </div>
                    <p className="mt-0.5 text-sm font-medium text-text-primary">{p.projeto}</p>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-text-secondary">
                    <span>{p.fornecedor}</span>
                    <span>Rev. {p.revisao}</span>
                    <span>{new Date(p.criado_em).toLocaleDateString("pt-BR")}</span>
                  </div>

                  {p.total_itens > 0 && (
                    <div className="space-y-1">
                      <div className="flex h-1.5 overflow-hidden rounded-full bg-surface-hover">
                        {itemCounts.map((ic) =>
                          ic.count > 0 ? (
                            <div
                              key={ic.status}
                              className={`${STATUS_BAR_COLORS[ic.status]} transition-all`}
                              style={{ width: `${(ic.count / p.total_itens) * 100}%` }}
                            />
                          ) : null
                        )}
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-text-tertiary">{p.total_itens} itens</span>
                        {p.parecer_geral && <ParecerGeralBadge status={p.parecer_geral} />}
                      </div>
                    </div>
                  )}
                </Link>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
