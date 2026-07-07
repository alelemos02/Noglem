/**
 * script.ts — roteiro PT-BR da JulIA.
 *
 * Cada passo da conversa tem um template de fala. Tom: amistosa, direta,
 * conduz o engenheiro pelo processo sem jargão desnecessário.
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
    `${saudacao()}! Sou a **JulIA**, sua assistente de engenharia. ` +
    `Vou te conduzir pelo parecer técnico **${parecer.numero_parecer}** ` +
    `(${parecer.projeto} · ${parecer.fornecedor}).`
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
      `A comparação da nova revisão da especificação terminou. ` +
      `Veja o que mudou e decida o que aplicar — itens alterados serão reabertos ` +
      `e itens removidos serão desativados (nunca apagados).`,
    "spec.comparando": () =>
      `Estou comparando a nova revisão da especificação contra os requisitos ` +
      `aprovados do caso. Já te mostro o que mudou.`,
    "spec.erro": () =>
      `Tive um problema ao comparar a nova revisão da especificação. ` +
      `Você pode tentar de novo ou descartar essa versão.`,

    // --- Setup / Requisitos ---
    "setup.docs_eng": () =>
      `Para começar, preciso do **documento principal da engenharia** — a ` +
      `requisição/especificação técnica que será a **base de todo o parecer**. ` +
      `Pode arrastar aqui embaixo. Depois que ele entrar, eu pergunto sobre ` +
      `documentos complementares (referências, normas) — esses ficam para o ` +
      `segundo momento.`,
    "setup.docs_complementares": () =>
      `Documento principal recebido. ✅ Antes de eu ler e extrair os requisitos: ` +
      `você tem **documentos complementares** (referências técnicas ou normas ` +
      `linkadas no documento principal)? Eles servem só como apoio — a análise ` +
      `continua baseada no documento principal. Se tiver, anexe pelo clipe aqui ` +
      `embaixo; se não tiver, é só me dizer que eu já começo a extração dos ` +
      `requisitos.`,
    "setup.docs_forn": () =>
      `Perfeito. Agora me envie a **proposta do fornecedor** ` +
      `(${parecer.fornecedor}), por favor.`,
    "setup.extrair": () =>
      `Recebi o documento da engenharia. Agora eu **leio a documentação e ` +
      `extraio a lista de requisitos** que vamos verificar na proposta. ` +
      `**Quantos requisitos você quer que eu extraia?** Me diga um número, ` +
      `ou se preferir eu escolho os mais relevantes para uma conversa mais ` +
      `fluida — é só responder aqui embaixo. A proposta do fornecedor a gente ` +
      `envia depois, na hora da análise.`,
    "requisitos.aprovar": () =>
      `Li os documentos e identifiquei os requisitos abaixo. Dê uma olhada: ` +
      `você pode **editar, remover ou me pedir ajustes**. Quando estiver bom, ` +
      `aprove — a lista aprovada vira a referência oficial da análise.`,

    // --- Análise ---
    "analise.docs_forn": () =>
      `Requisitos aprovados! ✅ Agora me envie a **proposta do ` +
      `${parecer.fornecedor}** para eu comparar cada requisito contra ela.`,
    "analise.pronta": () =>
      `Os **${requisitos.length} requisitos** estão aprovados. ` +
      `Posso iniciar a análise da proposta do ${parecer.fornecedor} contra eles?`,
    "analise.rodando": () =>
      `Estou comparando a proposta da **${parecer.fornecedor}** contra os ` +
      `requisitos aprovados. Isso leva alguns minutos — acompanhe o progresso abaixo.`,
    "analise.erro": () =>
      `A análise encontrou um erro. Podemos tentar novamente — se o problema ` +
      `persistir, verifique os documentos enviados.`,
    "analise.resultado": () => {
      const a = parecer.total_aprovados;
      const b = parecer.total_aprovados_comentarios;
      const c = parecer.total_rejeitados;
      const d = parecer.total_info_ausente;
      return (
        `Análise pronta! Dos **${parecer.total_itens} itens**: ` +
        `${a} aprovados, ${b} com comentários, ${c} rejeitados e ${d} sem informação. ` +
        `Veja o resumo abaixo — quando quiser, iniciamos o ciclo com o fornecedor.`
      );
    },

    // --- Ciclo com fornecedor ---
    "ciclo.rodada_erro": () =>
      `O processamento da última resposta do fornecedor falhou. ` +
      `Veja o detalhe abaixo e me envie de novo, por favor.`,
    "ciclo.vinculando": () =>
      `Recebi a resposta do fornecedor. Estou **identificando a quais itens ` +
      `do parecer cada trecho responde** — já te mostro as sugestões para você conferir.`,
    "ciclo.vinculacao_review": () =>
      `Aqui está o que identifiquei na resposta do fornecedor. **Confira os ` +
      `vínculos** — você pode corrigir ou remover qualquer um antes de eu avaliar ` +
      `as respostas.`,
    "ciclo.avaliando": () =>
      `Vínculos confirmados! Estou **avaliando cada resposta** do fornecedor ` +
      `contra o requisito correspondente. Um instante.`,
    "ciclo.decidir": () => {
      const m = itensReavaliacao.length;
      return (
        `O fornecedor respondeu **${m} ${m === 1 ? "item" : "itens"}**. ` +
        `Vamos decidir um por um — eu mostro a resposta e a minha avaliação, ` +
        `e **você dá a palavra final**.`
      );
    },
    "ciclo.aguardando_fornecedor": () => {
      const pendentes =
        resumo?.contagem_por_estado.find((c) => c.estado === "PENDENTE_FORNECEDOR")
          ?.total ?? 0;
      return (
        `Estamos aguardando o fornecedor responder ` +
        `**${pendentes} ${pendentes === 1 ? "item pendente" : "itens pendentes"}**. ` +
        `Você pode exportar a carta de pendências para enviar a ele, e quando a ` +
        `resposta chegar, é só me entregar aqui embaixo.`
      );
    },

    // --- Verificação final ---
    "verificacao.dispensada": () =>
      `Todos os itens foram resolvidos! Como a última resposta foi uma ` +
      `**proposta totalmente revisada (Tipo 1)**, eu já analisei esse documento ` +
      `nas rodadas — não preciso verificar de novo. Só falta a **sua validação final**.`,
    "verificacao.aguardando_proposta": () =>
      `Todos os itens foram resolvidos! Para fechar o caso com segurança, ` +
      `preciso da **proposta final consolidada** do fornecedor — vou verificar se ` +
      `ela incorpora tudo o que foi acordado nas rodadas.`,
    "verificacao.rodando": () =>
      `Estou verificando a proposta final contra os acordos das rodadas. ` +
      `Um instante.`,
    "verificacao.validar": () =>
      `Terminei a verificação da proposta final. Veja o resultado abaixo e ` +
      `**valide a conformidade** — a palavra final é sua.`,

    // --- Fechamento ---
    "caso.fechar": () =>
      `Verificação validada! Agora é só **fechar o caso** com o desfecho final.`,
    "caso.fechado": () =>
      `Caso encerrado: **${desfechoLabel(parecer.desfecho)}**. ` +
      `Obrigada por conduzir o processo comigo! Você pode exportar o parecer ` +
      `nos formatos abaixo ou me perguntar qualquer coisa sobre o caso.`,
  };

  return mensagens[step.id]();
}
