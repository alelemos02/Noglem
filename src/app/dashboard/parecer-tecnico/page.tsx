"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { FileSearch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { patecApi, type ParecerResponse } from "@/lib/patec-api";
import { ProcessamentoBadge, ParecerGeralBadge } from "@/components/parecer-tecnico/status-badge";
import { faseLabel } from "@/components/parecer-tecnico/phase-line";
import { desfechoLabel } from "@/components/parecer-tecnico/script";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { PageHeader } from "@/components/ui/page-header";
import { LoadingBlock } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { Alert } from "@/components/ui/alert";
import { toast } from "@/components/ui/toast";
import { useConfirm } from "@/components/ui/confirm-dialog";

const DISCIPLINA_LABELS: Record<string, string> = {
  instrumentacao: "Instrumentação",
  eletrico: "Elétrico",
  civil: "Civil",
  mecanico: "Mecânico",
  tubulacao: "Tubulação",
};

const STATUS_BAR_COLORS: Record<string, string> = {
  A: "bg-success",
  B: "bg-warning",
  C: "bg-danger",
  D: "bg-fg-subtle",
  E: "bg-info",
};

const PARECER_BORDER_COLORS: Record<string, string> = {
  APROVADO: "border-l-success",
  APROVADO_COM_COMENTARIOS: "border-l-warning",
  REJEITADO: "border-l-danger",
};

const DESFECHO_VARIANT: Record<string, "success" | "warning" | "error"> = {
  APROVADO: "success",
  COM_PENDENCIA: "warning",
  REPROVADO: "error",
};

const SEGMENTS = [
  { key: "concluidos", label: "Concluídos", color: "bg-success", filter: (p: ParecerResponse) => p.status_processamento === "concluido" },
  { key: "processando", label: "Processando", color: "bg-info", filter: (p: ParecerResponse) => p.status_processamento === "processando" },
  { key: "pendentes", label: "Pendentes", color: "bg-warning", filter: (p: ParecerResponse) => p.status_processamento === "pendente" },
  { key: "erro", label: "Erro", color: "bg-danger", filter: (p: ParecerResponse) => p.status_processamento === "erro" },
] as const;

export default function ParecerTecnicoPage() {
  const confirm = useConfirm();
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
    const ok = await confirm({
      title: `Excluir ${selectedCount} parecer(es)?`,
      description: "Os pareceres selecionados e suas análises serão removidos permanentemente.",
      confirmLabel: "Excluir",
      variant: "danger",
    });
    if (!ok) return;
    setDeletingSelected(true);
    setError("");
    const ids = Array.from(selectedIds);
    const results = await Promise.allSettled(ids.map((id) => patecApi.pareceres.delete(id)));
    const failed = results.filter((r) => r.status === "rejected").length;
    if (failed > 0) setError(`${failed} parecer(es) não puderam ser excluídos.`);
    if (ids.length - failed > 0) {
      toast.success(`${ids.length - failed} parecer(es) excluído(s)`);
      await loadPareceres();
    }
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
      <PageHeader tool="parecer-tecnico" />

      {/* Summary bar */}
      {total > 0 && (
        <div className="space-y-2">
          <div className="flex h-2 overflow-hidden rounded-sm bg-surface-2">
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
                  <div className={`h-2 w-2 rounded-full ${seg.color}`} />
                  <span className="text-xs text-fg-muted">
                    {seg.label}: <span className="font-mono font-medium tabular-nums">{seg.count}</span>
                  </span>
                </div>
              ) : null
            )}
            <span className="font-mono text-xs tabular-nums text-fg-subtle">Total: {total}</span>
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
              loading={deletingSelected}
            >
              {deletingSelected ? "Excluindo..." : `Excluir (${selectedCount})`}
            </Button>
          )}
          <Link href="/dashboard/parecer-tecnico/novo">
            <Button variant="primary">Novo parecer</Button>
          </Link>
        </div>
      </div>

      {/* Error */}
      {error && (
        <Alert variant="danger">
          <div className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button variant="ghost" size="sm" onClick={loadPareceres}>
              Tentar novamente
            </Button>
          </div>
        </Alert>
      )}

      {/* Content */}
      {loading ? (
        <LoadingBlock label="Carregando pareceres..." />
      ) : pareceres.length === 0 ? (
        <EmptyState
          icon={FileSearch}
          title="Nenhum parecer encontrado"
          description="Crie um novo parecer para começar a análise de documentação de fornecedores."
          action={
            <Link href="/dashboard/parecer-tecnico/novo">
              <Button variant="outline">Criar primeiro parecer</Button>
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {pareceres.map((p) => {
            const borderColor = (p.parecer_geral && PARECER_BORDER_COLORS[p.parecer_geral]) || "border-l-edge";
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
                className={`group relative rounded-lg border border-l-2 bg-surface-1 p-4 transition-colors hover:border-edge-strong hover:bg-surface-2 ${borderColor} ${
                  selected ? "ring-2 ring-accent" : ""
                }`}
              >
                <div className={`absolute top-3 right-3 transition-opacity ${selected ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}>
                  <Checkbox
                    checked={selected}
                    onCheckedChange={(checked) => toggleSelectOne(p.id, checked === true)}
                  />
                </div>

                <Link href={`/dashboard/parecer-tecnico/${p.id}`} className="block space-y-3">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-[13px] font-medium text-fg">{p.numero_parecer}</span>
                      <ProcessamentoBadge status={p.status_processamento} />
                      <Badge variant="secondary" className="text-xs">
                        {DISCIPLINA_LABELS[p.disciplina] ?? p.disciplina}
                      </Badge>
                      {p.fase_caso === "FECHADO" ? (
                        <Badge
                          variant={DESFECHO_VARIANT[p.desfecho ?? ""] ?? "secondary"}
                          className="text-xs"
                          dot
                        >
                          {desfechoLabel(p.desfecho)}
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs">
                          {faseLabel(p.fase_caso)}
                        </Badge>
                      )}
                    </div>
                    <p className="mt-0.5 text-sm font-medium text-fg">{p.projeto}</p>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-fg-muted">
                    <span>{p.fornecedor}</span>
                    <span>Rev. {p.revisao}</span>
                    <span>{new Date(p.criado_em).toLocaleDateString("pt-BR")}</span>
                  </div>

                  {p.total_itens > 0 && (
                    <div className="space-y-1">
                      <div className="flex h-1.5 overflow-hidden rounded-sm bg-surface-2">
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
                        <span className="text-xs text-fg-subtle">{p.total_itens} itens</span>
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
