/**
 * PATEC API client.
 * All calls go through /api/parecer-tecnico/ proxy.
 */

// --- Request helpers ---

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const r = payload as Record<string, unknown>;
  if (typeof r.detail === "string") return r.detail;
  if (r.error && typeof r.error === "object") {
    const nested = r.error as Record<string, unknown>;
    if (typeof nested.message === "string") return nested.message;
  }
  if (typeof r.message === "string") return r.message;
  return fallback;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const response = await fetch(`/api/parecer-tecnico${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extractErrorMessage(error, `Erro ${response.status}`));
  }

  return response.json();
}

// --- Types ---

export interface ParecerResponse {
  id: string;
  numero_parecer: string;
  projeto: string;
  fornecedor: string;
  revisao: string;
  disciplina: string;
  idioma_relatorio: ReportLanguage;
  status_processamento: string;
  parecer_geral: string | null;
  comentario_geral: string | null;
  conclusao: string | null;
  total_itens: number;
  total_aprovados: number;
  total_aprovados_comentarios: number;
  total_rejeitados: number;
  total_info_ausente: number;
  total_itens_adicionais: number;
  fase_caso: FaseCaso;
  complementares_resolvidos: boolean;
  desfecho: Desfecho | null;
  fechado_em: string | null;
  motivo_fechamento: string | null;
  criado_em: string;
  atualizado_em: string;
}

export type Desfecho = "APROVADO" | "COM_PENDENCIA" | "REPROVADO";

export type DecisaoHumana = "ACEITAR" | "ESCLARECER" | "REJEITAR" | "REPROVAR_CASO";

export type FaseCaso =
  | "SETUP"
  | "REQUISITOS"
  | "ANALISE"
  | "CICLO_FORNECEDOR"
  | "VERIFICACAO_FINAL"
  | "FECHADO";

export interface ParecerListResponse {
  items: ParecerResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface ParecerCreate {
  numero_parecer: string;
  projeto: string;
  fornecedor: string;
  revisao?: string;
  disciplina?: string;
  idioma_relatorio?: ReportLanguage;
}

export type ExportFormat = "pdf" | "xlsx" | "docx";
export type PerfilAnalise = "simples" | "padrao" | "completa" | string;
export type ReportLanguage = "pt" | "es" | "en";

export interface DocumentoResponse {
  id: string;
  parecer_id: string;
  tipo: string;
  nome_arquivo: string;
  tipo_arquivo: string;
  tamanho_bytes: number | null;
  criado_em: string;
  // Aviso quando a extração rendeu pouco/nenhum texto (imagem sem OCR, PDF
  // escaneado, arquivo vazio). null/ausente quando o documento foi lido ok.
  aviso_extracao?: string | null;
}

export interface RastreabilidadeLinha {
  requisito_numero: number;
  requisito_descricao: string;
  requisito_valor: string | null;
  requisito_prioridade: string | null;
  referencia_engenharia: string | null;
  item_numero: number | null;
  item_status: string | null;
  cobertura: "coberto" | "revisar";
}

export interface RastreabilidadeResponse {
  total_requisitos: number;
  cobertos: number;
  a_revisar: number;
  linhas: RastreabilidadeLinha[];
}

export interface QualidadeResponse {
  pareceres: {
    total: number;
    analisados: number;
    por_disciplina: Record<string, number>;
    por_desfecho: Record<string, number>;
  };
  itens: {
    total: number;
    media_por_parecer: number;
    por_status: Record<string, number>;
  };
  qualidade: {
    correcao_manual: { itens: number; taxa: number };
    requisitos_nao_cobertos: { itens: number; taxa: number };
    verificador_correcoes: number;
    consistencia_flags: number;
  };
}

export type UploadPhase = "queued" | "uploading" | "processing" | "done" | "error";

export interface UploadProgress {
  phase: UploadPhase;
  percent: number | null;
}

export interface ItemParecerResponse {
  id: string;
  parecer_id: string;
  numero: number;
  categoria: string | null;
  descricao_requisito: string;
  referencia_engenharia: string | null;
  referencia_fornecedor: string | null;
  valor_requerido: string | null;
  valor_fornecedor: string | null;
  status: string;
  justificativa_tecnica: string;
  acao_requerida: string | null;
  prioridade: string | null;
  norma_referencia: string | null;
  editado_manualmente: boolean;
  estado: string;
  marcacao_revisao: "NOVO" | "ALTERADO" | null;
  verificacao_flag: string | null;
  verificacao_nota: string | null;
  criado_em: string;
  atualizado_em: string;
}

export interface RodadaAvaliacaoResponse {
  id: string;
  numero_rodada: number;
  origem: "PROPOSTA_INICIAL" | "RESPOSTA_FORNECEDOR" | "COMENTARIO_ENGENHARIA";
  conteudo: string | null;
  anexo_ref: string | null;
  classificacao_ia: string | null;
  veredito_ia: "ATENDE" | "PARCIAL" | "NAO_ATENDE" | null;
  justificativa_ia: string | null;
  acao_requerida: string | null;
  decisao_humana: DecisaoHumana | null;
  revisor: string | null;
  criado_em: string;
}

export interface ItemRevisaoResponse {
  id: string;
  numero: number;
  categoria: string | null;
  descricao_requisito: string;
  valor_requerido: string | null;
  prioridade: string | null;
  estado: string;
  ultima_rodada: RodadaAvaliacaoResponse | null;
}

export interface CicloResumoResponse {
  fase_caso: FaseCaso;
  desfecho: Desfecho | null;
  contagem_por_estado: { estado: string; total: number }[];
  total_itens: number;
  tem_pendentes: boolean;
  tem_em_reavaliacao: boolean;
  todos_aceitos: boolean;
}

export interface DecisoHumanaResponse {
  item_id: string;
  numero: number;
  novo_estado: string;
  fase_caso: FaseCaso;
  desfecho: Desfecho | null;
  mensagem: string;
}

export interface ReimportResultResponse {
  processados: { item_id: string; numero: number; veredito_ia: string }[];
  ignorados: { linha: number; motivo: string }[];
  total_processados: number;
  total_ignorados: number;
  mensagem: string;
}

export type TipoRodada =
  | "PROPOSTA_REVISADA"
  | "RESPOSTA_ITENS"
  | "RESPOSTA_ITENS_PROPOSTA_POSTERIOR"
  | "EMAIL_AVULSO";

export type StatusRodada =
  | "RECEBIDA"
  | "VINCULACAO_SUGERIDA"
  | "VINCULACAO_CONFIRMADA"
  | "AVALIADA"
  | "ERRO";

export interface RodadaFornecedorResponse {
  id: string;
  numero: number;
  tipo: TipoRodada;
  status: StatusRodada;
  proposta_final: boolean;
  tem_texto_colado: boolean;
  documento_nome: string | null;
  erro_detalhe: string | null;
  criado_em: string;
}

export interface VinculoResponse {
  id: string;
  item_id: string;
  item_numero: number;
  item_descricao: string;
  item_estado: string;
  trecho: string | null;
  confianca: "ALTA" | "MEDIA" | "BAIXA" | null;
  metodo: "LLM" | "MANUAL" | "DETERMINISTICO" | null;
  veredito_ia: string | null;
  justificativa_ia: string | null;
}

export interface RodadaDetalheResponse extends RodadaFornecedorResponse {
  vinculos: VinculoResponse[];
}

export interface RodadaProgressoResponse {
  status: StatusRodada;
  percent: number | null;
  message: string | null;
  stage: string | null;
}

export type ResultadoValidado = "CONFORME" | "CONFORME_COM_PENDENCIA" | "NAO_CONFORME";

export interface SpecDiffAlterado {
  numero: number;
  campos_alterados: Record<string, { antes: string; depois: string }>;
  justificativa: string;
}

export interface SpecDiffNovo {
  categoria: string | null;
  descricao_requisito: string;
  valor_requerido: string | null;
  prioridade: "ALTA" | "MEDIA" | "BAIXA";
  norma_referencia: string | null;
  referencia_engenharia: string;
}

export interface VersaoSpecResponse {
  id: string;
  numero_versao: number;
  status: "EM_COMPARACAO" | "AGUARDANDO_DECISAO" | "APLICADA" | "DESCARTADA" | "ERRO";
  cenario: "A" | "B" | "C" | null;
  resumo_diff: {
    inalterados: number[];
    alterados: SpecDiffAlterado[];
    novos: SpecDiffNovo[];
    removidos: number[];
    resumo: string;
    cenario: string;
  } | null;
  erro_detalhe: string | null;
  fase_caso_anterior: string | null;
  aplicado_em: string | null;
  criado_em: string;
}

export interface VerificacaoFinalResponse {
  id: string;
  ia_dispensada: boolean;
  status: string;
  rodada_fornecedor_id: string | null;
  resultado_ia: {
    itens: { numero: number; conformidade: string; evidencia: string; observacao: string }[];
    resumo: string;
  } | null;
  resultado_validado: ResultadoValidado | null;
  observacoes: string | null;
  validado_em: string | null;
}

export interface ItemParecerUpdate {
  status?: string;
  justificativa_tecnica?: string;
  acao_requerida?: string;
  prioridade?: string;
  categoria?: string;
  descricao_requisito?: string;
  valor_requerido?: string;
  valor_fornecedor?: string;
  norma_referencia?: string;
}

export interface RecomendacaoResponse {
  id: string;
  parecer_id: string;
  texto: string;
  ordem: number;
}

export interface AnaliseResponse {
  task_id: string;
  message: string;
}

export interface StatusAnaliseResponse {
  status_processamento: string;
  task_state: string | null;
  message: string | null;
  stage: string | null;
  progress_percent: number | null;
  parecer_geral: string | null;
  total_itens: number;
}

export interface RequisitoBase {
  numero: number;
  categoria: string | null;
  descricao_requisito: string;
  referencia_engenharia: string | null;
  valor_requerido: string | null;
  prioridade: "ALTA" | "MEDIA" | "BAIXA";
  norma_referencia: string | null;
}

export interface RequisitoResponse extends RequisitoBase {
  id: string;
  parecer_id: string;
  versao: number;
  ativo: boolean;
  aprovado_em: string | null;
  criado_em: string;
}

export interface ExtracaoRequisitosResponse {
  requisitos: RequisitoBase[];
  total_itens: number;
  resumo: string;
}

export interface RequisitosAprovadosResponse {
  requisitos: RequisitoResponse[];
  total_itens: number;
  fase_caso: FaseCaso;
}

export interface RevisaoResponse {
  id: string;
  parecer_id: string;
  numero_revisao: number;
  motivo: string | null;
  criado_por: string | null;
  parecer_geral: string | null;
  comentario_geral: string | null;
  conclusao: string | null;
  total_itens: number;
  total_aprovados: number;
  total_aprovados_comentarios: number;
  total_rejeitados: number;
  total_info_ausente: number;
  total_itens_adicionais: number;
  criado_em: string;
}

export interface RevisaoListResponse {
  items: RevisaoResponse[];
  total: number;
}

export interface RevisaoCompareResponse {
  revisao_a: RevisaoResponse;
  revisao_b: RevisaoResponse;
  diferencas: {
    resumo: Record<string, { de: unknown; para: unknown }>;
    itens_adicionados: number;
    itens_removidos: number;
    itens_alterados: {
      numero: number;
      alteracoes: Record<string, { de: unknown; para: unknown }>;
    }[];
  };
}

export interface ChatMessageResponse {
  id: string;
  papel: "user" | "assistant";
  conteudo: string;
  ordem: number;
  gerou_nova_tabela: boolean;
  criado_em: string;
}

/** Estado do fluxo enviado ao chat (modo JULIA). */
export interface ChatContextoFluxo {
  fase_caso?: string;
  step_id?: string;
  requisitos_draft?: RequisitoBase[];
}

/** Ação estruturada emitida pela JULIA via chat (já aplicada no BD pelo backend). */
export type ChatAction = {
  tipo:
    | "atualizar_requisitos"
    | "atualizar_itens"
    | "aprovar_requisitos"
    | "iniciar_ciclo"
    | "revisar_especificacao"
    | "reanalisar"
    | "reabrir_requisitos"
    | "extrair_requisitos"
    | "confirmar_complementares";
  total?: number;
  fase_caso?: FaseCaso;
  perfil?: string;
  escopo?: string | null;
} & Record<string, unknown>;

export interface ChatHistoryResponse {
  messages: ChatMessageResponse[];
  total: number;
}

export interface EstimativaCustoResponse {
  total_caracteres: number;
  tokens_estimados_entrada: number;
  tokens_estimados_saida: number;
  num_chamadas_api: number;
  custo_estimado_usd: number;
  custo_estimado_brl: number;
  modelo: string;
  aviso: string | null;
}

// --- API ---

export const patecApi = {
  pareceres: {
    list(params?: { page?: number; projeto?: string; fornecedor?: string; status_processamento?: string }) {
      const query = new URLSearchParams();
      if (params?.page) query.set("page", String(params.page));
      if (params?.projeto) query.set("projeto", params.projeto);
      if (params?.fornecedor) query.set("fornecedor", params.fornecedor);
      if (params?.status_processamento) query.set("status_processamento", params.status_processamento);
      const qs = query.toString();
      return request<ParecerListResponse>(`/v1/pareceres${qs ? `?${qs}` : ""}`);
    },
    get(id: string) {
      return request<ParecerResponse>(`/v1/pareceres/${id}`);
    },
    create(data: ParecerCreate) {
      return request<ParecerResponse>("/v1/pareceres", {
        method: "POST",
        body: JSON.stringify(data),
      });
    },
    update(id: string, data: Partial<ParecerCreate>) {
      return request<ParecerResponse>(`/v1/pareceres/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      });
    },
    delete(id: string) {
      return request<void>(`/v1/pareceres/${id}`, { method: "DELETE" });
    },
    // Gate de setup: marca que os documentos complementares foram resolvidos
    // (anexados ou declarados inexistentes) — libera a etapa do fornecedor.
    confirmarComplementares(id: string) {
      return request<ParecerResponse>(
        `/v1/pareceres/${id}/complementares-resolvidos`,
        { method: "POST" }
      );
    },
  },
  documentos: {
    list(parecerId: string) {
      return request<DocumentoResponse[]>(`/v1/pareceres/${parecerId}/documentos`);
    },
    async upload(
      parecerId: string,
      tipo: "engenharia" | "fornecedor" | "anexo_engenharia",
      file: File,
      onProgress?: (progress: UploadProgress) => void
    ) {
      const formData = new FormData();
      formData.append("file", file);
      onProgress?.({ phase: "queued", percent: 0 });

      return new Promise<DocumentoResponse>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open(
          "POST",
          `/api/parecer-tecnico/v1/pareceres/${parecerId}/documentos/${tipo}`
        );

        xhr.upload.onprogress = (event) => {
          if (!event.lengthComputable) {
            onProgress?.({ phase: "uploading", percent: null });
            return;
          }
          onProgress?.({
            phase: "uploading",
            percent: Math.min(99, Math.round((event.loaded / event.total) * 100)),
          });
        };

        xhr.upload.onload = () => {
          onProgress?.({ phase: "processing", percent: 100 });
        };

        xhr.onload = () => {
          let body: unknown = null;
          try {
            body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
          } catch {
            body = null;
          }
          if (xhr.status >= 200 && xhr.status < 300 && body) {
            onProgress?.({ phase: "done", percent: 100 });
            resolve(body as DocumentoResponse);
            return;
          }
          onProgress?.({ phase: "error", percent: null });
          reject(new Error(extractErrorMessage(body, `Erro ${xhr.status}`)));
        };

        xhr.onerror = () => {
          onProgress?.({ phase: "error", percent: null });
          reject(new Error("Erro de rede ao enviar arquivo"));
        };

        xhr.send(formData);
      });
    },
    async delete(parecerId: string, docId: string) {
      const response = await fetch(
        `/api/parecer-tecnico/v1/pareceres/${parecerId}/documentos/${docId}`,
        { method: "DELETE" }
      );
      if (!response.ok) throw new Error("Erro ao remover documento");
    },
  },
  analise: {
    iniciar(parecerId: string, perfilAnalise: PerfilAnalise = "padrao") {
      return request<AnaliseResponse>(`/v1/pareceres/${parecerId}/analisar`, {
        method: "POST",
        body: JSON.stringify({ perfil_analise: perfilAnalise }),
      });
    },
    status(parecerId: string) {
      return request<StatusAnaliseResponse>(`/v1/pareceres/${parecerId}/status`);
    },
  },
  requisitos: {
    extrair(parecerId: string, perfilAnalise: PerfilAnalise = "padrao", feedback?: string) {
      return request<ExtracaoRequisitosResponse>(
        `/v1/pareceres/${parecerId}/requisitos/extrair`,
        {
          method: "POST",
          body: JSON.stringify({
            perfil_analise: perfilAnalise,
            ...(feedback ? { feedback } : {}),
          }),
        }
      );
    },
    list(parecerId: string) {
      return request<RequisitoResponse[]>(`/v1/pareceres/${parecerId}/requisitos`);
    },
    draft(parecerId: string) {
      return request<RequisitoResponse[]>(
        `/v1/pareceres/${parecerId}/requisitos/draft`
      );
    },
    salvarDraft(parecerId: string, requisitos: RequisitoBase[]) {
      return request<RequisitoResponse[]>(
        `/v1/pareceres/${parecerId}/requisitos/draft`,
        { method: "PUT", body: JSON.stringify({ requisitos }) }
      );
    },
    aprovar(parecerId: string, requisitos: RequisitoBase[]) {
      return request<RequisitosAprovadosResponse>(
        `/v1/pareceres/${parecerId}/requisitos/aprovar`,
        { method: "POST", body: JSON.stringify({ requisitos }) }
      );
    },
    reabrir(parecerId: string) {
      // Reabre os requisitos aprovados como rascunho editável (fase ANALISE)
      return request<RequisitoResponse[]>(
        `/v1/pareceres/${parecerId}/requisitos/reabrir`,
        { method: "POST" }
      );
    },
    update(parecerId: string, requisitoId: string, data: Partial<RequisitoBase>) {
      return request<RequisitoResponse>(
        `/v1/pareceres/${parecerId}/requisitos/${requisitoId}`,
        { method: "PATCH", body: JSON.stringify(data) }
      );
    },
  },
  exportacoes: {
    async download(parecerId: string, formato: ExportFormat) {
      const response = await fetch(
        `/api/parecer-tecnico/v1/pareceres/${parecerId}/exportar/${formato}`
      );
      if (!response.ok) {
        const error = await response.clone().json().catch(() => null);
        throw new Error(extractErrorMessage(error, `Erro ${response.status}`));
      }
      const blob = await response.blob();
      const cd = response.headers.get("content-disposition") || "";
      const match = cd.match(/filename="?([^";]+)"?/i);
      const filename = match?.[1] || `parecer.${formato}`;
      return { blob, filename };
    },
  },
  itens: {
    list(parecerId: string, params?: { status?: string; categoria?: string; prioridade?: string; busca?: string }) {
      const query = new URLSearchParams();
      if (params?.status) query.set("status", params.status);
      if (params?.categoria) query.set("categoria", params.categoria);
      if (params?.prioridade) query.set("prioridade", params.prioridade);
      if (params?.busca) query.set("busca", params.busca);
      const qs = query.toString();
      return request<ItemParecerResponse[]>(
        `/v1/pareceres/${parecerId}/itens${qs ? `?${qs}` : ""}`
      );
    },
    update(parecerId: string, itemId: string, data: ItemParecerUpdate) {
      return request<ItemParecerResponse>(
        `/v1/pareceres/${parecerId}/itens/${itemId}`,
        { method: "PUT", body: JSON.stringify(data) }
      );
    },
    rastreabilidade(parecerId: string) {
      return request<RastreabilidadeResponse>(
        `/v1/pareceres/${parecerId}/rastreabilidade`
      );
    },
  },
  recomendacoes: {
    list(parecerId: string) {
      return request<RecomendacaoResponse[]>(`/v1/pareceres/${parecerId}/recomendacoes`);
    },
  },
  revisoes: {
    list(parecerId: string) {
      return request<RevisaoListResponse>(`/v1/pareceres/${parecerId}/revisoes`);
    },
    create(parecerId: string, data: { motivo?: string }) {
      return request<RevisaoResponse>(`/v1/pareceres/${parecerId}/revisoes`, {
        method: "POST",
        body: JSON.stringify(data),
      });
    },
    comparar(parecerId: string, revA: number, revB: number) {
      return request<RevisaoCompareResponse>(
        `/v1/pareceres/${parecerId}/revisoes/comparar/${revA}/${revB}`
      );
    },
  },
  estimativa: {
    getCusto(parecerId: string) {
      return request<EstimativaCustoResponse>(`/v1/pareceres/${parecerId}/estimativa-custo`);
    },
  },
  ciclo: {
    resumo(parecerId: string) {
      return request<CicloResumoResponse>(`/v1/pareceres/${parecerId}/ciclo/resumo`);
    },
    itensEmReavaliacao(parecerId: string) {
      return request<ItemRevisaoResponse[]>(`/v1/pareceres/${parecerId}/ciclo/reavaliacao`);
    },
    itensDoCiclo(parecerId: string) {
      // Todos os itens do ciclo (decididos + pendentes) com a última rodada.
      return request<ItemRevisaoResponse[]>(`/v1/pareceres/${parecerId}/ciclo/itens`);
    },
    iniciar(parecerId: string) {
      return request<{ fase_caso: FaseCaso; mensagem: string }>(
        `/v1/pareceres/${parecerId}/ciclo/iniciar`,
        { method: "POST" }
      );
    },
    decidir(parecerId: string, itemId: string, decisao: DecisaoHumana, comentario?: string) {
      return request<DecisoHumanaResponse>(
        `/v1/pareceres/${parecerId}/ciclo/itens/${itemId}/decidir`,
        {
          method: "POST",
          body: JSON.stringify({ decisao, ...(comentario ? { comentario } : {}) }),
        }
      );
    },
    desfazerDecisao(parecerId: string, itemId: string) {
      return request<DecisoHumanaResponse>(
        `/v1/pareceres/${parecerId}/ciclo/itens/${itemId}/desfazer-decisao`,
        { method: "POST" }
      );
    },
    aplicarAvaliacao(parecerId: string) {
      return request<{
        aceitos: number;
        pendencias: number;
        fase_caso: FaseCaso;
        desfecho: Desfecho | null;
        mensagem: string;
      }>(`/v1/pareceres/${parecerId}/ciclo/aplicar-avaliacao`, { method: "POST" });
    },
    fechar(parecerId: string, desfecho: Desfecho, observacoes?: string) {
      return request<{ fase_caso: FaseCaso; desfecho: Desfecho; fechado_em: string; mensagem: string }>(
        `/v1/pareceres/${parecerId}/fechar`,
        {
          method: "POST",
          body: JSON.stringify({ desfecho, ...(observacoes ? { observacoes } : {}) }),
        }
      );
    },
    async criarRodada(
      parecerId: string,
      tipo: TipoRodada,
      opts: { arquivo?: File; textoColado?: string; propostaFinal?: boolean }
    ) {
      const formData = new FormData();
      formData.append("tipo", tipo);
      if (opts.arquivo) formData.append("arquivo", opts.arquivo);
      if (opts.textoColado) formData.append("texto_colado", opts.textoColado);
      if (opts.propostaFinal) formData.append("proposta_final", "true");
      const response = await fetch(
        `/api/parecer-tecnico/v1/pareceres/${parecerId}/rodadas`,
        { method: "POST", body: formData }
      );
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(extractErrorMessage(error, `Erro ${response.status}`));
      }
      return response.json() as Promise<{ rodada_id: string; task_id: string; mensagem: string }>;
    },
    listarRodadas(parecerId: string) {
      return request<RodadaFornecedorResponse[]>(`/v1/pareceres/${parecerId}/rodadas`);
    },
    detalharRodada(parecerId: string, rodadaId: string) {
      return request<RodadaDetalheResponse>(`/v1/pareceres/${parecerId}/rodadas/${rodadaId}`);
    },
    progressoRodada(parecerId: string, rodadaId: string) {
      return request<RodadaProgressoResponse>(
        `/v1/pareceres/${parecerId}/rodadas/${rodadaId}/progresso`
      );
    },
    corrigirVinculo(
      parecerId: string,
      rodadaId: string,
      avaliacaoId: string,
      data: { item_numero?: number; remover?: boolean }
    ) {
      return request<VinculoResponse | null>(
        `/v1/pareceres/${parecerId}/rodadas/${rodadaId}/vinculos/${avaliacaoId}`,
        { method: "PATCH", body: JSON.stringify(data) }
      );
    },
    confirmarVinculacao(parecerId: string, rodadaId: string) {
      return request<{ rodada_id: string; status: StatusRodada; itens_transicionados: number; task_id: string; mensagem: string }>(
        `/v1/pareceres/${parecerId}/rodadas/${rodadaId}/confirmar-vinculacao`,
        { method: "POST" }
      );
    },
    async reimportarRespostas(parecerId: string, file: File) {
      const formData = new FormData();
      formData.append("arquivo", file);
      const response = await fetch(
        `/api/parecer-tecnico/v1/pareceres/${parecerId}/reimportar-respostas`,
        { method: "POST", body: formData }
      );
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(extractErrorMessage(error, `Erro ${response.status}`));
      }
      return response.json() as Promise<ReimportResultResponse>;
    },
    historico(parecerId: string, itemId: string) {
      return request<RodadaAvaliacaoResponse[]>(
        `/v1/pareceres/${parecerId}/ciclo/itens/${itemId}/historico`
      );
    },
    async downloadCarta(parecerId: string) {
      const response = await fetch(
        `/api/parecer-tecnico/v1/pareceres/${parecerId}/exportar/carta-pendencias`
      );
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(extractErrorMessage(error, `Erro ${response.status}`));
      }
      const blob = await response.blob();
      const cd = response.headers.get("content-disposition") || "";
      const match = cd.match(/filename="?([^";]+)"?/i);
      const filename = match?.[1] || "carta_pendencias.xlsx";
      return { blob, filename };
    },
    async downloadCicloRodada(parecerId: string) {
      const response = await fetch(
        `/api/parecer-tecnico/v1/pareceres/${parecerId}/exportar/ciclo-rodada`
      );
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(extractErrorMessage(error, `Erro ${response.status}`));
      }
      const blob = await response.blob();
      const cd = response.headers.get("content-disposition") || "";
      const match = cd.match(/filename="?([^";]+)"?/i);
      const filename = match?.[1] || "ciclo_rodada.xlsx";
      return { blob, filename };
    },
  },
  spec: {
    async criarVersao(parecerId: string, arquivo: File) {
      const formData = new FormData();
      formData.append("arquivo", arquivo);
      const response = await fetch(
        `/api/parecer-tecnico/v1/pareceres/${parecerId}/spec-versoes`,
        { method: "POST", body: formData }
      );
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(extractErrorMessage(error, `Erro ${response.status}`));
      }
      return response.json() as Promise<VersaoSpecResponse>;
    },
    listar(parecerId: string) {
      return request<VersaoSpecResponse[]>(`/v1/pareceres/${parecerId}/spec-versoes`);
    },
    progresso(parecerId: string, versaoId: string) {
      return request<{ status: string; cenario: string | null; percent: number | null; message: string | null }>(
        `/v1/pareceres/${parecerId}/spec-versoes/${versaoId}/progresso`
      );
    },
    aplicar(parecerId: string, versaoId: string, incluirNovos: number[]) {
      return request<{ cenario: string | null; reabertos: number; desativados: number; incluidos: number; fase_caso: FaseCaso; mensagem: string }>(
        `/v1/pareceres/${parecerId}/spec-versoes/${versaoId}/aplicar`,
        { method: "POST", body: JSON.stringify({ incluir_novos: incluirNovos }) }
      );
    },
    descartar(parecerId: string, versaoId: string) {
      return request<VersaoSpecResponse>(
        `/v1/pareceres/${parecerId}/spec-versoes/${versaoId}/descartar`,
        { method: "POST" }
      );
    },
    recomparar(parecerId: string, versaoId: string) {
      return request<VersaoSpecResponse>(
        `/v1/pareceres/${parecerId}/spec-versoes/${versaoId}/recomparar`,
        { method: "POST" }
      );
    },
  },
  verificacao: {
    obter(parecerId: string) {
      return request<VerificacaoFinalResponse>(`/v1/pareceres/${parecerId}/verificacao-final`);
    },
    executar(parecerId: string, rodadaFornecedorId: string) {
      return request<{ verificacao_id: string; task_id: string; mensagem: string }>(
        `/v1/pareceres/${parecerId}/verificacao-final/executar`,
        {
          method: "POST",
          body: JSON.stringify({ rodada_fornecedor_id: rodadaFornecedorId }),
        }
      );
    },
    progresso(parecerId: string) {
      return request<{ status: string; percent: number | null; message: string | null; stage: string | null }>(
        `/v1/pareceres/${parecerId}/verificacao-final/progresso`
      );
    },
    validar(parecerId: string, resultadoValidado: ResultadoValidado, observacoes?: string) {
      return request<VerificacaoFinalResponse>(
        `/v1/pareceres/${parecerId}/verificacao-final/validar`,
        {
          method: "POST",
          body: JSON.stringify({
            resultado_validado: resultadoValidado,
            ...(observacoes ? { observacoes } : {}),
          }),
        }
      );
    },
  },
  chat: {
    historico(parecerId: string) {
      return request<ChatHistoryResponse>(`/v1/pareceres/${parecerId}/chat/historico`);
    },
    async sendMessage(
      parecerId: string,
      mensagem: string,
      onChunk: (text: string) => void,
      onDone: (data: { message_id: string; table_updated: boolean }) => void,
      onError: (error: string) => void,
      opts?: {
        /** Estado do fluxo (modo JULIA): habilita chat em qualquer fase + ações. */
        contexto?: ChatContextoFluxo;
        /** Ação estruturada emitida pela LLM (ex: atualizar draft de requisitos). */
        onAction?: (action: ChatAction) => void;
        /** A LLM tentou uma ação mas ela não pôde ser aplicada. */
        onActionError?: (detail: string) => void;
      }
    ) {
      const response = await fetch(
        `/api/parecer-tecnico/v1/pareceres/${parecerId}/chat/mensagem`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mensagem,
            ...(opts?.contexto ? { contexto: opts.contexto } : {}),
          }),
        }
      );

      if (!response.ok) {
        const error = await response.json().catch(() => null);
        onError(extractErrorMessage(error, `Erro ${response.status}`));
        return;
      }

      if (!response.body) {
        onError("Resposta de streaming invalida");
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";
      let finished = false;

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                if (currentEvent === "chunk") onChunk(data.text);
                else if (currentEvent === "action") opts?.onAction?.(data as ChatAction);
                else if (currentEvent === "action_error") opts?.onActionError?.(data.detail || "Ação não aplicada");
                else if (currentEvent === "done") { onDone({ message_id: data.message_id, table_updated: false }); finished = true; }
                else if (currentEvent === "table_updated") { onDone({ message_id: data.message_id, table_updated: true }); finished = true; }
                else if (currentEvent === "error") { onError(data.detail || "Erro desconhecido"); finished = true; }
              } catch { /* ignore malformed */ }
              currentEvent = "";
            }
          }
        }
      } catch {
        onError("Falha na conexao durante streaming da resposta");
        return;
      }
      if (!finished) onError("Conexao encerrada sem evento final");
    },
    clearHistory(parecerId: string) {
      return request<void>(`/v1/pareceres/${parecerId}/chat/historico`, { method: "DELETE" });
    },
  },
  admin: {
    qualidade() {
      return request<QualidadeResponse>(`/v1/admin/qualidade`);
    },
  },
};
