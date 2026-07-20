"use client";

/**
 * RequisitosWidget — revisão e aprovação da lista de requisitos extraída
 * pela LLM (W1), inline na conversa. O rascunho é PERSISTIDO no banco
 * (snapshot.requisitosDraft): edições manuais e via chat JulIA gravam lá,
 * e a tabela do caso mostra sempre o estado real.
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { RequisitoBase, RequisitoResponse } from "@/lib/patec-api";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";

const PRIORIDADE_VARIANT: Record<string, "error" | "warning" | "secondary"> = {
  ALTA: "error",
  MEDIA: "warning",
  BAIXA: "secondary",
};

const PRIORIDADES = ["ALTA", "MEDIA", "BAIXA"] as const;

function toBase(r: RequisitoResponse): RequisitoBase {
  return {
    numero: r.numero,
    categoria: r.categoria,
    descricao_requisito: r.descricao_requisito,
    referencia_engenharia: r.referencia_engenharia,
    valor_requerido: r.valor_requerido,
    prioridade: (r.prioridade as RequisitoBase["prioridade"]) ?? "MEDIA",
    norma_referencia: r.norma_referencia,
  };
}

export function RequisitosWidget() {
  const {
    snapshot,
    requisitosResumo,
    extracting,
    extrairRequisitos,
    salvarDraft,
    aprovarEAnalisar,
    setShowDataPanel,
  } = useConversation();

  const [feedback, setFeedback] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);
  const [approving, setApproving] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<RequisitoBase | null>(null);

  const draft = snapshot?.requisitosDraft ?? [];
  if (draft.length === 0) return null;

  // Reaberto pós-análise: já existem itens; aprovar vai REFAZER a análise.
  const reaberto = (snapshot?.itens.length ?? 0) > 0;

  const busy = extracting || approving || saving;

  const persistir = async (lista: RequisitoBase[]) => {
    setSaving(true);
    try {
      await salvarDraft(lista);
    } catch {
      // erro exibido pelo provider
    } finally {
      setSaving(false);
    }
  };

  const handleConcluirEdicao = async () => {
    if (editingIdx === null || !editForm) return;
    const lista = draft.map((r, i) => (i === editingIdx ? editForm : toBase(r)));
    setEditingIdx(null);
    setEditForm(null);
    await persistir(lista);
  };

  const handleRemover = async (idx: number) => {
    setEditingIdx(null);
    setEditForm(null);
    await persistir(draft.filter((_, i) => i !== idx).map(toBase));
  };

  const handleRegenerate = async () => {
    if (!feedback.trim()) return;
    // Ajuste pedido pelo engenheiro sobre a lista já extraída — feedback real
    // (pode liberar o teto se ele pedir a lista completa).
    await extrairRequisitos({ feedback });
    setFeedback("");
    setShowFeedback(false);
    setEditingIdx(null);
  };

  const handleApprove = async () => {
    setApproving(true);
    try {
      await aprovarEAnalisar();
    } catch {
      // erro exibido pelo provider
    } finally {
      setApproving(false);
    }
  };

  return (
    <WidgetFrame
      title={`${draft.length} ${draft.length === 1 ? "requisito identificado" : "requisitos identificados"}`}
    >
      {reaberto && (
        <p className="mb-2 rounded-lg bg-canvas px-3 py-2 text-xs text-fg-muted">
          Lista reaberta para edição (sem a comparação do fornecedor). Ao
          <strong> aprovar</strong>, a análise é refeita com a nova lista.
        </p>
      )}
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-xs text-fg-subtle">
          Rascunho salvo no banco — edite aqui, pela{" "}
          <button
            onClick={() => setShowDataPanel(true)}
            className="text-accent hover:underline"
          >
            Tabela do caso
          </button>{" "}
          ou pedindo à JulIA no chat.
        </p>
        {saving && (
          <span className="shrink-0 text-xs text-fg-subtle">salvando...</span>
        )}
      </div>

      {requisitosResumo && (
        <p className="mb-3 rounded-lg bg-info-subtle p-3 text-sm text-info-text">
          {requisitosResumo}
        </p>
      )}

      <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
        {draft.map((item, idx) => (
          <div
            key={item.id}
            className="rounded-lg border border-edge bg-canvas p-3"
          >
            <div className="flex items-start gap-3">
              <span className="mt-0.5 w-6 shrink-0 font-mono text-xs tabular-nums text-fg-subtle">
                {idx + 1}
              </span>
              <div className="min-w-0 flex-1">
                {editingIdx === idx && editForm ? (
                  <div className="space-y-2">
                    <textarea
                      value={editForm.descricao_requisito}
                      onChange={(e) =>
                        setEditForm({
                          ...editForm,
                          descricao_requisito: e.target.value,
                        })
                      }
                      rows={2}
                      className="w-full resize-none rounded-md border border-edge bg-surface-1 px-2 py-1.5 text-sm text-fg outline-none focus:border-accent"
                    />
                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        value={editForm.valor_requerido ?? ""}
                        onChange={(e) =>
                          setEditForm({
                            ...editForm,
                            valor_requerido: e.target.value || null,
                          })
                        }
                        placeholder="Valor requerido (ex: 4-20 mA HART, SIL 2)"
                        className="min-w-0 flex-1 rounded-md border border-edge bg-surface-1 px-2 py-1 text-xs text-fg outline-none focus:border-accent"
                      />
                      <select
                        value={editForm.prioridade}
                        onChange={(e) =>
                          setEditForm({
                            ...editForm,
                            prioridade: e.target.value as RequisitoBase["prioridade"],
                          })
                        }
                        className="rounded-md border border-edge bg-surface-1 px-2 py-1 text-xs text-fg outline-none focus:border-accent"
                      >
                        {PRIORIDADES.map((p) => (
                          <option key={p} value={p}>
                            {p}
                          </option>
                        ))}
                      </select>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={handleConcluirEdicao}
                        loading={saving}
                      >
                        Concluir
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      {item.categoria && (
                        <span className="text-xs font-medium text-fg-muted">
                          {item.categoria}
                        </span>
                      )}
                      <Badge
                        variant={
                          PRIORIDADE_VARIANT[item.prioridade ?? "MEDIA"] ??
                          "secondary"
                        }
                        dot
                      >
                        {item.prioridade ?? "MEDIA"}
                      </Badge>
                      {item.norma_referencia && (
                        <Badge variant="outline">{item.norma_referencia}</Badge>
                      )}
                    </div>
                    <p className="text-sm text-fg">
                      {item.descricao_requisito}
                    </p>
                    {item.valor_requerido && (
                      <p className="mt-0.5 font-mono text-xs text-fg-muted">
                        {item.valor_requerido}
                      </p>
                    )}
                    {item.referencia_engenharia && (
                      <p className="mt-1 text-xs italic text-fg-subtle">
                        Fonte: {item.referencia_engenharia}
                      </p>
                    )}
                  </>
                )}
              </div>
              {editingIdx !== idx && (
                <div className="flex shrink-0 gap-1">
                  <button
                    onClick={() => {
                      setEditingIdx(idx);
                      setEditForm(toBase(item));
                    }}
                    disabled={busy}
                    className="rounded px-1.5 py-0.5 text-xs text-fg-muted hover:bg-surface-2 hover:text-fg disabled:opacity-40"
                  >
                    Editar
                  </button>
                  <button
                    onClick={() => handleRemover(idx)}
                    disabled={busy}
                    className="rounded px-1.5 py-0.5 text-xs text-danger/80 hover:bg-danger-subtle hover:text-danger disabled:opacity-40"
                  >
                    Remover
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Feedback para re-extração */}
      {showFeedback && (
        <div className="mt-3 space-y-2">
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder='Ex: "Extrair só o capítulo 8 (itens 1.1 a 5A.1)", "adicionar item sobre certificação ATEX", "remover itens de documentação"...'
            rows={2}
            className="w-full resize-none rounded-lg border border-edge bg-canvas px-3 py-2 text-sm text-fg outline-none placeholder:text-fg-subtle focus:border-accent"
          />
          <div className="flex justify-center gap-3">
            <Button variant="ghost" onClick={() => setShowFeedback(false)}>
              Cancelar
            </Button>
            <Button
              onClick={handleRegenerate}
              loading={extracting}
              disabled={!feedback.trim() || busy}
            >
              Enviar à JulIA
            </Button>
          </div>
        </div>
      )}

      {/* Enquanto o usuário está conversando com a JulIA (modo feedback), o botão
          de aprovar fica oculto para não ser clicado por engano. */}
      {!showFeedback && (
        <div className="mt-4 flex items-center justify-center gap-3">
          <Button
            variant="secondary"
            onClick={() => setShowFeedback(true)}
            disabled={busy}
          >
            Pedir ajustes à JulIA
          </Button>
          <Button onClick={handleApprove} disabled={busy} loading={approving}>
            {reaberto ? "Aprovar e reavaliar" : "Aprovar e iniciar análise"}
          </Button>
        </div>
      )}
    </WidgetFrame>
  );
}
