"use client";

/**
 * ConversationProvider — estado central da conversa da JulIA.
 *
 * Mantém um snapshot único do caso (derivado 100% do backend) + o estado local
 * da sessão (draft de requisitos, perfil de análise, streaming do chat).
 * O passo ativo e a timeline são derivados por funções puras a cada render.
 *
 * Substitui o antigo workspace-context.tsx.
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  useMemo,
  type ReactNode,
} from "react";
import {
  patecApi,
  type PerfilAnalise,
  type RequisitoBase,
  type ChatMessageResponse,
  type DecisaoHumana,
  type Desfecho,
  type ResultadoValidado,
  type TipoRodada,
  type ExportFormat,
  type UploadProgress,
} from "@/lib/patec-api";
import type {
  Snapshot,
  ConversationStep,
  TimelineEntry,
  TaskProgress,
} from "./types";
import { deriveStep } from "./derive-step";
import { deriveTimeline } from "./derive-timeline";

// Perfis de extração de requisitos (governam só a extração, R1 lê do BD)
export const PERFIL_OPTIONS: Array<{
  value: PerfilAnalise;
  label: string;
  description: string;
}> = [
  {
    value: "simples",
    label: "Simples — 10 itens",
    description: "Foco nos desvios críticos: segurança, rejeições e bloqueios técnicos.",
  },
  {
    value: "padrao",
    label: "Padrão — 15 itens",
    description: "Cobertura equilibrada dos requisitos críticos e relevantes.",
  },
  {
    value: "completa",
    label: "Completa — 20 itens",
    description: "Análise abrangente, incluindo documentação e prazos.",
  },
  {
    value: "integral",
    label: "Integral — todos",
    description: "Segue na íntegra a tabela de requisitos da engenharia, sem limite.",
  },
  {
    value: "personalizado",
    label: "Personalizado",
    description: "Defina o número exato de itens.",
  },
];

// Progresso da extração sem update há mais que isto = task morta (o worker
// bate heartbeat a cada 60s; 5 batidas perdidas não é atraso, é óbito).
const EXTRACAO_STALE_S = 300;

export const STAGE_LABELS: Record<string, string> = {
  queued: "Na fila",
  starting: "Iniciando",
  loading_documents: "Carregando documentos",
  cache_lookup: "Verificando cache",
  cache_hit: "Cache encontrado",
  llm_analysis: "Analisando com LLM",
  reference_validation: "Validando referências",
  optimizing_fields: "Otimizando campos",
  saving_results: "Salvando resultados",
  completed: "Concluído",
  error: "Erro",
  processing: "Processando",
  // Extração de requisitos (task extrair_requisitos no worker)
  lendo_documento: "Lendo documentos",
  extraindo: "Extraindo requisitos",
  amarracoes: "Desdobrando amarrações",
  revisando: "Revisando a lista",
  corrigindo: "Aplicando correções",
  salvando: "Salvando rascunho",
};

interface ConversationContextValue {
  parecerId: string;
  snapshot: Snapshot | null;
  loading: boolean;
  notFound: boolean;
  step: ConversationStep | null;
  timeline: TimelineEntry[];
  actionError: string;
  clearActionError: () => void;

  // Perfil de análise (extração)
  perfil: PerfilAnalise;
  setPerfil: (p: PerfilAnalise) => void;
  customItemCount: number;
  setCustomItemCount: (n: number) => void;

  // Draft de requisitos (W1) — persistido no BD (snapshot.requisitosDraft)
  requisitosResumo: string;
  extracting: boolean;
  extrairRequisitos: (opts?: {
    escopo?: string;
    feedback?: string;
    perfil?: string;
  }) => Promise<boolean>;
  salvarDraft: (requisitos: RequisitoBase[]) => Promise<void>;
  reabrirRequisitos: () => Promise<void>;
  confirmarComplementares: () => Promise<void>;
  aprovarEAnalisar: () => Promise<void>;

  // Tabela do caso (visualização do banco de dados)
  showDataPanel: boolean;
  setShowDataPanel: (v: boolean) => void;

  // Tabela completa do ciclo (decisão W4 — todos os itens + decidir inline)
  showCicloPanel: boolean;
  setShowCicloPanel: (v: boolean) => void;

  // Documentos
  uploadDocumento: (
    tipo: "engenharia" | "fornecedor" | "anexo_engenharia",
    files: FileList | File[],
    onProgress?: (file: File, progress: UploadProgress) => void
  ) => Promise<void>;
  deleteDocumento: (docId: string) => Promise<void>;

  // Análise / ciclo
  startAnalysis: () => Promise<void>;
  iniciarCiclo: () => Promise<void>;

  // Rodadas (fase B)
  criarRodada: (
    tipo: TipoRodada,
    opts: { arquivo?: File; textoColado?: string; propostaFinal?: boolean }
  ) => Promise<void>;
  confirmarVinculacao: (rodadaId: string) => Promise<void>;
  corrigirVinculo: (
    rodadaId: string,
    avaliacaoId: string,
    data: { item_numero?: number; remover?: boolean }
  ) => Promise<void>;
  decidirItem: (
    itemId: string,
    decisao: DecisaoHumana,
    comentario?: string
  ) => Promise<void>;
  desfazerDecisao: (itemId: string) => Promise<void>;
  aplicarAvaliacao: () => Promise<void>;
  downloadCarta: () => Promise<void>;
  downloadCicloRodada: () => Promise<void>;
  reimportarRespostas: (file: File) => Promise<string>;

  // Verificação final / fechamento (fase C)
  executarVerificacao: (rodadaFornecedorId: string) => Promise<void>;
  validarVerificacao: (
    resultado: ResultadoValidado,
    observacoes?: string
  ) => Promise<void>;
  fecharCaso: (desfecho: Desfecho, observacoes?: string) => Promise<void>;
  exportar: (formato: ExportFormat) => Promise<void>;

  // Revisão de spec (fase D)
  criarSpecVersao: (arquivo: File) => Promise<void>;
  aplicarSpec: (versaoId: string, incluirNovos: number[]) => Promise<void>;
  descartarSpec: (versaoId: string) => Promise<void>;
  recompararSpec: (versaoId: string) => Promise<void>;

  // Progresso de tarefa assíncrona do passo ativo
  taskProgress: TaskProgress | null;

  // Chat RAG (texto livre)
  streamingContent: string;
  chatSending: boolean;
  sendFreeText: (text: string) => Promise<void>;
  /** Mensagens efêmeras da JulIA nesta sessão (gate pré-análise etc.). */
  ephemeral: TimelineEntry[];
  pushEphemeral: (entry: TimelineEntry) => void;

  refreshSnapshot: () => Promise<void>;
}

const ConversationContext = createContext<ConversationContextValue | null>(null);

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function ConversationProvider({
  parecerId,
  children,
}: {
  parecerId: string;
  children: ReactNode;
}) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [actionError, setActionError] = useState("");

  const [perfil, setPerfil] = useState<PerfilAnalise>("padrao");
  const [customItemCount, setCustomItemCount] = useState(25);

  const [requisitosResumo, setRequisitosResumo] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [showDataPanel, setShowDataPanel] = useState(false);
  const [showCicloPanel, setShowCicloPanel] = useState(false);

  const [taskProgress, setTaskProgress] = useState<TaskProgress | null>(null);

  const [streamingContent, setStreamingContent] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [ephemeral, setEphemeral] = useState<TimelineEntry[]>([]);

  const refreshing = useRef(false);

  const resolvedPerfil: PerfilAnalise =
    perfil === "personalizado"
      ? `custom_${Math.max(1, Math.min(customItemCount, 100))}`
      : perfil;

  // --- Snapshot ---

  const refreshSnapshot = useCallback(async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    try {
      const parecer = await patecApi.pareceres.get(parecerId);
      const fase = parecer.fase_caso;

      const posAnalise = ["CICLO_FORNECEDOR", "VERIFICACAO_FINAL", "FECHADO"].includes(fase);
      const emVerificacao = fase === "VERIFICACAO_FINAL";

      const preAnalise = ["SETUP", "REQUISITOS", "ANALISE"].includes(fase);

      const [
        documentos,
        requisitos,
        requisitosDraft,
        itens,
        rodadas,
        resumo,
        itensReavaliacao,
        verificacao,
        specVersoes,
        chatHistory,
      ] = await Promise.all([
        patecApi.documentos.list(parecerId).catch(() => []),
        patecApi.requisitos.list(parecerId).catch(() => []),
        // Rascunho persistido no BD — só existe pré-análise
        preAnalise
          ? patecApi.requisitos.draft(parecerId).catch(() => [])
          : Promise.resolve([]),
        patecApi.itens.list(parecerId).catch(() => []),
        posAnalise
          ? patecApi.ciclo.listarRodadas(parecerId).catch(() => [])
          : Promise.resolve([]),
        posAnalise
          ? patecApi.ciclo.resumo(parecerId).catch(() => null)
          : Promise.resolve(null),
        fase === "CICLO_FORNECEDOR"
          ? patecApi.ciclo.itensEmReavaliacao(parecerId).catch(() => [])
          : Promise.resolve([]),
        // GET cria o registro e aplica a bifurcação do bloco 29 — só chamar na fase certa
        emVerificacao || fase === "FECHADO"
          ? patecApi.verificacao.obter(parecerId).catch(() => null)
          : Promise.resolve(null),
        fase !== "SETUP"
          ? patecApi.spec.listar(parecerId).catch(() => [])
          : Promise.resolve([]),
        patecApi.chat
          .historico(parecerId)
          .then((h) => h.messages)
          .catch(() => [] as ChatMessageResponse[]),
      ]);

      setSnapshot({
        parecer,
        documentos,
        requisitos,
        requisitosDraft,
        itens,
        rodadas,
        resumo,
        itensReavaliacao,
        verificacao,
        specVersoes,
        chatHistory,
      });
      // O snapshot recém-carregado é a fonte autoritativa e já inclui o histórico
      // de chat + eventos na ordem cronológica correta (deriveTimeline). As efêmeras
      // eram só uma ponte até esta sincronização — limpá-las evita que mensagens de
      // sessões/ações anteriores fiquem "presas" no rodapé, fora de ordem. Toasts de
      // ação são empurrados DEPOIS do refresh, então sobrevivem.
      setEphemeral([]);
    } catch {
      setNotFound(true);
    } finally {
      refreshing.current = false;
      setLoading(false);
    }
  }, [parecerId]);

  useEffect(() => {
    // fetch-on-mount: todo setState do refreshSnapshot ocorre após await
     
    void refreshSnapshot();
  }, [refreshSnapshot]);

  // --- Derivação ---

  const step = useMemo(
    () => (snapshot ? deriveStep(snapshot) : null),
    [snapshot]
  );

  const timeline = useMemo(
    () => (snapshot ? deriveTimeline(snapshot) : []),
    [snapshot]
  );

  // --- Polling consolidado do passo ativo ---

  useEffect(() => {
    if (!snapshot || !step) return;

    type Poll = () => Promise<{
      percent: number | null;
      message: string | null;
      stage: string | null;
      terminou: boolean;
    }>;

    let poll: Poll | null = null;

    if (extracting) {
      // Extração de requisitos no worker — condicionado ao estado local (não ao
      // step): a re-extração com feedback acontece já no passo requisitos.aprovar.
      poll = async () => {
        const p = await patecApi.requisitos.extracaoProgresso(parecerId);
        // Progresso "morto": chave sumiu (TTL) ou worker parou de bater o
        // heartbeat (60s) — sem isto, worker morto = barra eterna.
        const idadeS =
          typeof p.updated_at === "number"
            ? Date.now() / 1000 - p.updated_at
            : null;
        const morto =
          !p.stage || (idadeS !== null && idadeS > EXTRACAO_STALE_S);
        const terminou = p.stage === "completed" || p.stage === "error" || morto;
        if (terminou) {
          setExtracting(false);
          if (p.stage === "completed") {
            // O resumo da extração viaja na mensagem do stage completed
            setRequisitosResumo(p.message ?? "");
          } else if (morto) {
            setActionError(
              "A extração parou de responder. Tente extrair novamente."
            );
          } else {
            setActionError(p.message ?? "Erro ao extrair requisitos");
          }
        }
        return {
          percent: p.percent,
          message: p.message,
          stage: p.stage,
          terminou,
        };
      };
    } else if (step.id === "analise.rodando") {
      poll = async () => {
        const s = await patecApi.analise.status(parecerId);
        return {
          percent: s.progress_percent,
          message: s.message,
          stage: s.stage,
          terminou: s.status_processamento !== "processando",
        };
      };
    } else if (
      (step.id === "ciclo.vinculando" || step.id === "ciclo.avaliando") &&
      step.rodada
    ) {
      const rodadaId = step.rodada.id;
      const statusInicial = step.rodada.status;
      poll = async () => {
        const p = await patecApi.ciclo.progressoRodada(parecerId, rodadaId);
        return {
          percent: p.percent,
          message: p.message,
          stage: p.stage,
          terminou: p.status !== statusInicial,
        };
      };
    } else if (step.id === "verificacao.rodando") {
      poll = async () => {
        const p = await patecApi.verificacao.progresso(parecerId);
        return {
          percent: p.percent,
          message: p.message,
          stage: p.stage,
          terminou: p.status !== "EM_VERIFICACAO",
        };
      };
    } else if (step.id === "spec.comparando" && step.specVersao) {
      const versaoId = step.specVersao.id;
      poll = async () => {
        const p = await patecApi.spec.progresso(parecerId, versaoId);
        return {
          percent: p.percent,
          message: p.message,
          stage: null,
          terminou: p.status !== "EM_COMPARACAO",
        };
      };
    } else if (
      (step.id === "setup.docs_eng" ||
        step.id === "setup.docs_complementares" ||
        step.id === "analise.docs_forn") &&
      snapshot.documentos.some((d) => d.aviso_extracao)
    ) {
      // OCR em andamento: um documento imagem/scan ainda esta sem texto. Re-busca
      // ate o OCR preencher (aviso some) e entao avança. Se falhar de vez, o aviso
      // persiste (correto — o gate segura ate o usuario enviar um arquivo legível).
      poll = async () => {
        const docs = await patecApi.documentos.list(parecerId);
        const pendente = docs.some((d) => d.aviso_extracao);
        return {
          percent: null,
          message: pendente
            ? "Lendo o documento com OCR — isso leva alguns segundos..."
            : "Documento lido.",
          stage: "ocr",
          terminou: !pendente,
        };
      };
    }

    if (!poll) return;

    let cancelled = false;
    const tick = async () => {
      try {
        const r = await poll!();
        if (cancelled) return;
        setTaskProgress({
          percent: r.percent ?? 0,
          message: r.message ?? "",
          stage: r.stage ?? "processing",
        });
        if (r.terminou) {
          await refreshSnapshot();
        }
      } catch {
        // erro transitório de rede: tenta no próximo tick
      }
    };

    void tick();
    const interval = setInterval(tick, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
      // limpa o progresso ao sair do passo (evita barra "fantasma" no próximo)
      setTaskProgress(null);
    };
  }, [parecerId, snapshot, step, extracting, refreshSnapshot]);

  // Recuperação pós-reload: se o usuário der F5 com a extração rodando no
  // worker, o estado local `extracting` se perde — re-liga a partir do
  // progresso ativo no Redis (stage não-terminal E fresco: o heartbeat do
  // worker bate a cada 60s; sem frescor seria re-engatar um estado morto).
  // Roda uma vez, ao montar.
  const extracaoRecoveryChecked = useRef(false);
  useEffect(() => {
    if (!snapshot || extracaoRecoveryChecked.current) return;
    extracaoRecoveryChecked.current = true;
    const fase = snapshot.parecer.fase_caso;
    if (fase !== "SETUP" && fase !== "REQUISITOS" && fase !== "ANALISE") return;
    void patecApi.requisitos
      .extracaoProgresso(parecerId)
      .then((p) => {
        const idadeS =
          typeof p.updated_at === "number"
            ? Date.now() / 1000 - p.updated_at
            : null;
        const fresco = idadeS !== null && idadeS <= EXTRACAO_STALE_S;
        if (p.stage && p.stage !== "completed" && p.stage !== "error" && fresco) {
          setExtracting(true);
        }
      })
      .catch(() => {
        // sem progresso ativo (ou erro transitório) — segue sem recuperação
      });
  }, [parecerId, snapshot]);

  // --- Helpers de ação ---

  const runAction = useCallback(
    async (fn: () => Promise<void>) => {
      setActionError("");
      try {
        await fn();
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Erro inesperado");
        throw err;
      }
    },
    []
  );

  // --- Documentos ---

  const uploadDocumento = useCallback(
    async (
      tipo: "engenharia" | "fornecedor" | "anexo_engenharia",
      files: FileList | File[],
      onProgress?: (file: File, progress: UploadProgress) => void
    ) =>
      runAction(async () => {
        for (const file of Array.from(files)) {
          await patecApi.documentos.upload(parecerId, tipo, file, (progress) =>
            onProgress?.(file, progress)
          );
        }
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  const deleteDocumento = useCallback(
    async (docId: string) =>
      runAction(async () => {
        await patecApi.documentos.delete(parecerId, docId);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  // --- Requisitos (W1) ---

  // Perfil da última extração disparada nesta sessão: a re-extração com
  // feedback ("Pedir ajustes") não passa perfil, e sem esta memória ela caía
  // no default "padrao" — cortando em 15 uma lista pedida como completa/custom.
  const lastPerfilRef = useRef<PerfilAnalise | null>(null);

  const extrairRequisitos = useCallback(
    async (opts?: {
      escopo?: string;
      feedback?: string;
      perfil?: string;
    }): Promise<boolean> => {
      setActionError("");
      const perfilEfetivo =
        (opts?.perfil as PerfilAnalise | undefined) ??
        lastPerfilRef.current ??
        resolvedPerfil;
      try {
        await patecApi.requisitos.extrair(parecerId, perfilEfetivo, {
          escopo: opts?.escopo,
          feedback: opts?.feedback,
        });
        lastPerfilRef.current = perfilEfetivo;
        // Só liga o polling APÓS o 202: o endpoint grava o stage "queued" no
        // Redis antes de responder, então o primeiro tick nunca lê o stage
        // terminal velho da extração anterior (corrida que encerrava a nova
        // extração na hora com o resumo/draft antigos).
        setExtracting(true);
        return true;
      } catch (err) {
        // NÃO mexe em `extracting` aqui: um 409 significa que OUTRA extração
        // está rodando — desligar mataria a barra de progresso dela.
        setActionError(
          err instanceof Error ? err.message : "Erro ao extrair requisitos"
        );
        return false;
      }
    },
    [parecerId, resolvedPerfil]
  );

  // Substitui o rascunho persistido (edição manual no widget/tabela)
  const salvarDraft = useCallback(
    async (requisitos: RequisitoBase[]) =>
      runAction(async () => {
        await patecApi.requisitos.salvarDraft(parecerId, requisitos);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  // Reabre os requisitos aprovados como rascunho editável (fase ANALISE) — o
  // RequisitosWidget reaparece para o engenheiro editar a lista antes de reavaliar
  const reabrirRequisitos = useCallback(
    async () =>
      runAction(async () => {
        await patecApi.requisitos.reabrir(parecerId);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  // Gate de setup: marca os documentos complementares como resolvidos (anexados
  // ou inexistentes) e avança para a etapa da proposta do fornecedor.
  const confirmarComplementares = useCallback(
    async () =>
      runAction(async () => {
        await patecApi.pareceres.confirmarComplementares(parecerId);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  // W1 (aprovar requisitos no BD) — dispara a análise R1 só se a proposta do
  // fornecedor já estiver presente; senão, o fluxo pede a proposta (analise.docs_forn).
  const aprovarEAnalisar = useCallback(async () => {
    const draft = snapshot?.requisitosDraft ?? [];
    if (draft.length === 0) return;
    const temForn =
      snapshot?.documentos.some((d) => d.tipo === "fornecedor") ?? false;
    await runAction(async () => {
      await patecApi.requisitos.aprovar(
        parecerId,
        draft.map((r) => ({
          numero: r.numero,
          categoria: r.categoria,
          descricao_requisito: r.descricao_requisito,
          referencia_engenharia: r.referencia_engenharia,
          valor_requerido: r.valor_requerido,
          prioridade: r.prioridade ?? "MEDIA",
          norma_referencia: r.norma_referencia,
        }))
      );
      setRequisitosResumo("");
      if (temForn) {
        await patecApi.analise.iniciar(parecerId, resolvedPerfil);
      }
      await refreshSnapshot();
    });
  }, [parecerId, snapshot, resolvedPerfil, refreshSnapshot, runAction]);

  // --- Análise / ciclo ---

  const startAnalysis = useCallback(
    async () =>
      runAction(async () => {
        await patecApi.analise.iniciar(parecerId, resolvedPerfil);
        await refreshSnapshot();
      }),
    [parecerId, resolvedPerfil, refreshSnapshot, runAction]
  );

  const iniciarCiclo = useCallback(
    async () =>
      runAction(async () => {
        await patecApi.ciclo.iniciar(parecerId);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  // --- Rodadas (fase B) ---

  const criarRodada = useCallback(
    async (
      tipo: TipoRodada,
      opts: { arquivo?: File; textoColado?: string; propostaFinal?: boolean }
    ) =>
      runAction(async () => {
        await patecApi.ciclo.criarRodada(parecerId, tipo, opts);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  const confirmarVinculacao = useCallback(
    async (rodadaId: string) =>
      runAction(async () => {
        await patecApi.ciclo.confirmarVinculacao(parecerId, rodadaId);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  const corrigirVinculo = useCallback(
    async (
      rodadaId: string,
      avaliacaoId: string,
      data: { item_numero?: number; remover?: boolean }
    ) =>
      runAction(async () => {
        await patecApi.ciclo.corrigirVinculo(parecerId, rodadaId, avaliacaoId, data);
      }),
    [parecerId, runAction]
  );

  const decidirItem = useCallback(
    async (itemId: string, decisao: DecisaoHumana, comentario?: string) =>
      runAction(async () => {
        await patecApi.ciclo.decidir(parecerId, itemId, decisao, comentario);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  const desfazerDecisao = useCallback(
    async (itemId: string) =>
      runAction(async () => {
        await patecApi.ciclo.desfazerDecisao(parecerId, itemId);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  const aplicarAvaliacao = useCallback(
    async () =>
      runAction(async () => {
        await patecApi.ciclo.aplicarAvaliacao(parecerId);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  const downloadCarta = useCallback(
    async () =>
      runAction(async () => {
        const { blob, filename } = await patecApi.ciclo.downloadCarta(parecerId);
        downloadBlob(blob, filename);
      }),
    [parecerId, runAction]
  );

  const downloadCicloRodada = useCallback(
    async () =>
      runAction(async () => {
        const { blob, filename } = await patecApi.ciclo.downloadCicloRodada(parecerId);
        downloadBlob(blob, filename);
      }),
    [parecerId, runAction]
  );

  const reimportarRespostas = useCallback(
    async (file: File): Promise<string> => {
      setActionError("");
      try {
        const result = await patecApi.ciclo.reimportarRespostas(parecerId, file);
        await refreshSnapshot();
        return result.mensagem;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Erro ao importar carta";
        setActionError(msg);
        throw err;
      }
    },
    [parecerId, refreshSnapshot]
  );

  // --- Verificação final / fechamento (fase C) ---

  const executarVerificacao = useCallback(
    async (rodadaFornecedorId: string) =>
      runAction(async () => {
        await patecApi.verificacao.executar(parecerId, rodadaFornecedorId);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  const validarVerificacao = useCallback(
    async (resultado: ResultadoValidado, observacoes?: string) =>
      runAction(async () => {
        await patecApi.verificacao.validar(parecerId, resultado, observacoes);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  const fecharCaso = useCallback(
    async (desfecho: Desfecho, observacoes?: string) =>
      runAction(async () => {
        await patecApi.ciclo.fechar(parecerId, desfecho, observacoes);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  const exportar = useCallback(
    async (formato: ExportFormat) =>
      runAction(async () => {
        const { blob, filename } = await patecApi.exportacoes.download(
          parecerId,
          formato
        );
        downloadBlob(blob, filename);
      }),
    [parecerId, runAction]
  );

  // --- Revisão de spec (fase D) ---

  const criarSpecVersao = useCallback(
    async (arquivo: File) =>
      runAction(async () => {
        await patecApi.spec.criarVersao(parecerId, arquivo);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  const aplicarSpec = useCallback(
    async (versaoId: string, incluirNovos: number[]) =>
      runAction(async () => {
        await patecApi.spec.aplicar(parecerId, versaoId, incluirNovos);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  const descartarSpec = useCallback(
    async (versaoId: string) =>
      runAction(async () => {
        await patecApi.spec.descartar(parecerId, versaoId);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  const recompararSpec = useCallback(
    async (versaoId: string) =>
      runAction(async () => {
        await patecApi.spec.recomparar(parecerId, versaoId);
        await refreshSnapshot();
      }),
    [parecerId, refreshSnapshot, runAction]
  );

  // --- Chat RAG (texto livre) ---

  const pushEphemeral = useCallback((entry: TimelineEntry) => {
    setEphemeral((prev) => [...prev, entry]);
  }, []);

  // A ação da JulIA já foi aplicada no BANCO pelo backend — aqui só
  // ressincronizamos, damos a confirmação visual concreta e disparamos os
  // passos seguintes (ex: aprovação W1 → análise R1 começa sozinha).
  const applyChatAction = useCallback(
    async (action: {
      tipo: string;
      total?: number;
      perfil?: string;
      escopo?: string | null;
      reavaliados?: number;
      reavaliacao_erro?: string;
      mudancas?: { numero: number; de: string; para: string }[];
    }) => {
      const now = new Date().toISOString();
      if (action.tipo === "atualizar_requisitos") {
        // Confirmação visual: selo derivado de gerou_nova_tabela na timeline
        // (persiste ao F5) — o refresh abaixo já o traz; sem chip efêmero aqui.
        await refreshSnapshot();
        setShowDataPanel(true);
      } else if (action.tipo === "atualizar_itens") {
        await refreshSnapshot();
        setShowDataPanel(true);
        // Reavaliação automática pós-correção de descrição/valor (#13): o chip
        // detalha o resultado; o selo "Tabela atualizada" persiste via timeline.
        const mudancas = action.mudancas ?? [];
        if ((action.reavaliados ?? 0) > 0) {
          pushEphemeral({
            kind: "event",
            key: `acao-reaval-auto-${Date.now()}`,
            at: now,
            title: "Itens reavaliados contra a proposta",
            detail: mudancas.length
              ? `Status alterados: ${mudancas.map((m) => `item ${m.numero}: ${m.de}→${m.para}`).join(", ")}`
              : "Classificações confirmadas — nenhuma mudança de status",
            tone: "success",
          });
        } else if (action.reavaliacao_erro) {
          pushEphemeral({
            kind: "event",
            key: `acao-reaval-erro-${Date.now()}`,
            at: now,
            title: "Correção aplicada, mas a reavaliação falhou",
            detail: `${action.reavaliacao_erro} — peça "reavalie os itens" para tentar de novo`,
            tone: "warning",
          });
        }
      } else if (action.tipo === "reavaliar_itens") {
        await refreshSnapshot();
        setShowDataPanel(true);
        const mudancas = action.mudancas ?? [];
        const n = action.total ?? 0;
        pushEphemeral({
          kind: "event",
          key: `acao-reaval-${Date.now()}`,
          at: now,
          title: "Itens reavaliados contra a proposta",
          detail: mudancas.length
            ? `Status alterados: ${mudancas.map((m) => `item ${m.numero}: ${m.de}→${m.para}`).join(", ")}`
            : `${n} ${n === 1 ? "item reavaliado" : "itens reavaliados"} — nenhuma mudança de status`,
          tone: "success",
        });
      } else if (action.tipo === "aprovar_requisitos") {
        const n = action.total ?? 0;
        pushEphemeral({
          kind: "event",
          key: `acao-ok-${Date.now()}`,
          at: now,
          title: "Requisitos aprovados (W1)",
          detail: `${n} ${n === 1 ? "requisito é" : "requisitos são"} agora a referência oficial — iniciando a análise`,
          tone: "success",
        });
        // W1 feito no banco; dispara a análise R1 (mesmo caminho do botão)
        try {
          await patecApi.analise.iniciar(parecerId, resolvedPerfil);
        } catch {
          // se falhar, o derive cai em analise.pronta e o usuário pode redisparar
        }
        await refreshSnapshot();
      } else if (action.tipo === "iniciar_ciclo") {
        await refreshSnapshot();
        pushEphemeral({
          kind: "event",
          key: `acao-ok-${Date.now()}`,
          at: now,
          title: "Ciclo com o fornecedor iniciado (W2)",
          tone: "success",
        });
      } else if (action.tipo === "revisar_especificacao") {
        // Ação de UI: abre o envio da nova revisão inline na conversa
        pushEphemeral({
          kind: "widget",
          key: `acao-spec-${Date.now()}`,
          at: now,
          widget: "spec-upload",
        });
      } else if (action.tipo === "reanalisar") {
        // Ação de UI: redispara a análise R1 completa (mesmo caminho do
        // comando "reanalisar") — com validação de fase e barra de progresso.
        try {
          await startAnalysis();
          pushEphemeral({
            kind: "event",
            key: `acao-reanalise-${Date.now()}`,
            at: now,
            title: "Reanálise iniciada",
            detail: "Reavaliando todos os requisitos aprovados contra a proposta",
            tone: "success",
          });
        } catch {
          pushEphemeral({
            kind: "event",
            key: `acao-reanalise-erro-${Date.now()}`,
            at: now,
            title: "Não consegui reiniciar a análise",
            detail: "A reanálise só roda na fase de análise do caso.",
            tone: "error",
          });
        }
      } else if (action.tipo === "reabrir_requisitos") {
        // Backend já reabriu os requisitos como rascunho; ressincroniza para o
        // RequisitosWidget reaparecer (lista editável, sem a comparação).
        const n = action.total ?? 0;
        await refreshSnapshot();
        pushEphemeral({
          kind: "event",
          key: `acao-reabrir-${Date.now()}`,
          at: now,
          title: "Lista de requisitos reaberta para edição",
          detail: `${n} ${n === 1 ? "requisito" : "requisitos"} — edite abaixo; ao aprovar, a análise é refeita`,
          tone: "success",
        });
      } else if (action.tipo === "extrair_requisitos") {
        // Ação de UI (passo setup.extrair): dispara a extração no worker com o
        // perfil que a JulIA escolheu na conversa. O polling de progresso conduz
        // até o fim; ao concluir, o snapshot avança para a revisão dos requisitos.
        // O `escopo` que a JulIA capturou (ex.: "só o Cap. 2, todos os itens da
        // tabela") vai como ESCOPO da extração — ativa o recorte por seção e a
        // enumeração linha-a-linha SEM liberar o teto de itens do perfil.
        const iniciou = await extrairRequisitos({
          escopo: typeof action.escopo === "string" ? action.escopo : undefined,
          perfil: typeof action.perfil === "string" ? action.perfil : undefined,
        });
        pushEphemeral(
          iniciou
            ? {
                kind: "event",
                key: `acao-extrair-${Date.now()}`,
                at: now,
                title: "Extração de requisitos iniciada",
                detail:
                  "Acompanhe o progresso abaixo — a lista aparece para revisão ao concluir",
                tone: "success",
              }
            : {
                kind: "event",
                key: `acao-extrair-erro-${Date.now()}`,
                at: now,
                title: "Não consegui iniciar a extração",
                detail:
                  "Veja o aviso acima — pode já haver uma extração em andamento.",
                tone: "error",
              }
        );
      } else if (action.tipo === "confirmar_complementares") {
        // Backend já marcou os complementares como resolvidos; ressincroniza para
        // o fluxo avançar para a proposta do fornecedor.
        await refreshSnapshot();
        pushEphemeral({
          kind: "event",
          key: `acao-compl-${Date.now()}`,
          at: now,
          title: "Documentos complementares concluídos",
          detail: "Seguindo para a proposta do fornecedor",
          tone: "success",
        });
      }
    },
    [
      parecerId,
      resolvedPerfil,
      pushEphemeral,
      refreshSnapshot,
      setShowDataPanel,
      startAnalysis,
      extrairRequisitos,
    ]
  );

  const sendFreeText = useCallback(
    async (text: string) => {
      if (!snapshot || chatSending) return;

      setChatSending(true);
      setStreamingContent("");
      pushEphemeral({
        kind: "user",
        key: `eph-user-${Date.now()}`,
        at: new Date().toISOString(),
        text,
      });

      // Estado do fluxo (modo JulIA): chat real em qualquer fase + ações
      const draft = snapshot.requisitosDraft;
      const contexto = {
        fase_caso: snapshot.parecer.fase_caso,
        step_id: step?.id,
        ...(draft.length > 0
          ? {
              requisitos_draft: draft.map((r) => ({
                numero: r.numero,
                categoria: r.categoria,
                descricao_requisito: r.descricao_requisito,
                referencia_engenharia: r.referencia_engenharia,
                valor_requerido: r.valor_requerido,
                prioridade: r.prioridade ?? "MEDIA",
                norma_referencia: r.norma_referencia,
              })),
            }
          : {}),
      };

      let accumulated = "";
      try {
        await patecApi.chat.sendMessage(
          parecerId,
          text,
          (chunk) => {
            accumulated += chunk;
            setStreamingContent(accumulated);
          },
          (data) => {
            setStreamingContent("");
            pushEphemeral({
              kind: "julia",
              key: `chat-${data.message_id}`,
              at: new Date().toISOString(),
              markdown: accumulated,
            });
            if (data.table_updated) {
              refreshSnapshot();
            }
          },
          (errorMsg) => {
            setStreamingContent("");
            pushEphemeral({
              kind: "julia",
              key: `eph-err-${Date.now()}`,
              at: new Date().toISOString(),
              markdown: `Desculpe, tive um problema: ${errorMsg}`,
            });
          },
          {
            contexto,
            onAction: applyChatAction,
            onActionError: (detail) => {
              pushEphemeral({
                kind: "event",
                key: `acao-err-${Date.now()}`,
                at: new Date().toISOString(),
                title: "Não consegui aplicar a mudança",
                detail: detail || "Tente pedir de novo, talvez em partes menores",
                tone: "warning",
              });
            },
          }
        );
      } catch {
        // Falha ANTES do stream (ex.: backend inalcançável / fetch rejeitado) —
        // sem isto o erro era engolido e a conversa "travava" sem aviso nenhum.
        setStreamingContent("");
        pushEphemeral({
          kind: "event",
          key: `eph-neterr-${Date.now()}`,
          at: new Date().toISOString(),
          title: "Não consegui falar com o servidor",
          detail:
            "A mensagem não foi enviada. Verifique se o backend está no ar e tente de novo.",
          tone: "error",
        });
      } finally {
        setChatSending(false);
      }
    },
    [
      parecerId,
      snapshot,
      step,
      chatSending,
      pushEphemeral,
      refreshSnapshot,
      applyChatAction,
    ]
  );

  const clearActionError = useCallback(() => setActionError(""), []);

  const value: ConversationContextValue = useMemo(
    () => ({
      parecerId,
      snapshot,
      loading,
      notFound,
      step,
      timeline,
      actionError,
      clearActionError,
      perfil,
      setPerfil,
      customItemCount,
      setCustomItemCount,
      requisitosResumo,
      extracting,
      extrairRequisitos,
      salvarDraft,
      reabrirRequisitos,
      confirmarComplementares,
      aprovarEAnalisar,
      showDataPanel,
      setShowDataPanel,
      showCicloPanel,
      setShowCicloPanel,
      uploadDocumento,
      deleteDocumento,
      startAnalysis,
      iniciarCiclo,
      criarRodada,
      confirmarVinculacao,
      corrigirVinculo,
      decidirItem,
      desfazerDecisao,
      aplicarAvaliacao,
      downloadCarta,
      downloadCicloRodada,
      reimportarRespostas,
      executarVerificacao,
      validarVerificacao,
      fecharCaso,
      exportar,
      criarSpecVersao,
      aplicarSpec,
      descartarSpec,
      recompararSpec,
      taskProgress,
      streamingContent,
      chatSending,
      sendFreeText,
      ephemeral,
      pushEphemeral,
      refreshSnapshot,
    }),
    [
      parecerId,
      snapshot,
      loading,
      notFound,
      step,
      timeline,
      actionError,
      clearActionError,
      perfil,
      customItemCount,
      requisitosResumo,
      extracting,
      extrairRequisitos,
      salvarDraft,
      reabrirRequisitos,
      confirmarComplementares,
      aprovarEAnalisar,
      showDataPanel,
      showCicloPanel,
      uploadDocumento,
      deleteDocumento,
      startAnalysis,
      iniciarCiclo,
      criarRodada,
      confirmarVinculacao,
      corrigirVinculo,
      decidirItem,
      desfazerDecisao,
      aplicarAvaliacao,
      downloadCarta,
      downloadCicloRodada,
      reimportarRespostas,
      executarVerificacao,
      validarVerificacao,
      fecharCaso,
      exportar,
      criarSpecVersao,
      aplicarSpec,
      descartarSpec,
      recompararSpec,
      taskProgress,
      streamingContent,
      chatSending,
      sendFreeText,
      ephemeral,
      pushEphemeral,
      refreshSnapshot,
    ]
  );

  return (
    <ConversationContext.Provider value={value}>
      {children}
    </ConversationContext.Provider>
  );
}

export function useConversation(): ConversationContextValue {
  const ctx = useContext(ConversationContext);
  if (!ctx) {
    throw new Error("useConversation must be used within ConversationProvider");
  }
  return ctx;
}
