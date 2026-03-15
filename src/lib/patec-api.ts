/**
 * PATEC API client for Noglem integration.
 * All calls go through /api/parecer-tecnico/ proxy which adds Clerk auth.
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
  criado_em: string;
  atualizado_em: string;
}

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
}

export type ExportFormat = "pdf" | "xlsx" | "docx";
export type PerfilAnalise =
  | "triagem_tecnica"
  | "conformidade_tecnica"
  | "auditoria_tecnica_completa";

export interface DocumentoResponse {
  id: string;
  parecer_id: string;
  tipo: string;
  nome_arquivo: string;
  tipo_arquivo: string;
  tamanho_bytes: number | null;
  criado_em: string;
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
  criado_em: string;
  atualizado_em: string;
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
  },
  documentos: {
    list(parecerId: string) {
      return request<DocumentoResponse[]>(`/v1/pareceres/${parecerId}/documentos`);
    },
    async upload(parecerId: string, tipo: "engenharia" | "fornecedor", file: File) {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(
        `/api/parecer-tecnico/v1/pareceres/${parecerId}/documentos/${tipo}`,
        { method: "POST", body: formData }
      );
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(extractErrorMessage(error, `Erro ${response.status}`));
      }
      return response.json() as Promise<DocumentoResponse>;
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
    iniciar(parecerId: string, perfilAnalise: PerfilAnalise = "conformidade_tecnica") {
      return request<AnaliseResponse>(`/v1/pareceres/${parecerId}/analisar`, {
        method: "POST",
        body: JSON.stringify({ perfil_analise: perfilAnalise }),
      });
    },
    status(parecerId: string) {
      return request<StatusAnaliseResponse>(`/v1/pareceres/${parecerId}/status`);
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
  chat: {
    historico(parecerId: string) {
      return request<ChatHistoryResponse>(`/v1/pareceres/${parecerId}/chat/historico`);
    },
    async sendMessage(
      parecerId: string,
      mensagem: string,
      regenerar: boolean,
      onChunk: (text: string) => void,
      onDone: (data: { message_id: string; table_updated: boolean }) => void,
      onError: (error: string) => void
    ) {
      const response = await fetch(
        `/api/parecer-tecnico/v1/pareceres/${parecerId}/chat/mensagem`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mensagem, regenerar }),
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
};
