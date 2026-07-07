"use client";

/**
 * CicloTablePanel — visão de TABELA da fase de decisão (W4), modelo
 * "resolvedora": a JulIA já avaliou tudo; a tabela mostra a análise PRONTA
 * (sem aceites item-a-item). O engenheiro lê e, em última instância, abre o
 * "Comentar" de um item para CONVERSAR com a JulIA sobre ele e, se precisar,
 * pedir aprovação/reprovação. O commit em lote é o "Aplicar e seguir".
 *
 * Dados de GET /ciclo/itens (não do snapshot), buscados ao abrir.
 */

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  patecApi,
  type DecisaoHumana,
  type ItemRevisaoResponse,
} from "@/lib/patec-api";
import { useConversation } from "../conversation-provider";

const VEREDITO_LABELS: Record<string, string> = {
  ATENDE: "Atende",
  PARCIAL: "Parcial",
  NAO_ATENDE: "Não atende",
};

const DECISAO_LABELS: Record<string, string> = {
  ACEITAR: "Aceitar",
  ESCLARECER: "Esclarecer",
  REJEITAR: "Rejeitar",
  REPROVAR_CASO: "Reprovar caso",
};

const VEREDITO_PARA_SUGESTAO: Record<string, string> = {
  ATENDE: "ACEITAR",
  PARCIAL: "ESCLARECER",
  NAO_ATENDE: "REJEITAR",
};

const ESTADO_INFO: Record<
  string,
  { label: string; variant: "success" | "warning" | "error" | "secondary" | "info" }
> = {
  ABERTO: { label: "Aberto", variant: "secondary" },
  PENDENTE_FORNECEDOR: { label: "Aguardando fornecedor", variant: "info" },
  EM_REAVALIACAO: { label: "Avaliado pela JulIA", variant: "warning" },
  ACEITO: { label: "Aceito", variant: "success" },
  REPROVADO: { label: "Reprovado", variant: "error" },
  DESATIVADO: { label: "Desativado", variant: "secondary" },
};

function vereditoVariant(
  v: string | null | undefined
): "success" | "warning" | "error" | "secondary" {
  if (v === "ATENDE") return "success";
  if (v === "PARCIAL") return "warning";
  if (v === "NAO_ATENDE") return "error";
  return "secondary";
}

const TH = "px-3 py-2 text-[10px] uppercase tracking-wider text-fg-subtle";

// Detecta, de forma determinística, se a mensagem do engenheiro expressa uma
// DECISÃO sobre o item (não uma pergunta). Retorna a decisão ou null (→ vira
// conversa com a JulIA). No ciclo, a decisão é aplicada via decidirItem — não
// adianta a JulIA editar o status, que é outro campo.
function detectarDecisao(msg: string): DecisaoHumana | null {
  const t = msg
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
  // Perguntas não decidem (ex.: "você acha que pode aprovar?").
  if (/\?/.test(t) || /\b(sera|voce acha|o que|como|qual|por ?que)\b/.test(t)) {
    return null;
  }
  if (/reprov\w*\s+(o\s+|esse\s+|este\s+)?caso/.test(t)) return "REPROVAR_CASO";
  const negado = /\bnao\s+(pode\s+|deve\s+)?(aprov|aceit|libera|segu)/.test(t);
  if (!negado && /\b(aprov|aceit|libera|de acordo|esta ok|ta ok|pode seguir|conforme)/.test(t)) {
    return "ACEITAR";
  }
  if (/\b(rejeit|recus|nega\b|nao atende|reprov)/.test(t)) return "REJEITAR";
  if (/\b(esclarec|pendencia|falta (info|detal)|detalh\w* melhor|precisa explic)/.test(t)) {
    return "ESCLARECER";
  }
  return null;
}

// ── Diálogo de comentário por item ──────────────────────────────────────────
function ItemComentarDialog({
  item,
  onClose,
  onChanged,
}: {
  item: ItemRevisaoResponse;
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const {
    sendFreeText,
    streamingContent,
    chatSending,
    decidirItem,
    desfazerDecisao,
  } = useConversation();
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmReprovar, setConfirmReprovar] = useState(false);
  const [motivo, setMotivo] = useState("");

  const r = item.ultima_rodada;
  const pendente = item.estado === "EM_REAVALIACAO";
  const decidido =
    item.estado === "ACEITO" || item.estado === "PENDENTE_FORNECEDOR";

  const enviar = async () => {
    const t = input.trim();
    if (!t || chatSending || busy) return;

    // Se a mensagem expressa uma decisão sobre ESTE item (e ele está pendente),
    // aplica a decisão do ciclo de verdade — não adianta só conversar.
    const decisao = pendente ? detectarDecisao(t) : null;
    if (decisao === "REPROVAR_CASO") {
      setInput("");
      setConfirmReprovar(true); // ação destrutiva → pede confirmação
      return;
    }
    if (decisao) {
      setInput("");
      await decidir(decisao); // aplica (Aceitar/Esclarecer/Rejeitar) + fecha
      return;
    }

    // Senão, é conversa: manda para a JulIA.
    setInput("");
    await sendFreeText(
      `Sobre o item ${item.numero} (${item.descricao_requisito}): ${t}`
    );
    await onChanged();
  };

  const decidir = async (decisao: DecisaoHumana) => {
    setBusy(true);
    try {
      await decidirItem(
        item.id,
        decisao,
        decisao === "REPROVAR_CASO" ? motivo || undefined : undefined
      );
      await onChanged();
      onClose();
    } catch {
      // erro exibido pelo provider
    } finally {
      setBusy(false);
    }
  };

  const desfazer = async () => {
    setBusy(true);
    try {
      await desfazerDecisao(item.id);
      await onChanged();
      onClose();
    } catch {
      // erro exibido pelo provider
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-(--z-popover) flex items-center justify-center bg-overlay p-4"
      onClick={(e) => {
        e.stopPropagation();
        onClose();
      }}
    >
      <div
        className="flex max-h-[82vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-edge bg-canvas shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-edge px-4 py-3">
          <h3 className="font-sans text-sm font-bold text-fg">
            Item {item.numero} · conversar com a JulIA
          </h3>
          <button
            onClick={onClose}
            className="rounded px-2 py-1 text-sm text-fg-subtle hover:bg-surface-2 hover:text-fg"
            aria-label="Fechar"
          >
            ✕
          </button>
        </div>

        {/* Contexto do item */}
        <div className="border-b border-edge px-4 py-3 text-xs">
          <p className="text-fg">{item.descricao_requisito}</p>
          {r?.veredito_ia && (
            <p className="mt-1.5 text-fg-muted">
              <Badge variant={vereditoVariant(r.veredito_ia)} className="text-[10px]">
                JulIA: {VEREDITO_LABELS[r.veredito_ia] ?? r.veredito_ia}
              </Badge>
              {r.justificativa_ia && (
                <span className="mt-1 block text-fg-subtle">
                  {r.justificativa_ia}
                </span>
              )}
            </p>
          )}
        </div>

        {/* Conversa */}
        <div className="flex-1 overflow-auto px-4 py-3">
          {chatSending || streamingContent ? (
            <div className="whitespace-pre-wrap rounded-lg bg-canvas px-3 py-2 text-xs text-fg-muted">
              {streamingContent || "JulIA está pensando..."}
            </div>
          ) : (
            <p className="text-xs text-fg-subtle">
              Pergunte algo sobre este item ou discuta a avaliação com a JulIA. A
              conversa também fica registrada na thread principal.
            </p>
          )}
        </div>

        {/* Entrada do chat */}
        <div className="border-t border-edge px-4 py-3">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void enviar();
                }
              }}
              placeholder="Fale com a JulIA sobre este item..."
              rows={1}
              disabled={chatSending}
              className="min-h-[38px] flex-1 resize-none rounded-lg border border-edge bg-canvas px-3 py-2 text-sm text-fg outline-none placeholder:text-fg-subtle focus:border-accent disabled:opacity-60"
            />
            <Button
              size="sm"
              variant="secondary"
              onClick={enviar}
              loading={chatSending}
              disabled={chatSending || !input.trim()}
            >
              Enviar
            </Button>
          </div>
        </div>

        {/* Última instância — decisão explícita do engenheiro */}
        <div className="border-t border-edge bg-canvas/40 px-4 py-3">
          <p className="mb-2 text-[10px] uppercase tracking-wide text-fg-subtle">
            Última instância — você decide este item
          </p>
          {confirmReprovar ? (
            <div className="space-y-2">
              <input
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                placeholder="Motivo da reprovação do caso (opcional)"
                className="w-full rounded border border-edge bg-canvas px-2 py-1 text-xs text-fg outline-none focus:border-danger"
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => decidir("REPROVAR_CASO")}
                  loading={busy}
                >
                  Reprovar o caso inteiro
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setConfirmReprovar(false)}
                >
                  Cancelar
                </Button>
              </div>
            </div>
          ) : pendente ? (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                className="text-success-text"
                onClick={() => decidir("ACEITAR")}
                loading={busy}
              >
                Aceitar
              </Button>
              <Button
                size="sm"
                variant="secondary"
                className="text-warning-text"
                onClick={() => decidir("ESCLARECER")}
                loading={busy}
              >
                Esclarecer
              </Button>
              <Button
                size="sm"
                variant="secondary"
                className="text-danger-text"
                onClick={() => decidir("REJEITAR")}
                loading={busy}
              >
                Rejeitar
              </Button>
              <button
                onClick={() => setConfirmReprovar(true)}
                className="ml-auto text-[11px] text-danger/70 hover:underline"
              >
                Reprovar caso
              </button>
            </div>
          ) : decidido ? (
            <Button size="sm" variant="secondary" onClick={desfazer} loading={busy}>
              ↶ Desfazer decisão deste item
            </Button>
          ) : (
            <p className="text-xs text-fg-subtle">
              Sem ação disponível para este item.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export function CicloTablePanel() {
  const {
    parecerId,
    snapshot,
    showCicloPanel,
    setShowCicloPanel,
    desfazerDecisao,
    aplicarAvaliacao,
    downloadCicloRodada,
  } = useConversation();

  const [itens, setItens] = useState<ItemRevisaoResponse[] | null>(null);
  const [desfazendo, setDesfazendo] = useState<string | null>(null);
  const [comentandoId, setComentandoId] = useState<string | null>(null);
  const [aplicando, setAplicando] = useState(false);
  const [exportando, setExportando] = useState(false);

  const recarregar = useCallback(async () => {
    const data = await patecApi.ciclo.itensDoCiclo(parecerId).catch(() => []);
    setItens(data);
  }, [parecerId]);

  useEffect(() => {
    if (!showCicloPanel) return;
    let active = true;
    patecApi.ciclo
      .itensDoCiclo(parecerId)
      .then((data) => {
        if (active) setItens(data);
      })
      .catch(() => {
        if (active) setItens([]);
      });
    return () => {
      active = false;
    };
  }, [showCicloPanel, parecerId]);

  const fechar = () => {
    setItens(null);
    setShowCicloPanel(false);
  };

  if (!showCicloPanel) return null;

  const desfazer = async (itemId: string) => {
    setDesfazendo(itemId);
    try {
      await desfazerDecisao(itemId);
      await recarregar();
    } catch {
      // erro exibido pelo provider
    } finally {
      setDesfazendo(null);
    }
  };

  const aplicar = async () => {
    setAplicando(true);
    try {
      await aplicarAvaliacao();
      fechar();
    } catch {
      // erro exibido pelo provider
    } finally {
      setAplicando(false);
    }
  };

  const exportar = async () => {
    setExportando(true);
    try {
      await downloadCicloRodada();
    } catch {
      // erro exibido pelo provider
    } finally {
      setExportando(false);
    }
  };

  const pendentes = (itens ?? []).filter((i) => i.estado === "EM_REAVALIACAO").length;
  const comentandoItem = itens?.find((i) => i.id === comentandoId) ?? null;

  const comentarBtn = (itemId: string) => (
    <button
      onClick={() => setComentandoId(itemId)}
      className="inline-flex items-center gap-1 rounded-md border border-edge bg-surface-1 px-2 py-0.5 text-[11px] font-medium text-fg-muted hover:bg-surface-2 hover:text-fg"
      title="Conversar com a JulIA sobre este item"
    >
      💬 Comentar
    </button>
  );

  return (
    <div
      className="fixed inset-0 z-(--z-modal) flex items-center justify-center bg-overlay p-4"
      onClick={fechar}
    >
      <div
        className="flex max-h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-edge bg-canvas shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-edge px-5 py-3">
          <div>
            <h2 className="font-sans text-sm font-bold text-fg">
              Análise das respostas — feita pela JulIA
            </h2>
            <p className="text-xs text-fg-subtle">
              {itens === null
                ? "Carregando..."
                : `${itens.length} itens · ${pendentes} avaliado(s). Revise; use Comentar só se quiser corrigir.`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={exportar}
              loading={exportando}
              disabled={exportando}
            >
              Exportar Excel
            </Button>
            <button
              onClick={fechar}
              className="rounded px-2 py-1 text-sm text-fg-subtle hover:bg-surface-2 hover:text-fg"
              aria-label="Fechar"
            >
              ✕
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto">
          {itens === null ? (
            <p className="py-10 text-center text-sm text-fg-subtle">
              Carregando itens...
            </p>
          ) : itens.length === 0 ? (
            <p className="py-10 text-center text-sm text-fg-subtle">
              Nenhum item no ciclo.
            </p>
          ) : (
            <table className="w-full border-collapse text-left text-xs">
              <thead className="sticky top-0 z-10 bg-canvas">
                <tr className="border-b border-edge">
                  <th className={TH}>#</th>
                  <th className={TH}>Requisito</th>
                  <th className={TH}>Resposta do fornecedor</th>
                  <th className={TH}>Avaliação da JulIA</th>
                  <th className={TH}>Situação</th>
                  <th className={TH}>Decisão</th>
                </tr>
              </thead>
              <tbody>
                {itens.map((i) => {
                  const r = i.ultima_rodada;
                  const estado = ESTADO_INFO[i.estado] ?? {
                    label: i.estado,
                    variant: "secondary" as const,
                  };
                  const pendente = i.estado === "EM_REAVALIACAO";
                  const sugestao = r?.veredito_ia
                    ? VEREDITO_PARA_SUGESTAO[r.veredito_ia] ?? "ESCLARECER"
                    : "ESCLARECER";
                  return (
                    <tr
                      key={i.id}
                      className="border-b border-edge/50 align-top hover:bg-surface-2"
                    >
                      <td className="px-3 py-2 font-mono tabular-nums text-fg-subtle">
                        {i.numero}
                      </td>
                      <td className="px-3 py-2 text-fg">
                        {i.descricao_requisito}
                        {i.valor_requerido && (
                          <span className="mt-1 block font-mono text-[11px] text-fg-subtle">
                            {i.valor_requerido}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-fg-muted">
                        {r?.conteudo ?? "—"}
                      </td>
                      <td className="px-3 py-2">
                        {r?.veredito_ia ? (
                          <>
                            <Badge
                              variant={vereditoVariant(r.veredito_ia)}
                              className="text-[10px]"
                            >
                              {VEREDITO_LABELS[r.veredito_ia] ?? r.veredito_ia}
                            </Badge>
                            {r.justificativa_ia && (
                              <span className="mt-1 block text-[11px] text-fg-subtle">
                                {r.justificativa_ia}
                              </span>
                            )}
                          </>
                        ) : (
                          <span className="text-fg-subtle">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant={estado.variant} dot className="text-[10px]">
                          {estado.label}
                        </Badge>
                      </td>
                      <td className="px-3 py-2">
                        {pendente ? (
                          <div className="flex flex-col items-start gap-1.5">
                            <Badge
                              variant={vereditoVariant(r?.veredito_ia)}
                              className="text-[10px]"
                            >
                              Sugerido: {DECISAO_LABELS[sugestao]}
                            </Badge>
                            {comentarBtn(i.id)}
                          </div>
                        ) : r?.decisao_humana ? (
                          <div className="flex flex-col items-start gap-1.5">
                            <span className="text-fg-muted">
                              {DECISAO_LABELS[r.decisao_humana] ?? r.decisao_humana}
                            </span>
                            <div className="flex items-center gap-2">
                              {r.decisao_humana !== "REPROVAR_CASO" &&
                                (i.estado === "ACEITO" ||
                                  i.estado === "PENDENTE_FORNECEDOR") && (
                                  <button
                                    onClick={() => desfazer(i.id)}
                                    disabled={desfazendo === i.id}
                                    className="text-[11px] text-accent hover:underline disabled:opacity-40"
                                    title="Voltar este item para a fila"
                                  >
                                    {desfazendo === i.id
                                      ? "desfazendo..."
                                      : "↶ Desfazer"}
                                  </button>
                                )}
                              {comentarBtn(i.id)}
                            </div>
                          </div>
                        ) : (
                          comentarBtn(i.id)
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-edge px-5 py-3">
          <p className="text-xs text-fg-subtle">
            A análise da JulIA já está pronta. Aplique tudo de uma vez — ou ajuste
            antes pelo Comentar de cada item.
          </p>
          <Button
            onClick={aplicar}
            loading={aplicando}
            disabled={aplicando || pendentes === 0 || !snapshot}
          >
            Aplicar e seguir{pendentes > 0 ? ` (${pendentes})` : ""}
          </Button>
        </div>
      </div>

      {comentandoItem && (
        <ItemComentarDialog
          item={comentandoItem}
          onClose={() => setComentandoId(null)}
          onChanged={recarregar}
        />
      )}
    </div>
  );
}
