"use client";

/**
 * ItemsBrowserWidget — navegação livre pelos itens do parecer, invocado por
 * comando ("ver itens", "ver item 4"). Tabela compacta com linha expansível:
 * detalhe completo, histórico de rodadas e edição de campos.
 */

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ItemParecerResponse } from "@/lib/patec-api";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";
import { STATUS_INFO } from "./analise-resultado-widget";
import { HistoricoInline } from "./item-decision-widget";
import { patecApi } from "@/lib/patec-api";

const ESTADO_LABELS: Record<string, string> = {
  ABERTO: "Aberto",
  PENDENTE_FORNECEDOR: "Pendente fornecedor",
  EM_REAVALIACAO: "Em reavaliação",
  ACEITO: "Aceito",
  REPROVADO: "Reprovado",
  DESATIVADO: "Desativado",
};

function ItemDetail({ item }: { item: ItemParecerResponse }) {
  const { parecerId, refreshSnapshot } = useConversation();
  const [showHistorico, setShowHistorico] = useState(false);
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState(item.status);
  const [justificativa, setJustificativa] = useState(item.justificativa_tecnica);
  const [acao, setAcao] = useState(item.acao_requerida ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      await patecApi.itens.update(parecerId, item.id, {
        status,
        justificativa_tecnica: justificativa,
        acao_requerida: acao || undefined,
      });
      await refreshSnapshot();
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar item");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-2 border-t border-edge px-3 py-3 text-xs">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {item.valor_requerido && (
          <div>
            <p className="text-[10px] font-semibold uppercase text-fg-subtle">
              Valor requerido
            </p>
            <p className="text-fg">{item.valor_requerido}</p>
          </div>
        )}
        {item.valor_fornecedor && (
          <div>
            <p className="text-[10px] font-semibold uppercase text-fg-subtle">
              Valor do fornecedor
            </p>
            <p className="text-fg">{item.valor_fornecedor}</p>
          </div>
        )}
        {item.norma_referencia && (
          <div>
            <p className="text-[10px] font-semibold uppercase text-fg-subtle">
              Norma
            </p>
            <p className="text-fg">{item.norma_referencia}</p>
          </div>
        )}
        <div>
          <p className="text-[10px] font-semibold uppercase text-fg-subtle">
            Estado no ciclo
          </p>
          <p className="text-fg">
            {ESTADO_LABELS[item.estado] ?? item.estado}
          </p>
        </div>
      </div>

      {editing ? (
        <div className="space-y-2 rounded-lg bg-surface-1 p-2">
          <div className="flex items-center gap-2">
            <label className="text-[10px] font-semibold uppercase text-fg-subtle">
              Status
            </label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="rounded-md border border-edge bg-canvas px-2 py-1 text-xs text-fg outline-none focus:border-accent"
            >
              {Object.entries(STATUS_INFO).map(([s, info]) => (
                <option key={s} value={s}>
                  {s} — {info.label}
                </option>
              ))}
            </select>
          </div>
          <textarea
            value={justificativa}
            onChange={(e) => setJustificativa(e.target.value)}
            placeholder="Justificativa técnica"
            rows={3}
            className="w-full resize-none rounded-md border border-edge bg-canvas px-2 py-1.5 text-xs text-fg outline-none focus:border-accent"
          />
          <textarea
            value={acao}
            onChange={(e) => setAcao(e.target.value)}
            placeholder="Ação requerida (opcional)"
            rows={2}
            className="w-full resize-none rounded-md border border-edge bg-canvas px-2 py-1.5 text-xs text-fg outline-none focus:border-accent"
          />
          {error && <p className="text-danger-text">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancelar
            </Button>
            <Button size="sm" onClick={handleSave} loading={saving}>
              Salvar
            </Button>
          </div>
        </div>
      ) : (
        <>
          {item.justificativa_tecnica && (
            <div>
              <p className="text-[10px] font-semibold uppercase text-fg-subtle">
                Justificativa técnica
              </p>
              <p className="text-fg-muted">{item.justificativa_tecnica}</p>
            </div>
          )}
          {item.acao_requerida && (
            <div>
              <p className="text-[10px] font-semibold uppercase text-warning-text">
                Ação requerida
              </p>
              <p className="text-fg-muted">{item.acao_requerida}</p>
            </div>
          )}
        </>
      )}

      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={() => setShowHistorico((v) => !v)}
          className="text-accent hover:underline"
        >
          {showHistorico ? "ocultar histórico" : "ver histórico de rodadas"}
        </button>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="text-fg-subtle hover:text-fg"
          >
            editar item
          </button>
        )}
        {item.editado_manualmente && (
          <span className="text-[10px] text-fg-disabled">editado manualmente</span>
        )}
      </div>

      {showHistorico && (
        <div className="rounded-lg bg-canvas p-3">
          <HistoricoInline itemId={item.id} />
        </div>
      )}
    </div>
  );
}

export function ItemsBrowserWidget({ focusNumero }: { focusNumero?: number }) {
  const { snapshot } = useConversation();
  const [expanded, setExpanded] = useState<string | null>(() => {
    if (focusNumero == null) return null;
    return (
      snapshot?.itens.find((i) => i.numero === focusNumero)?.id ?? null
    );
  });

  if (!snapshot) return null;

  const itens = [...snapshot.itens]
    .filter((i) => (focusNumero != null ? i.numero === focusNumero : true))
    .sort((a, b) => a.numero - b.numero);

  if (itens.length === 0) {
    return (
      <WidgetFrame>
        <p className="text-sm text-fg-muted">
          {focusNumero != null
            ? `Não encontrei o item #${focusNumero}.`
            : "Ainda não há itens — eles aparecem depois da análise."}
        </p>
      </WidgetFrame>
    );
  }

  return (
    <WidgetFrame
      title={
        focusNumero != null
          ? `Item #${focusNumero}`
          : `${itens.length} itens do parecer`
      }
    >
      <div className="max-h-[28rem] space-y-1 overflow-y-auto pr-1">
        {itens.map((item) => (
          <div
            key={item.id}
            className="rounded-lg border border-edge bg-canvas"
          >
            <button
              onClick={() =>
                setExpanded((cur) => (cur === item.id ? null : item.id))
              }
              className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-surface-2"
            >
              <span className="w-8 shrink-0 font-mono text-xs tabular-nums text-fg-subtle">
                #{item.numero}
              </span>
              <span
                className={`shrink-0 rounded px-1.5 font-mono text-xs font-bold ${STATUS_INFO[item.status]?.chip ?? ""}`}
              >
                {item.status}
              </span>
              {item.marcacao_revisao && (
                <Badge variant="warning" className="text-[10px]">
                  {item.marcacao_revisao}
                </Badge>
              )}
              <span className="min-w-0 flex-1 truncate text-xs text-fg-muted">
                {item.descricao_requisito}
              </span>
              <span className="shrink-0 text-xs text-fg-disabled">
                {expanded === item.id ? "▲" : "▼"}
              </span>
            </button>
            {expanded === item.id && <ItemDetail item={item} />}
          </div>
        ))}
      </div>
    </WidgetFrame>
  );
}
