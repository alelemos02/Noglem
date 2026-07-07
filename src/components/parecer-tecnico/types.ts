/**
 * Tipos do motor de conversa da JulIA.
 *
 * A conversa é 100% derivada do estado persistido no backend (mais um pequeno
 * estado local de sessão, como o draft de requisitos). Nada de "conversa salva":
 * refresh é idempotente por construção.
 */

import type {
  ParecerResponse,
  DocumentoResponse,
  RequisitoResponse,
  ItemParecerResponse,
  RodadaFornecedorResponse,
  CicloResumoResponse,
  ItemRevisaoResponse,
  VerificacaoFinalResponse,
  VersaoSpecResponse,
  ChatMessageResponse,
} from "@/lib/patec-api";

/** Snapshot completo do estado do caso, carregado do backend. */
export interface Snapshot {
  parecer: ParecerResponse;
  documentos: DocumentoResponse[];
  /** Requisitos aprovados (W1). */
  requisitos: RequisitoResponse[];
  /** Rascunho de requisitos persistido no BD (aprovado_em IS NULL). */
  requisitosDraft: RequisitoResponse[];
  itens: ItemParecerResponse[];
  rodadas: RodadaFornecedorResponse[];
  resumo: CicloResumoResponse | null;
  itensReavaliacao: ItemRevisaoResponse[];
  verificacao: VerificacaoFinalResponse | null;
  specVersoes: VersaoSpecResponse[];
  chatHistory: ChatMessageResponse[];
}

export type StepId =
  // Revisão de especificação (lateral, precede tudo)
  | "spec.diff_decisao"
  | "spec.comparando"
  | "spec.erro"
  // Setup / Requisitos (W1)
  | "setup.docs_eng"
  | "setup.docs_complementares"
  | "setup.docs_forn"
  | "setup.extrair"
  | "requisitos.aprovar"
  // Análise (R1/W2)
  | "analise.docs_forn"
  | "analise.pronta"
  | "analise.rodando"
  | "analise.erro"
  | "analise.resultado"
  // Ciclo com fornecedor (W3/R2/W4)
  | "ciclo.rodada_erro"
  | "ciclo.vinculando"
  | "ciclo.vinculacao_review"
  | "ciclo.avaliando"
  | "ciclo.decidir"
  | "ciclo.aguardando_fornecedor"
  // Verificação final (R3/W5)
  | "verificacao.dispensada"
  | "verificacao.aguardando_proposta"
  | "verificacao.rodando"
  | "verificacao.validar"
  // Fechamento (W6)
  | "caso.fechar"
  | "caso.fechado";

/** O passo ativo da conversa: a última mensagem da JulIA + widget interativo. */
export interface ConversationStep {
  id: StepId;
  /** Rodada relevante para os passos do ciclo. */
  rodada?: RodadaFornecedorResponse;
  /** Versão de spec relevante para os passos de revisão. */
  specVersao?: VersaoSpecResponse;
}

/** Widgets que podem ser invocados como mensagens efêmeras (comandos). */
export type EphemeralWidget =
  | { widget: "items-browser"; focusNumero?: number }
  | { widget: "rastreabilidade" }
  | {
      widget: "upload";
      tipo: "engenharia" | "fornecedor" | "anexo_engenharia";
      hint: string;
    }
  | { widget: "spec-upload" }
  | { widget: "reanalisar" }
  | { widget: "fechar" };

/** Entrada da timeline (passado congelado + histórico de chat RAG). */
export type TimelineEntry =
  | {
      kind: "julia";
      key: string;
      at: string;
      /** Markdown renderizado como fala da JulIA. */
      markdown: string;
    }
  | {
      kind: "user";
      key: string;
      at: string;
      text: string;
    }
  | {
      kind: "event";
      key: string;
      at: string;
      /** Título curto do evento de workflow (ex: "Documento recebido"). */
      title: string;
      /** Detalhe opcional (ex: nome do arquivo, contagens). */
      detail?: string;
      tone?: "neutral" | "success" | "warning" | "error";
    }
  | ({
      kind: "widget";
      key: string;
      at: string;
    } & EphemeralWidget);

/** Progresso de tarefa assíncrona (Celery via Redis). */
export interface TaskProgress {
  percent: number;
  message: string;
  stage: string;
}
