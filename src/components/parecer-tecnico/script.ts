/**
 * script.ts — roteiro PT-BR da JulIA.
 *
 * Cada passo da conversa tem um template de fala. Voz da JulIA: ela é a
 * ENGENHEIRA que conduz o parecer (não uma "assistente"/sistema). Primeira
 * pessoa, humana e próxima, mas técnica e precisa. Sem emojis no dia a dia —
 * só em ocasião muito especial (ex.: o fechamento do caso).
 */

import type { Snapshot, ConversationStep, StepId } from "./types";

export function saudacao(date = new Date()): string {
  const h = date.getHours();
  if (h < 6) return "Boa noite";
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

/** Mensagem de abertura da thread (sempre a primeira entrada da timeline). */
export function mensagemAbertura(snapshot: Snapshot): string {
  const { parecer } = snapshot;
  return (
    `${saudacao()}! Aqui é a **JulIA** — sou a engenheira que vai tocar com você o ` +
    `parecer técnico **${parecer.numero_parecer}** ` +
    `(${parecer.projeto} · ${parecer.fornecedor}). Pode contar comigo em cada etapa.`
  );
}

const DESFECHO_LABELS: Record<string, string> = {
  APROVADO: "Aprovado",
  COM_PENDENCIA: "Aprovado com pendência",
  REPROVADO: "Reprovado",
};

export function desfechoLabel(desfecho: string | null): string {
  return desfecho ? (DESFECHO_LABELS[desfecho] ?? desfecho) : "—";
}

/** Fala da JulIA para o passo ativo. */
export function mensagemDoPasso(
  step: ConversationStep,
  snapshot: Snapshot
): string {
  const { parecer, requisitos, resumo, itensReavaliacao } = snapshot;

  const mensagens: Record<StepId, () => string> = {
    // --- Revisão de especificação (lateral) ---
    "spec.diff_decisao": () =>
      `Terminei de comparar a nova revisão da especificação. Dá uma olhada no ` +
      `que mudou e me diz o que aplicar — os itens alterados eu reabro, e os ` +
      `removidos eu desativo (nunca apago nada).`,
    "spec.comparando": () =>
      `Já estou comparando a nova revisão contra os requisitos que a gente ` +
      `aprovou. Volto num instante com o que mudou.`,
    "spec.erro": () =>
      `Tropecei ao comparar a nova revisão da especificação. Podemos tentar de ` +
      `novo, ou você descarta essa versão — como preferir.`,

    // --- Setup / Requisitos ---
    "setup.docs_eng": () =>
      `Pra gente começar, me manda o **documento principal da engenharia** — a ` +
      `requisição/especificação que vai ser a **base de todo o parecer**. É só ` +
      `arrastar aqui embaixo. Assim que ele entrar, eu te pergunto sobre ` +
      `documentos complementares (referências, normas); esses ficam pra depois.`,
    "setup.docs_complementares": () =>
      `Recebi o documento principal. Antes de eu mergulhar nele e extrair os ` +
      `requisitos: você tem algum **documento complementar** — uma norma, uma ` +
      `referência citada no documento principal? Serve só de apoio; a análise ` +
      `continua em cima do documento principal. Se tiver, anexa pelo clipe aqui ` +
      `embaixo. Se não tiver, é só me falar que eu já começo a extração.`,
    "setup.docs_forn": () =>
      `Fechado. Agora me manda a **proposta do fornecedor** ` +
      `(${parecer.fornecedor}), por favor.`,
    "setup.extrair": () =>
      `Documento da engenharia recebido. Agora eu **leio tudo e levanto a lista ` +
      `de requisitos** que a gente vai conferir na proposta. **Quantos requisitos ` +
      `você quer que eu extraia?** Me diz um número — ou, se preferir, eu escolho ` +
      `os mais relevantes pra deixar a conversa mais leve. A proposta do ` +
      `fornecedor a gente vê depois, na hora da análise.`,
    "requisitos.aprovar": () =>
      `Li os documentos e levantei os requisitos abaixo. Dá uma olhada com calma: ` +
      `você pode **editar, remover ou me pedir ajustes**. Quando achar que está ` +
      `bom, aprova — a lista aprovada vira a referência oficial da análise.`,

    // --- Análise ---
    "analise.docs_forn": () =>
      `Requisitos aprovados. Agora me manda a **proposta do ` +
      `${parecer.fornecedor}** que eu comparo cada requisito contra ela.`,
    "analise.pronta": () =>
      `Os **${requisitos.length} requisitos** estão aprovados. ` +
      `Posso já iniciar a análise da proposta do ${parecer.fornecedor} contra eles?`,
    "analise.rodando": () =>
      `Estou comparando a proposta da **${parecer.fornecedor}** contra os ` +
      `requisitos aprovados. Leva alguns minutos — pode acompanhar o progresso abaixo.`,
    "analise.erro": () =>
      `A análise esbarrou num erro. A gente pode tentar de novo — se insistir, ` +
      `vale conferir os documentos que foram enviados.`,
    "analise.resultado": () => {
      const a = parecer.total_aprovados;
      const b = parecer.total_aprovados_comentarios;
      const c = parecer.total_rejeitados;
      const d = parecer.total_info_ausente;
      return (
        `Terminei a análise! Dos **${parecer.total_itens} itens**: ` +
        `${a} aprovados, ${b} com comentários, ${c} rejeitados e ${d} sem informação. ` +
        `Dá uma olhada no resumo abaixo — quando você quiser, a gente inicia o ciclo com o fornecedor.`
      );
    },

    // --- Ciclo com fornecedor ---
    "ciclo.rodada_erro": () =>
      `O processamento da última resposta do fornecedor falhou. ` +
      `Dá uma olhada no detalhe abaixo e me reenvia, por favor.`,
    "ciclo.vinculando": () =>
      `Recebi a resposta do fornecedor. Estou **identificando a quais itens ` +
      `do parecer cada trecho responde** — já te mostro pra você conferir.`,
    "ciclo.vinculacao_review": () =>
      `Aqui está o que consegui identificar na resposta do fornecedor. **Confere ` +
      `os vínculos** — você pode corrigir ou tirar qualquer um antes de eu avaliar ` +
      `as respostas.`,
    "ciclo.avaliando": () =>
      `Vínculos confirmados. Estou **avaliando cada resposta** do fornecedor ` +
      `contra o requisito correspondente. Um instante.`,
    "ciclo.decidir": () => {
      const m = itensReavaliacao.length;
      return (
        `O fornecedor respondeu **${m} ${m === 1 ? "item" : "itens"}**. ` +
        `Vamos decidir um por um — eu te mostro a resposta e a minha avaliação, ` +
        `e **a palavra final é sua**.`
      );
    },
    "ciclo.aguardando_fornecedor": () => {
      const pendentes =
        resumo?.contagem_por_estado.find((c) => c.estado === "PENDENTE_FORNECEDOR")
          ?.total ?? 0;
      return (
        `Estamos esperando o fornecedor responder ` +
        `**${pendentes} ${pendentes === 1 ? "item pendente" : "itens pendentes"}**. ` +
        `Se quiser, exporta a carta de pendências pra mandar pra ele; quando a ` +
        `resposta chegar, é só me entregar aqui embaixo.`
      );
    },

    // --- Verificação final ---
    "verificacao.dispensada": () =>
      `Todos os itens foram resolvidos! Como a última resposta já veio como ` +
      `**proposta totalmente revisada (Tipo 1)**, eu analisei esse documento nas ` +
      `rodadas — não preciso verificar de novo. Falta só a **sua validação final**.`,
    "verificacao.aguardando_proposta": () =>
      `Todos os itens foram resolvidos! Pra fechar o caso com segurança, ` +
      `preciso da **proposta final consolidada** do fornecedor — vou conferir se ` +
      `ela incorpora tudo o que foi acordado nas rodadas.`,
    "verificacao.rodando": () =>
      `Estou verificando a proposta final contra os acordos das rodadas. ` +
      `Um instante.`,
    "verificacao.validar": () =>
      `Terminei a verificação da proposta final. Dá uma olhada no resultado ` +
      `abaixo e **valida a conformidade** — a palavra final é sua.`,

    // --- Fechamento ---
    "caso.fechar": () =>
      `Verificação validada! Agora é só **fechar o caso** com o desfecho final.`,
    "caso.fechado": () =>
      `Caso encerrado: **${desfechoLabel(parecer.desfecho)}**. ` +
      `Obrigada por conduzir isso comigo — foi um bom trabalho! 🎉 Você pode ` +
      `exportar o parecer nos formatos abaixo, ou me perguntar qualquer coisa sobre o caso.`,
  };

  return mensagens[step.id]();
}
