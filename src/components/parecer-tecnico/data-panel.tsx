"use client";

/**
 * DataPanel — a "Tabela do caso": visualização direta do banco de dados,
 * sempre acessível pelo botão no topo ou pelo comando "ver tabela".
 *
 * Além de conferir o que está salvo, o engenheiro REVISA EM LOTE: cada linha
 * tem uma caixa de comentário à direita; o botão no rodapé envia tudo de uma
 * vez para a JulIA, que aplica as correções procedentes direto no banco.
 */

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConversation } from "./conversation-provider";
import { STATUS_INFO } from "./widgets/analise-resultado-widget";

const ESTADO_LABELS: Record<string, string> = {
  ABERTO: "Aberto",
  PENDENTE_FORNECEDOR: "Pendente fornecedor",
  EM_REAVALIACAO: "Em reavaliação",
  ACEITO: "Aceito",
  REPROVADO: "Reprovado",
  DESATIVADO: "Desativado",
};

const PRIORIDADE_VARIANT: Record<string, "error" | "warning" | "secondary"> = {
  ALTA: "error",
  MEDIA: "warning",
  BAIXA: "secondary",
};

const TH_CLASS =
  "px-3 py-2 text-[10px] uppercase tracking-wider text-fg-subtle";
const COMENTARIO_TH = "Seu comentário";

function ComentarioCell({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <td className="w-72 min-w-64 px-3 py-2">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Discorda? Escreva sua observação..."
        rows={2}
        className="w-full resize-y rounded-md border border-edge bg-canvas px-2 py-1.5 text-xs text-fg outline-none transition-colors placeholder:text-fg-disabled focus:border-accent"
      />
    </td>
  );
}

function RequisitosTable({
  comentarios,
  setComentario,
}: {
  comentarios: Record<string, string>;
  setComentario: (key: string, v: string) => void;
}) {
  const { snapshot } = useConversation();
  if (!snapshot) return null;

  const draft = snapshot.requisitosDraft;
  const aprovados = snapshot.requisitos.filter((r) => r.ativo);
  // Draft em revisão tem precedência visual; senão mostra os aprovados
  const lista = draft.length > 0 ? draft : aprovados;
  const ehDraft = draft.length > 0;

  if (lista.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-fg-subtle">
        Ainda não há requisitos — eles aparecem aqui após a extração.
      </p>
    );
  }

  return (
    <table className="w-full border-collapse text-left text-xs">
      <thead className="sticky top-0 z-10 bg-canvas">
        <tr className="border-b border-edge">
          <th className={TH_CLASS}>#</th>
          <th className={TH_CLASS}>Status</th>
          <th className={TH_CLASS}>Categoria</th>
          <th className={TH_CLASS}>Prior.</th>
          <th className={TH_CLASS}>Requisito</th>
          <th className={TH_CLASS}>Valor requerido</th>
          <th className={TH_CLASS}>Norma</th>
          <th className={TH_CLASS}>{COMENTARIO_TH}</th>
        </tr>
      </thead>
      <tbody>
        {lista.map((r) => (
          <tr
            key={r.id}
            className="border-b border-edge/50 align-top hover:bg-surface-2"
          >
            <td className="px-3 py-2 font-mono tabular-nums text-fg-subtle">
              {r.numero}
            </td>
            <td className="px-3 py-2">
              <Badge
                variant={ehDraft ? "warning" : "success"}
                className="text-[10px]"
                dot
              >
                {ehDraft ? "Rascunho" : "Aprovado"}
              </Badge>
            </td>
            <td className="px-3 py-2 text-fg-muted">{r.categoria ?? "—"}</td>
            <td className="px-3 py-2">
              <Badge
                variant={PRIORIDADE_VARIANT[r.prioridade ?? "MEDIA"] ?? "secondary"}
                className="text-[10px]"
              >
                {r.prioridade ?? "MEDIA"}
              </Badge>
            </td>
            <td className="px-3 py-2 text-fg">{r.descricao_requisito}</td>
            <td className="px-3 py-2 font-mono text-fg-muted">
              {r.valor_requerido ?? "—"}
              {r.referencia_engenharia && (
                <span className="mt-1 block font-sans text-[11px] italic text-fg-subtle">
                  Fonte: {r.referencia_engenharia}
                </span>
              )}
            </td>
            <td className="px-3 py-2 text-fg-muted">
              {r.norma_referencia ?? "—"}
            </td>
            <ComentarioCell
              value={comentarios[`req-${r.numero}`] ?? ""}
              onChange={(v) => setComentario(`req-${r.numero}`, v)}
            />
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ItensTable({
  comentarios,
  setComentario,
}: {
  comentarios: Record<string, string>;
  setComentario: (key: string, v: string) => void;
}) {
  const { snapshot } = useConversation();
  if (!snapshot) return null;

  const itens = [...snapshot.itens].sort((a, b) => a.numero - b.numero);

  return (
    <table className="w-full border-collapse text-left text-xs">
      <thead className="sticky top-0 z-10 bg-canvas">
        <tr className="border-b border-edge">
          <th className={TH_CLASS}>#</th>
          <th className={TH_CLASS}>Status</th>
          <th className={TH_CLASS}>Estado no ciclo</th>
          <th className={TH_CLASS}>Requisito</th>
          <th className={TH_CLASS}>Valor requerido</th>
          <th className={TH_CLASS}>Valor do fornecedor</th>
          <th className={TH_CLASS}>Ação requerida</th>
          <th className={TH_CLASS}>{COMENTARIO_TH}</th>
        </tr>
      </thead>
      <tbody>
        {itens.map((i) => (
          <tr
            key={i.id}
            className="border-b border-edge/50 align-top hover:bg-surface-2"
          >
            <td className="px-3 py-2 font-mono tabular-nums text-fg-subtle">
              {i.numero}
            </td>
            <td className="px-3 py-2">
              <span
                className={`rounded px-1.5 font-mono text-xs font-bold ${STATUS_INFO[i.status]?.chip ?? ""}`}
                title={STATUS_INFO[i.status]?.label}
              >
                {i.status}
              </span>
              {i.marcacao_revisao && (
                <Badge variant="warning" className="ml-1 text-[10px]">
                  {i.marcacao_revisao}
                </Badge>
              )}
            </td>
            <td className="px-3 py-2 text-fg-muted">
              {ESTADO_LABELS[i.estado] ?? i.estado}
            </td>
            <td className="px-3 py-2 text-fg">{i.descricao_requisito}</td>
            <td className="px-3 py-2 font-mono text-fg-muted">
              {i.valor_requerido ?? "—"}
              {i.referencia_engenharia && (
                <span className="mt-1 block font-sans text-[11px] italic text-fg-subtle">
                  Fonte: {i.referencia_engenharia}
                </span>
              )}
            </td>
            <td className="px-3 py-2 font-mono text-fg-muted">
              {i.valor_fornecedor ?? "—"}
              {i.referencia_fornecedor && (
                <span className="mt-1 block font-sans text-[11px] italic text-fg-subtle">
                  Fonte: {i.referencia_fornecedor}
                </span>
              )}
              {(i.verificacao_flag || i.verificacao_nota) && (
                <span className="mt-1.5 block font-sans">
                  <Badge variant="warning" className="text-[10px]" dot>
                    {i.verificacao_nota ? "Verificado" : "Verificar"}
                  </Badge>
                  <span
                    className="mt-1 block text-[11px] italic text-warning-text"
                    title={i.verificacao_flag ?? undefined}
                  >
                    {i.verificacao_nota ?? i.verificacao_flag}
                  </span>
                </span>
              )}
            </td>
            <td className="px-3 py-2 text-fg-muted">
              {i.acao_requerida ?? "—"}
            </td>
            <ComentarioCell
              value={comentarios[`item-${i.numero}`] ?? ""}
              onChange={(v) => setComentario(`item-${i.numero}`, v)}
            />
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function DataPanel() {
  const { snapshot, showDataPanel, setShowDataPanel, sendFreeText } =
    useConversation();
  const [comentarios, setComentarios] = useState<Record<string, string>>({});

  if (!showDataPanel || !snapshot) return null;

  const draft = snapshot.requisitosDraft;
  const temDraft = draft.length > 0;
  // Rascunho em revisão (inclui reabertura pós-análise) tem precedência sobre
  // os itens — o usuário está editando a LISTA, não a análise.
  const temItens = !temDraft && snapshot.itens.length > 0;
  const titulo = temDraft
    ? `Requisitos em revisão (${draft.length})`
    : temItens
      ? `Itens do parecer (${snapshot.itens.length})`
      : `Requisitos aprovados (${snapshot.requisitos.filter((r) => r.ativo).length})`;

  const setComentario = (key: string, v: string) =>
    setComentarios((prev) => ({ ...prev, [key]: v }));

  const preenchidos = Object.entries(comentarios).filter(
    ([, v]) => v.trim().length > 0
  );

  const enviarComentarios = async () => {
    if (preenchidos.length === 0) return;
    const alvo = temItens ? "os itens do parecer" : "o rascunho de requisitos";
    const linhas = preenchidos
      .sort(([a], [b]) => {
        const na = parseInt(a.split("-")[1], 10);
        const nb = parseInt(b.split("-")[1], 10);
        return na - nb;
      })
      .map(([key, v]) => {
        const numero = key.split("-")[1];
        const label = temItens ? "Item" : "Requisito";
        return `- ${label} ${numero}: ${v.trim()}`;
      })
      .join("\n");
    const mensagem =
      `Revisei ${alvo} na Tabela do caso e tenho as seguintes observações:\n\n` +
      `${linhas}\n\n` +
      `Aplique as correções que forem procedentes.`;

    setComentarios({});
    setShowDataPanel(false);
    await sendFreeText(mensagem);
  };

  return (
    <div
      className="fixed inset-0 z-(--z-modal) flex items-center justify-center bg-overlay p-4"
      onClick={() => setShowDataPanel(false)}
    >
      <div
        className="flex max-h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-edge bg-canvas shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-edge px-5 py-3">
          <div>
            <h2 className="font-sans text-sm font-bold text-fg">
              Tabela do caso — {titulo}
            </h2>
            <p className="text-xs text-fg-subtle">
              Direto do banco de dados. Comente as divergências na coluna da
              direita e envie tudo de uma vez para a JulIA.
            </p>
          </div>
          <button
            onClick={() => setShowDataPanel(false)}
            className="rounded px-2 py-1 text-sm text-fg-subtle hover:bg-surface-2 hover:text-fg"
            aria-label="Fechar tabela"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-auto">
          {temItens ? (
            <ItensTable comentarios={comentarios} setComentario={setComentario} />
          ) : (
            <RequisitosTable
              comentarios={comentarios}
              setComentario={setComentario}
            />
          )}
        </div>

        {/* Rodapé: envio em lote dos comentários */}
        <div className="flex items-center justify-between gap-3 border-t border-edge px-5 py-3">
          <p className="text-xs text-fg-subtle">
            {preenchidos.length === 0
              ? "Escreva observações nas linhas que discordar — a JulIA aplica as correções no banco."
              : `${preenchidos.length} ${preenchidos.length === 1 ? "comentário pronto" : "comentários prontos"} para envio.`}
          </p>
          <Button
            onClick={enviarComentarios}
            disabled={preenchidos.length === 0}
          >
            Enviar comentários à JulIA
            {preenchidos.length > 0 ? ` (${preenchidos.length})` : ""}
          </Button>
        </div>
      </div>
    </div>
  );
}
