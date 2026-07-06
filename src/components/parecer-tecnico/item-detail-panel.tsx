"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "./status-badge";
import { PriorityBadge } from "./priority-badge";
import { useWorkspace } from "./workspace-context";

const CLASSIFICATION_BUTTONS = [
  {
    status: "A",
    label: "Aprovado",
    color:
      "border-success/35 text-success hover:bg-success-subtle",
    activeColor: "bg-success text-white border-success/35",
  },
  {
    status: "B",
    label: "Aprov. Com.",
    color:
      "border-warning/35 text-warning hover:bg-warning-subtle",
    activeColor: "bg-warning text-white border-warning/35",
  },
  {
    status: "C",
    label: "Rejeitado",
    color:
      "border-danger/35 text-danger hover:bg-danger-subtle",
    activeColor: "bg-danger text-white border-danger/35",
  },
  {
    status: "D",
    label: "Info Ausente",
    color:
      "border-edge-strong text-fg-muted hover:bg-surface-2",
    activeColor: "bg-fg-subtle text-white border-edge-strong",
  },
  {
    status: "E",
    label: "Adicional",
    color:
      "border-info/35 text-info hover:bg-info-subtle",
    activeColor: "bg-info text-white border-info/35",
  },
];

export function ItemDetailPanel() {
  const {
    selectedItem,
    selectedItemId,
    filteredItens,
    selectNextItem,
    selectPreviousItem,
    updateItem,
  } = useWorkspace();

  const [editing, setEditing] = useState(false);
  const [editJustificativa, setEditJustificativa] = useState("");
  const [editAcao, setEditAcao] = useState("");
  const [saving, setSaving] = useState(false);

  const item = selectedItem;
  if (!item) return null;

  const currentIdx = filteredItens.findIndex((i) => i.id === selectedItemId);
  const positionText = `Item ${currentIdx + 1} de ${filteredItens.length}`;

  const handleClassify = async (newStatus: string) => {
    if (newStatus === item.status || saving) return;
    setSaving(true);
    try {
      await updateItem(item.id, { status: newStatus });
    } finally {
      setSaving(false);
    }
  };

  const startEdit = () => {
    setEditJustificativa(item.justificativa_tecnica || "");
    setEditAcao(item.acao_requerida || "");
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      await updateItem(item.id, {
        justificativa_tecnica: editJustificativa,
        acao_requerida: editAcao,
      });
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-edge bg-surface-1 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-fg">
              Item {item.numero}
            </h2>
            <StatusBadge status={item.status} />
            {item.prioridade && <PriorityBadge priority={item.prioridade} />}
            {item.categoria && (
              <span className="rounded bg-white/10 px-2 py-0.5 text-xs text-fg-muted">
                {item.categoria}
              </span>
            )}
            {item.editado_manualmente && (
              <span className="rounded bg-info-subtle px-2 py-0.5 text-xs text-info">
                Editado
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {!editing && (
              <Button variant="outline" size="sm" onClick={startEdit}>
                Editar
              </Button>
            )}
          </div>
        </div>

        {/* Navigation */}
        <div className="mt-2 flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={selectPreviousItem}
          >
            ← Anterior
          </Button>
          <span className="text-xs text-fg-subtle">{positionText}</span>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={selectNextItem}
          >
            Proximo →
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {/* Side-by-side comparison */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Engineering side */}
          <div className="rounded-lg border border-info/35 bg-info-subtle">
            <div className="border-b border-info/35 px-4 py-2">
              <h3 className="text-sm font-semibold text-info">
                Solicitacao da Engenharia
              </h3>
            </div>
            <div className="space-y-3 p-4">
              <div>
                <p className="text-xs font-medium text-info-text">
                  Requisito
                </p>
                <p className="mt-1 whitespace-pre-line text-sm text-fg">
                  {item.descricao_requisito}
                </p>
              </div>
              {item.valor_requerido && (
                <div>
                  <p className="text-xs font-medium text-info-text">
                    Valor Requerido
                  </p>
                  <p className="mt-1 text-sm text-fg">
                    {item.valor_requerido}
                  </p>
                </div>
              )}
              {item.referencia_engenharia && (
                <div>
                  <p className="text-xs font-medium text-info-text">
                    Referencia
                  </p>
                  <p className="mt-1 text-sm text-fg">
                    {item.referencia_engenharia}
                  </p>
                </div>
              )}
              {item.norma_referencia && (
                <div>
                  <p className="text-xs font-medium text-info-text">Norma</p>
                  <p className="mt-1 text-sm text-fg">
                    {item.norma_referencia}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Supplier side */}
          <div className="rounded-lg border border-warning/35 bg-warning-subtle">
            <div className="border-b border-warning/35 px-4 py-2">
              <h3 className="text-sm font-semibold text-warning">
                Proposta do Fornecedor
              </h3>
            </div>
            <div className="space-y-3 p-4">
              {item.valor_fornecedor ? (
                <div>
                  <p className="text-xs font-medium text-warning-text">
                    Valor Proposto
                  </p>
                  <p className="mt-1 whitespace-pre-line text-sm text-fg">
                    {item.valor_fornecedor}
                  </p>
                </div>
              ) : (
                <p className="text-sm italic text-fg-subtle">
                  Nao informado pelo fornecedor
                </p>
              )}
              {item.referencia_fornecedor && (
                <div>
                  <p className="text-xs font-medium text-warning-text">
                    Referencia
                  </p>
                  <p className="mt-1 text-sm text-fg">
                    {item.referencia_fornecedor}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Justification */}
        <div className="space-y-4 rounded-lg border border-edge bg-surface-1 p-4">
          <div>
            <p className="text-xs font-semibold text-fg-muted">
              Justificativa Tecnica
            </p>
            {editing ? (
              <textarea
                className="mt-1 w-full rounded-md border border-edge bg-canvas p-2 text-sm text-fg outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                rows={4}
                value={editJustificativa}
                onChange={(e) => setEditJustificativa(e.target.value)}
              />
            ) : (
              <p className="mt-1 whitespace-pre-line text-sm text-fg">
                {item.justificativa_tecnica || "—"}
              </p>
            )}
          </div>

          <div>
            <p className="text-xs font-semibold text-fg-muted">
              Acao Requerida
            </p>
            {editing ? (
              <textarea
                className="mt-1 w-full rounded-md border border-edge bg-canvas p-2 text-sm text-fg outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                rows={3}
                value={editAcao}
                onChange={(e) => setEditAcao(e.target.value)}
              />
            ) : (
              <p className="mt-1 whitespace-pre-line text-sm text-fg">
                {item.acao_requerida || "Nenhuma"}
              </p>
            )}
          </div>

          {editing && (
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={cancelEdit}
                disabled={saving}
              >
                Cancelar
              </Button>
              <Button size="sm" onClick={saveEdit} disabled={saving}>
                {saving ? "Salvando..." : "Salvar"}
              </Button>
            </div>
          )}
        </div>

        {/* Classification bar */}
        <div className="rounded-lg border border-edge bg-surface-1 p-4">
          <p className="mb-3 text-xs font-semibold text-fg-muted">
            Classificacao Rapida
            <span className="ml-2 font-normal text-fg-subtle">
              (teclas 1-5)
            </span>
          </p>
          <div className="flex flex-wrap gap-2">
            {CLASSIFICATION_BUTTONS.map((btn, idx) => {
              const isActive = item.status === btn.status;
              return (
                <button
                  key={btn.status}
                  onClick={() => handleClassify(btn.status)}
                  disabled={saving}
                  className={`flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-all ${
                    isActive ? btn.activeColor : btn.color
                  } ${saving ? "opacity-50" : ""}`}
                >
                  <kbd className="rounded bg-white/20 px-1 font-mono text-xs">
                    {idx + 1}
                  </kbd>
                  {btn.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
