/**
 * deriveTimeline — reconstrói o "passado congelado" da conversa a partir dos
 * registros persistidos no backend (com seus timestamps reais), mesclado
 * cronologicamente com o histórico do chat RAG.
 *
 * Função pura: mesmo snapshot ⇒ mesma timeline. É isso que torna o F5
 * idempotente — a conversa se remonta sozinha do banco.
 */

import type { Snapshot, TimelineEntry } from "./types";
import { mensagemAbertura, desfechoLabel } from "./script";

const DOC_TIPO_LABELS: Record<string, string> = {
  engenharia: "engenharia",
  fornecedor: "fornecedor",
  anexo_engenharia: "anexo da engenharia",
  resposta_fornecedor: "resposta do fornecedor",
};

export const RODADA_TIPO_LABELS: Record<string, string> = {
  PROPOSTA_REVISADA: "Tipo 1 — Proposta revisada",
  RESPOSTA_ITENS: "Tipo 2 — Respostas aos itens",
  RESPOSTA_ITENS_PROPOSTA_POSTERIOR: "Tipo 3 — Respostas + proposta posterior",
  EMAIL_AVULSO: "Tipo 4 — E-mail avulso",
};

const RODADA_STATUS_LABELS: Record<string, string> = {
  RECEBIDA: "recebida",
  VINCULACAO_SUGERIDA: "vínculos sugeridos",
  VINCULACAO_CONFIRMADA: "em avaliação",
  AVALIADA: "avaliada",
  ERRO: "erro",
};

const RESULTADO_LABELS: Record<string, string> = {
  CONFORME: "Conforme",
  CONFORME_COM_PENDENCIA: "Conforme com pendência",
  NAO_CONFORME: "Não conforme",
};

function formatSize(bytes: number | null): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

/** Ordena por timestamp; empate: evento de workflow antes de mensagem de chat. */
function compareEntries(a: TimelineEntry, b: TimelineEntry): number {
  const ta = new Date(a.at).getTime();
  const tb = new Date(b.at).getTime();
  if (ta !== tb) return ta - tb;
  const wa = a.kind === "event" ? 0 : 1;
  const wb = b.kind === "event" ? 0 : 1;
  return wa - wb;
}

export function deriveTimeline(snapshot: Snapshot): TimelineEntry[] {
  const {
    parecer,
    documentos,
    requisitos,
    itens,
    rodadas,
    verificacao,
    specVersoes,
    chatHistory,
  } = snapshot;

  const entries: TimelineEntry[] = [];

  // --- Abertura da JulIA (sempre a primeira entrada) ---
  entries.push({
    kind: "julia",
    key: "abertura",
    at: parecer.criado_em,
    markdown: mensagemAbertura(snapshot),
  });

  // --- Documentos recebidos ---
  for (const doc of documentos) {
    const tipoLabel = DOC_TIPO_LABELS[doc.tipo] ?? doc.tipo;
    const size = formatSize(doc.tamanho_bytes);
    entries.push({
      kind: "event",
      key: `doc-${doc.id}`,
      at: doc.criado_em,
      title: "Documento recebido",
      detail: `${doc.nome_arquivo} (${tipoLabel}${size ? `, ${size}` : ""})`,
    });
  }

  // --- Requisitos aprovados (W1) ---
  const ativos = requisitos.filter((r) => r.ativo);
  if (ativos.length > 0) {
    const at =
      ativos[0].aprovado_em ?? ativos[0].criado_em ?? parecer.atualizado_em;
    entries.push({
      kind: "event",
      key: "requisitos-aprovados",
      at,
      title: "Requisitos aprovados",
      detail: `${ativos.length} ${ativos.length === 1 ? "requisito" : "requisitos"} viraram a referência oficial da análise`,
      tone: "success",
    });
  }

  // --- Análise concluída (R1) ---
  if (itens.length > 0) {
    // O timestamp mais antigo de item marca a conclusão da análise
    const at = itens.reduce(
      (min, i) => (i.criado_em < min ? i.criado_em : min),
      itens[0].criado_em
    );
    entries.push({
      kind: "event",
      key: "analise-concluida",
      at,
      title: "Análise concluída",
      detail:
        `${parecer.total_itens} itens — ${parecer.total_aprovados} aprovados, ` +
        `${parecer.total_aprovados_comentarios} c/ comentários, ` +
        `${parecer.total_rejeitados} rejeitados, ` +
        `${parecer.total_info_ausente} sem informação`,
      tone: "success",
    });
  }

  // --- Rodadas do fornecedor ---
  for (const rodada of rodadas) {
    const tipoLabel = RODADA_TIPO_LABELS[rodada.tipo] ?? rodada.tipo;
    const statusLabel = RODADA_STATUS_LABELS[rodada.status] ?? rodada.status;
    const origem = rodada.documento_nome
      ? rodada.documento_nome
      : rodada.tem_texto_colado
        ? "texto colado"
        : "";
    entries.push({
      kind: "event",
      key: `rodada-${rodada.id}`,
      at: rodada.criado_em,
      title: `Rodada ${rodada.numero} do fornecedor`,
      detail: `${tipoLabel}${origem ? ` · ${origem}` : ""}${rodada.proposta_final ? " · proposta final" : ""} — ${statusLabel}`,
      tone: rodada.status === "ERRO" ? "error" : "neutral",
    });
  }

  // --- Verificação final validada (W5) ---
  if (verificacao?.validado_em && verificacao.resultado_validado) {
    entries.push({
      kind: "event",
      key: "verificacao-validada",
      at: verificacao.validado_em,
      title: "Verificação final validada",
      detail: RESULTADO_LABELS[verificacao.resultado_validado] ?? verificacao.resultado_validado,
      tone: verificacao.resultado_validado === "NAO_CONFORME" ? "warning" : "success",
    });
  }

  // --- Revisões de especificação aplicadas/descartadas (R4/W7) ---
  for (const versao of specVersoes) {
    if (versao.status === "APLICADA") {
      entries.push({
        kind: "event",
        key: `spec-${versao.id}`,
        at: versao.aplicado_em ?? versao.criado_em,
        title: `Revisão de especificação v${versao.numero_versao} aplicada`,
        detail: versao.resumo_diff?.resumo,
        tone: "warning",
      });
    } else if (versao.status === "DESCARTADA") {
      entries.push({
        kind: "event",
        key: `spec-${versao.id}`,
        at: versao.criado_em,
        title: `Revisão de especificação v${versao.numero_versao} descartada`,
      });
    }
  }

  // --- Fechamento (W6) ---
  if (parecer.fase_caso === "FECHADO" && parecer.fechado_em) {
    entries.push({
      kind: "event",
      key: "fechamento",
      at: parecer.fechado_em,
      title: "Caso fechado",
      detail: desfechoLabel(parecer.desfecho),
      tone: parecer.desfecho === "REPROVADO" ? "error" : "success",
    });
  }

  // --- Histórico do chat RAG ---
  for (const msg of chatHistory) {
    if (msg.papel === "user") {
      entries.push({
        kind: "user",
        key: `chat-${msg.id}`,
        at: msg.criado_em,
        text: msg.conteudo,
      });
    } else {
      entries.push({
        kind: "julia",
        key: `chat-${msg.id}`,
        at: msg.criado_em,
        markdown: msg.conteudo,
      });
      if (msg.gerou_nova_tabela) {
        // Selo de escrita no banco: vem da flag gravada pelo backend junto com a
        // ação, nunca da prosa da JulIA. O +1s fura o desempate de compareEntries
        // (event antes de chat) para o selo aparecer logo APÓS a fala.
        entries.push({
          kind: "event",
          key: `chat-${msg.id}-tabela`,
          at: new Date(new Date(msg.criado_em).getTime() + 1000).toISOString(),
          title: "Tabela do caso atualizada por esta resposta",
          detail: "Alteração gravada no banco — confira na Tabela do caso",
          tone: "success",
        });
      }
    }
  }

  return entries.sort(compareEntries);
}
