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
      "border-green-700/50 text-green-400 hover:bg-green-900/30",
    activeColor: "bg-green-600 text-white border-green-600",
  },
  {
    status: "B",
    label: "Aprov. Com.",
    color:
      "border-yellow-700/50 text-yellow-400 hover:bg-yellow-900/30",
    activeColor: "bg-yellow-600 text-white border-yellow-600",
  },
  {
    status: "C",
    label: "Rejeitado",
    color:
      "border-red-700/50 text-red-400 hover:bg-red-900/30",
    activeColor: "bg-red-600 text-white border-red-600",
  },
  {
    status: "D",
    label: "Info Ausente",
    color:
      "border-gray-600/50 text-gray-400 hover:bg-gray-800/50",
    activeColor: "bg-gray-600 text-white border-gray-600",
  },
  {
    status: "E",
    label: "Adicional",
    color:
      "border-blue-700/50 text-blue-400 hover:bg-blue-900/30",
    activeColor: "bg-blue-600 text-white border-blue-600",
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
      <div className="border-b border-border bg-surface px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-text-primary">
              Item {item.numero}
            </h2>
            <StatusBadge status={item.status} />
            {item.prioridade && <PriorityBadge priority={item.prioridade} />}
            {item.categoria && (
              <span className="rounded bg-white/10 px-2 py-0.5 text-xs text-text-secondary">
                {item.categoria}
              </span>
            )}
            {item.editado_manualmente && (
              <span className="rounded bg-purple-900/40 px-2 py-0.5 text-xs text-purple-400">
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
          <span className="text-xs text-text-tertiary">{positionText}</span>
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
          <div className="rounded-lg border border-blue-700/40 bg-blue-900/20">
            <div className="border-b border-blue-700/40 px-4 py-2">
              <h3 className="text-sm font-semibold text-blue-400">
                Solicitacao da Engenharia
              </h3>
            </div>
            <div className="space-y-3 p-4">
              <div>
                <p className="text-xs font-medium text-blue-400/80">
                  Requisito
                </p>
                <p className="mt-1 whitespace-pre-line text-sm text-text-primary">
                  {item.descricao_requisito}
                </p>
              </div>
              {item.valor_requerido && (
                <div>
                  <p className="text-xs font-medium text-blue-400/80">
                    Valor Requerido
                  </p>
                  <p className="mt-1 text-sm text-text-primary">
                    {item.valor_requerido}
                  </p>
                </div>
              )}
              {item.referencia_engenharia && (
                <div>
                  <p className="text-xs font-medium text-blue-400/80">
                    Referencia
                  </p>
                  <p className="mt-1 text-sm text-text-primary">
                    {item.referencia_engenharia}
                  </p>
                </div>
              )}
              {item.norma_referencia && (
                <div>
                  <p className="text-xs font-medium text-blue-400/80">Norma</p>
                  <p className="mt-1 text-sm text-text-primary">
                    {item.norma_referencia}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Supplier side */}
          <div className="rounded-lg border border-amber-700/40 bg-amber-900/20">
            <div className="border-b border-amber-700/40 px-4 py-2">
              <h3 className="text-sm font-semibold text-amber-400">
                Proposta do Fornecedor
              </h3>
            </div>
            <div className="space-y-3 p-4">
              {item.valor_fornecedor ? (
                <div>
                  <p className="text-xs font-medium text-amber-400/80">
                    Valor Proposto
                  </p>
                  <p className="mt-1 whitespace-pre-line text-sm text-text-primary">
                    {item.valor_fornecedor}
                  </p>
                </div>
              ) : (
                <p className="text-sm italic text-text-tertiary">
                  Nao informado pelo fornecedor
                </p>
              )}
              {item.referencia_fornecedor && (
                <div>
                  <p className="text-xs font-medium text-amber-400/80">
                    Referencia
                  </p>
                  <p className="mt-1 text-sm text-text-primary">
                    {item.referencia_fornecedor}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Justification */}
        <div className="space-y-4 rounded-lg border border-border bg-surface p-4">
          <div>
            <p className="text-xs font-semibold text-text-secondary">
              Justificativa Tecnica
            </p>
            {editing ? (
              <textarea
                className="mt-1 w-full rounded-md border border-border bg-bg-primary p-2 text-sm text-text-primary outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                rows={4}
                value={editJustificativa}
                onChange={(e) => setEditJustificativa(e.target.value)}
              />
            ) : (
              <p className="mt-1 whitespace-pre-line text-sm text-text-primary">
                {item.justificativa_tecnica || "—"}
              </p>
            )}
          </div>

          <div>
            <p className="text-xs font-semibold text-text-secondary">
              Acao Requerida
            </p>
            {editing ? (
              <textarea
                className="mt-1 w-full rounded-md border border-border bg-bg-primary p-2 text-sm text-text-primary outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                rows={3}
                value={editAcao}
                onChange={(e) => setEditAcao(e.target.value)}
              />
            ) : (
              <p className="mt-1 whitespace-pre-line text-sm text-text-primary">
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
        <div className="rounded-lg border border-border bg-surface p-4">
          <p className="mb-3 text-xs font-semibold text-text-secondary">
            Classificacao Rapida
            <span className="ml-2 font-normal text-text-tertiary">
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
