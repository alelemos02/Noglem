"use client";

import { useRef, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "./status-badge";
import { PriorityBadge } from "./priority-badge";
import {
  useWorkspace,
  STATUS_COLORS,
  STATUS_OPTIONS,
} from "./workspace-context";

interface ItemListPanelProps {
  onItemSelect?: () => void;
}

export function ItemListPanel({ onItemSelect }: ItemListPanelProps) {
  const {
    filteredItens,
    itens,
    selectedItemId,
    selectItem,
    filters,
    setFilters,
    statusCounts,
  } = useWorkspace();

  const selectedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedItemId]);

  const handleSelect = (id: string) => {
    selectItem(id);
    onItemSelect?.();
  };

  const summaryParts: string[] = [];
  if (statusCounts.C > 0) summaryParts.push(`${statusCounts.C} rejeitados`);
  if (statusCounts.D > 0) summaryParts.push(`${statusCounts.D} info ausente`);
  if (statusCounts.B > 0) summaryParts.push(`${statusCounts.B} c/ comentarios`);

  return (
    <div className="flex h-full flex-col">
      {/* Search + filters */}
      <div className="border-b border-border p-3 space-y-2">
        <Input
          placeholder="Buscar itens..."
          className="h-8 text-sm"
          value={filters.busca}
          onChange={(e) => setFilters({ busca: e.target.value })}
        />

        {/* Status filter pills */}
        <div className="flex flex-wrap gap-1">
          {STATUS_OPTIONS.filter((o) => o.value !== "").map((opt) => {
            const count = statusCounts[opt.value] || 0;
            if (count === 0) return null;
            const active = filters.status === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() =>
                  setFilters({ status: active ? "" : opt.value })
                }
                className={`rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
                  active
                    ? "bg-accent text-white"
                    : "border border-border text-text-secondary hover:bg-surface-hover"
                }`}
              >
                {opt.label} ({count})
              </button>
            );
          })}
        </div>

        {/* Count */}
        <div className="text-xs text-text-tertiary">
          {filteredItens.length} de {itens.length} itens
          {summaryParts.length > 0 && ` (${summaryParts.join(", ")})`}
        </div>
      </div>

      {/* Item list */}
      <div className="flex-1 overflow-y-auto">
        {filteredItens.length === 0 ? (
          <div className="p-6 text-center text-sm text-text-tertiary">
            Nenhum item encontrado
          </div>
        ) : (
          filteredItens.map((item) => {
            const isSelected = item.id === selectedItemId;
            return (
              <div
                key={item.id}
                ref={isSelected ? selectedRef : undefined}
                onClick={() => handleSelect(item.id)}
                className={`cursor-pointer border-b border-border border-l-4 p-3 transition-colors ${
                  STATUS_COLORS[item.status] || "border-l-border"
                } ${
                  isSelected
                    ? "bg-accent/10 ring-1 ring-inset ring-accent/30"
                    : "hover:bg-surface-hover"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-text-secondary">
                        Item {item.numero}
                      </span>
                      <StatusBadge status={item.status} />
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm text-text-primary">
                      {item.descricao_requisito}
                    </p>
                    {item.categoria && (
                      <span className="mt-1 inline-block text-xs text-text-tertiary">
                        {item.categoria}
                      </span>
                    )}
                  </div>
                  <div className="flex-shrink-0">
                    {item.prioridade && item.prioridade !== "BAIXA" && (
                      <PriorityBadge priority={item.prioridade} />
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
