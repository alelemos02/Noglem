/**
 * commands.ts — comandos de texto da JulIA (match por palavra-chave, PT-BR
 * tolerante a acentos). O que não casar aqui vai para o chat RAG.
 */

import type { useConversation } from "./conversation-provider";
import type { EphemeralWidget } from "./types";
import { faseLabel } from "./phase-line";

type Conversation = ReturnType<typeof useConversation>;

export interface Command {
  run: (c: Conversation) => Promise<void>;
}

function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .trim();
}

function pushWidget(c: Conversation, widget: EphemeralWidget) {
  c.pushEphemeral({
    kind: "widget",
    key: `cmd-${widget.widget}-${Date.now()}`,
    at: new Date().toISOString(),
    ...widget,
  });
}

function pushJulia(c: Conversation, markdown: string) {
  c.pushEphemeral({
    kind: "julia",
    key: `cmd-julia-${Date.now()}`,
    at: new Date().toISOString(),
    markdown,
  });
}

function uploadPrompt(c: Conversation): {
  tipo: "engenharia" | "fornecedor" | "anexo_engenharia";
  hint: string;
  texto: string;
} {
  const stepId = c.step?.id;
  if (
    stepId === "analise.docs_forn" ||
    stepId === "ciclo.aguardando_fornecedor" ||
    stepId === "verificacao.aguardando_proposta"
  ) {
    return {
      tipo: "fornecedor",
      hint: "Proposta, resposta ou documento do fornecedor",
      texto:
        "Você pode anexar o arquivo pelo clipe na caixa de conversa ou usar a área de upload abaixo. Vou registrar como documento do fornecedor.",
    };
  }

  return {
    tipo: "engenharia",
    hint: "Documentos da engenharia (requisição técnica, folha de dados)",
    texto:
      "Você pode anexar o arquivo pelo clipe na caixa de conversa ou usar a área de upload abaixo. Vou registrar como documento da engenharia.",
  };
}

export function matchCommand(text: string): Command | null {
  const t = normalize(text);

  if (
    /\b(upload|carregar|enviar|anexar|subir)\b/.test(t) &&
    /\b(arquivo|arquivos|documento|documentos|pdf|docx|xlsx|imagem|imagens|foto|fotos|anexo|anexos|proposta|requisicao|especificacao)\b/.test(t)
  ) {
    return {
      run: async (c) => {
        const prompt = uploadPrompt(c);
        pushJulia(c, prompt.texto);
        pushWidget(c, {
          widget: "upload",
          tipo: prompt.tipo,
          hint: prompt.hint,
        });
      },
    };
  }

  // exportar pdf|xlsx|docx
  const exportMatch = t.match(/^exportar?\s+(pdf|xlsx|excel|docx|word)$/);
  if (exportMatch) {
    const fmt =
      exportMatch[1] === "excel"
        ? "xlsx"
        : exportMatch[1] === "word"
          ? "docx"
          : (exportMatch[1] as "pdf" | "xlsx" | "docx");
    return { run: async (c) => c.exportar(fmt).catch(() => {}) };
  }

  // carta de pendências
  if (/^(exportar?\s+|baixar?\s+)?carta(\s+de\s+pendencias?)?$/.test(t)) {
    return { run: async (c) => c.downloadCarta().catch(() => {}) };
  }

  // ver item N / item N
  const itemMatch = t.match(/^(ver\s+|mostrar?\s+|abrir?\s+)?item\s+#?(\d+)$/);
  if (itemMatch) {
    const numero = parseInt(itemMatch[2], 10);
    return {
      run: async (c) => pushWidget(c, { widget: "items-browser", focusNumero: numero }),
    };
  }

  // ver itens / itens / listar itens
  if (/^(ver\s+|mostrar?\s+|listar?\s+)?(os\s+)?itens$/.test(t)) {
    return { run: async (c) => pushWidget(c, { widget: "items-browser" }) };
  }

  // rastreabilidade / cobertura — mapa requisito -> item
  if (/^(ver\s+|mostrar?\s+)?(rastreabilidade|cobertura)$/.test(t)) {
    return { run: async (c) => pushWidget(c, { widget: "rastreabilidade" }) };
  }

  // ver tabela / tabela / ver banco — abre a visualização do banco de dados
  if (/^(ver\s+|abrir?\s+|mostrar?\s+)?(a\s+)?(tabela|banco(\s+de\s+dados)?)$/.test(t)) {
    return {
      run: async (c) => {
        c.setShowDataPanel(true);
      },
    };
  }

  // revisar especificação / nova revisão
  if (
    /^(revisar?|atualizar?)\s+(a\s+)?(especificacao|spec)$/.test(t) ||
    /^nova\s+revisao(\s+da\s+(especificacao|spec))?$/.test(t)
  ) {
    return { run: async (c) => pushWidget(c, { widget: "spec-upload" }) };
  }

  // reanalisar
  if (/^reanalisar?(\s+proposta)?$/.test(t)) {
    return { run: async (c) => pushWidget(c, { widget: "reanalisar" }) };
  }

  // editar a lista de requisitos (reabre a tabela editável, fase ANALISE)
  if (/^(editar|alterar|revisar|ajustar)\s+(a\s+)?(lista\s+de\s+)?requisitos$/.test(t)) {
    return {
      run: async (c) =>
        c.reabrirRequisitos().catch(() => {
          pushJulia(
            c,
            "Não consegui reabrir os requisitos. A edição da lista só vale antes de iniciar o ciclo com o fornecedor — depois, use **revisar especificação**."
          );
        }),
    };
  }

  // fechar caso (W6, inclusive caso travado no ciclo)
  if (/^(fechar|encerrar)\s+(o\s+)?caso$/.test(t)) {
    return { run: async (c) => pushWidget(c, { widget: "fechar" }) };
  }

  // status / onde estamos
  if (/^(status|onde\s+estamos\??|resumo(\s+do\s+caso)?)$/.test(t)) {
    return {
      run: async (c) => {
        const s = c.snapshot;
        if (!s) return;
        const p = s.parecer;
        const linhas = [
          `**${p.numero_parecer}** (${p.projeto} · ${p.fornecedor}) — fase **${faseLabel(p.fase_caso)}**.`,
        ];
        if (p.total_itens > 0) {
          linhas.push(
            `${p.total_itens} itens: ${p.total_aprovados} aprovados, ` +
              `${p.total_aprovados_comentarios} c/ comentários, ${p.total_rejeitados} rejeitados, ` +
              `${p.total_info_ausente} sem informação.`
          );
        }
        if (s.resumo) {
          const estados = s.resumo.contagem_por_estado
            .filter((e) => e.total > 0)
            .map((e) => `${e.total} ${e.estado.toLowerCase().replace(/_/g, " ")}`)
            .join(", ");
          if (estados) linhas.push(`Ciclo: ${estados}.`);
        }
        if (p.desfecho) linhas.push(`Desfecho: **${p.desfecho}**.`);
        pushJulia(c, linhas.join("\n\n"));
      },
    };
  }

  // ajuda
  if (/^(ajuda|help|comandos|\?)$/.test(t)) {
    return {
      run: async (c) =>
        pushJulia(
          c,
          "Posso te ajudar com:\n\n" +
            "- **ver tabela** — a tabela do caso, direto do banco de dados\n" +
            "- **ver itens** / **ver item 4** — navegar pelos itens do parecer\n" +
            "- **rastreabilidade** — cobertura requisito → item (o que ficou sem análise)\n" +
            "- **status** — resumo de onde estamos\n" +
            "- **exportar pdf / xlsx / docx** — baixar o parecer\n" +
            "- **carta** — baixar a carta de pendências\n" +
            "- **editar requisitos** — rever/alterar a lista de requisitos e reavaliar\n" +
            "- **revisar especificação** — subir nova revisão da spec\n" +
            "- **reanalisar** — rodar a análise de novo\n" +
            "- **fechar caso** — registrar o desfecho final\n\n" +
            "Ou me pergunte qualquer coisa sobre os documentos do caso. 💬"
        ),
    };
  }

  return null;
}
