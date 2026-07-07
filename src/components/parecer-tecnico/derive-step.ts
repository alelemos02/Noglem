/**
 * deriveStep — função pura que decide o passo ativo da conversa a partir do
 * snapshot do backend + estado local da sessão.
 *
 * A ordem das verificações É a precedência do script (espelha a máquina de
 * estados de backend/app/services/state_machine.py):
 *
 *   SETUP → REQUISITOS → ANALISE → CICLO_FORNECEDOR → VERIFICACAO_FINAL → FECHADO
 *
 * A revisão de especificação (R4/W7) é lateral e bloqueia o resto enquanto
 * houver comparação em andamento ou decisão pendente.
 */

import type { Snapshot, ConversationStep } from "./types";

export function deriveStep(snapshot: Snapshot): ConversationStep {
  const {
    parecer,
    documentos,
    requisitosDraft,
    rodadas,
    resumo,
    verificacao,
    specVersoes,
  } = snapshot;
  const fase = parecer.fase_caso;
  // Só conta como "tem engenharia" um doc de engenharia efetivamente LIDO — um
  // upload de imagem/scan sem OCR (aviso_extracao) entra vazio e não pode ser a
  // base da análise. Mantém o usuário no passo de upload até enviar um legível.
  const temEng = documentos.some(
    (d) => d.tipo === "engenharia" && !d.aviso_extracao
  );
  const temForn = documentos.some((d) => d.tipo === "fornecedor");
  const complementaresResolvidos = parecer.complementares_resolvidos;

  // --- Revisão de especificação (lateral, precede tudo) ---
  const specPendente = specVersoes.find((v) => v.status === "AGUARDANDO_DECISAO");
  if (specPendente) return { id: "spec.diff_decisao", specVersao: specPendente };

  const specComparando = specVersoes.find((v) => v.status === "EM_COMPARACAO");
  if (specComparando) return { id: "spec.comparando", specVersao: specComparando };

  const specErro = specVersoes.find((v) => v.status === "ERRO");
  if (specErro) return { id: "spec.erro", specVersao: specErro };

  // --- Fechado (terminal) ---
  if (fase === "FECHADO") return { id: "caso.fechado" };

  // --- Análise em processamento / erro (vale para SETUP/REQUISITOS/ANALISE) ---
  if (parecer.status_processamento === "processando") {
    return { id: "analise.rodando" };
  }

  // --- Setup / Requisitos (W1) ---
  // Coleta conduzida pela conversa, nesta ordem:
  //   1. documento PRINCIPAL da engenharia (base de todo o parecer)
  //   2. documentos COMPLEMENTARES (referências/normas — anexa ou declara que não tem)
  //   3. extração (quantos requisitos) → aprovação
  // A proposta do FORNECEDOR só é pedida DEPOIS da aprovação (fase ANALISE), para
  // os requisitos serem extraídos do documento da engenharia sem o viés da proposta.
  if (fase === "SETUP" || fase === "REQUISITOS") {
    if (parecer.status_processamento === "erro") return { id: "analise.erro" };
    if (!temEng) return { id: "setup.docs_eng" };
    if (!complementaresResolvidos) return { id: "setup.docs_complementares" };
    // Rascunho persistido no BD: sobrevive a recargas (F5 idempotente)
    if (requisitosDraft.length > 0) {
      return { id: "requisitos.aprovar" };
    }
    return { id: "setup.extrair" };
  }

  // --- Análise (R1 concluída ou pendente de disparo) ---
  if (fase === "ANALISE") {
    if (parecer.status_processamento === "erro") return { id: "analise.erro" };
    // Rascunho tem prioridade: lista de requisitos reaberta para edição (ou
    // re-extração pós-aprovação) volta ao gate W1, mesmo já havendo análise.
    if (requisitosDraft.length > 0) return { id: "requisitos.aprovar" };
    if (parecer.total_itens > 0) return { id: "analise.resultado" };
    // Requisitos aprovados; a análise R1 precisa da proposta do fornecedor
    if (!temForn) return { id: "analise.docs_forn" };
    // Requisitos aprovados + proposta presente, mas análise ainda não rodou
    return { id: "analise.pronta" };
  }

  // --- Ciclo com fornecedor (W3/R2/W4) ---
  if (fase === "CICLO_FORNECEDOR") {
    // Rodada ativa tem prioridade: o fluxo dela precisa terminar primeiro
    const rodadaErro = rodadas.find((r) => r.status === "ERRO");
    if (rodadaErro) return { id: "ciclo.rodada_erro", rodada: rodadaErro };

    const rodadaVinculando = rodadas.find((r) => r.status === "RECEBIDA");
    if (rodadaVinculando)
      return { id: "ciclo.vinculando", rodada: rodadaVinculando };

    const rodadaReview = rodadas.find((r) => r.status === "VINCULACAO_SUGERIDA");
    if (rodadaReview)
      return { id: "ciclo.vinculacao_review", rodada: rodadaReview };

    const rodadaAvaliando = rodadas.find(
      (r) => r.status === "VINCULACAO_CONFIRMADA"
    );
    if (rodadaAvaliando)
      return { id: "ciclo.avaliando", rodada: rodadaAvaliando };

    // Itens aguardando decisão humana (W4)
    if (resumo?.tem_em_reavaliacao) return { id: "ciclo.decidir" };

    // Sem rodada ativa: aguardando resposta do fornecedor
    return { id: "ciclo.aguardando_fornecedor" };
  }

  // --- Verificação final (R3/W5) ---
  if (fase === "VERIFICACAO_FINAL") {
    if (verificacao) {
      if (verificacao.resultado_validado) return { id: "caso.fechar" };
      if (verificacao.status === "EM_VERIFICACAO")
        return { id: "verificacao.rodando" };
      if (verificacao.status === "AGUARDANDO_VALIDACAO")
        return { id: "verificacao.validar" };
      if (verificacao.ia_dispensada) return { id: "verificacao.dispensada" };
      // AGUARDANDO_PROPOSTA_FINAL (ou recém-criada sem dispensa)
      return { id: "verificacao.aguardando_proposta" };
    }
    // Snapshot ainda sem o registro (primeiro GET cria) — trata como aguardando
    return { id: "verificacao.aguardando_proposta" };
  }

  // Fallback defensivo: não deveria acontecer
  return { id: "setup.docs_eng" };
}
