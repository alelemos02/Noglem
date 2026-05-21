"use client";

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
import { useRouter } from "next/navigation";
import {
  patecApi,
  type ParecerResponse,
  type ItemParecerResponse,
  type ItemParecerUpdate,
  type DocumentoResponse,
  type RecomendacaoResponse,
  type PerfilAnalise,
  type PreviewItemCandidato,
} from "@/lib/patec-api";

// --- Constants shared across workspace ---

export const STATUS_OPTIONS = [
  { value: "", label: "Todos" },
  { value: "A", label: "Aprovado" },
  { value: "B", label: "Aprov. c/ Com." },
  { value: "C", label: "Rejeitado" },
  { value: "D", label: "Info Ausente" },
  { value: "E", label: "Adicional" },
];

export const STATUS_LABELS: Record<string, string> = {
  A: "Aprovado",
  B: "Aprov. c/ Com.",
  C: "Rejeitado",
  D: "Info Ausente",
  E: "Adicional",
};

export const PRIORITY_OPTIONS = [
  { value: "", label: "Todas" },
  { value: "ALTA", label: "Alta" },
  { value: "MEDIA", label: "Media" },
  { value: "BAIXA", label: "Baixa" },
];

export const STATUS_COLORS: Record<string, string> = {
  A: "border-l-green-500",
  B: "border-l-yellow-500",
  C: "border-l-red-500",
  D: "border-l-gray-400",
  E: "border-l-blue-500",
};

export const STATUS_BG_COLORS: Record<string, string> = {
  A: "bg-green-500",
  B: "bg-yellow-500",
  C: "bg-red-500",
  D: "bg-gray-400",
  E: "bg-blue-500",
};

export const ANALYSIS_PROFILE_OPTIONS: Array<{
  value: PerfilAnalise;
  label: string;
  description: string;
}> = [
  {
    value: "simples",
    label: "Simples — 10 itens",
    description:
      "Foco nos desvios criticos: seguranca, rejeicoes e bloqueios tecnicos. Ideal para triagem rapida.",
  },
  {
    value: "padrao",
    label: "Padrao — 15 itens",
    description:
      "Cobertura equilibrada dos requisitos criticos e relevantes. Indicado para a maioria das avaliacoes.",
  },
  {
    value: "completa",
    label: "Completa — 20 itens",
    description:
      "Analise abrangente cobrindo todos os requisitos de impacto tecnico, incluindo documentacao e prazos.",
  },
  {
    value: "personalizado",
    label: "Personalizado",
    description:
      "Defina o numero exato de itens que deseja analisar.",
  },
  {
    value: "integral",
    label: "Integral — todos os requisitos",
    description:
      "Segue na integra todos os requisitos listados na tabela de engenharia, sem limite de itens. Recomendado quando a engenharia define uma tabela de requisitos a ser verificada integralmente.",
  },
];

export const STAGE_LABELS: Record<string, string> = {
  queued: "Na fila",
  starting: "Iniciando",
  loading_documents: "Carregando documentos",
  cache_lookup: "Verificando cache",
  cache_hit: "Cache encontrado",
  llm_analysis: "Analisando com IA",
  reference_validation: "Validando referencias",
  optimizing_fields: "Otimizando campos",
  saving_results: "Salvando resultados",
  completed: "Concluido",
  error: "Erro",
  processing: "Processando",
};

// --- Interfaces ---

interface Filters {
  status: string;
  prioridade: string;
  busca: string;
}

interface WorkspaceContextValue {
  parecer: ParecerResponse | null;
  itens: ItemParecerResponse[];
  filteredItens: ItemParecerResponse[];
  selectedItemId: string | null;
  selectedItem: ItemParecerResponse | null;
  documentos: DocumentoResponse[];
  recomendacoes: RecomendacaoResponse[];
  filters: Filters;
  loading: boolean;
  notFound: boolean;
  analyzing: boolean;
  analysisMessage: string;
  analysisStage: string;
  analysisPercent: number;
  analysisError: string;
  analysisProfile: PerfilAnalise;
  customItemCount: number;
  hasResults: boolean;
  hasEngDocs: boolean;
  hasFornDocs: boolean;
  canAnalyze: boolean;
  statusCounts: Record<string, number>;
  showSetupOverride: boolean;
  setShowSetupOverride: (v: boolean) => void;
  showCiclo: boolean;
  setShowCiclo: (v: boolean) => void;
  previewItems: PreviewItemCandidato[];
  previewLoading: boolean;
  previewError: string;
  previewResumo: string;
  showPreviewDialog: boolean;
  setShowPreviewDialog: (v: boolean) => void;
  loadPreview: (feedback?: string) => Promise<void>;
  approveAndAnalyze: () => Promise<void>;
  selectItem: (id: string | null) => void;
  selectNextItem: () => void;
  selectPreviousItem: () => void;
  updateItem: (id: string, data: ItemParecerUpdate) => Promise<void>;
  refreshAll: () => Promise<void>;
  loadDocumentos: () => Promise<void>;
  setFilters: (filters: Partial<Filters>) => void;
  startAnalysis: () => Promise<void>;
  setAnalysisProfile: (profile: PerfilAnalise) => void;
  setCustomItemCount: (n: number) => void;
  deleteParecer: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

// --- Sort: rejected + high priority first ---

function sortByUrgency(items: ItemParecerResponse[]): ItemParecerResponse[] {
  const statusOrder: Record<string, number> = { C: 0, D: 1, B: 2, E: 3, A: 4 };
  const prioOrder: Record<string, number> = { ALTA: 0, MEDIA: 1, BAIXA: 2 };

  return [...items].sort((a, b) => {
    const sa = statusOrder[a.status] ?? 5;
    const sb = statusOrder[b.status] ?? 5;
    if (sa !== sb) return sa - sb;

    const pa = prioOrder[a.prioridade || "MEDIA"] ?? 1;
    const pb = prioOrder[b.prioridade || "MEDIA"] ?? 1;
    if (pa !== pb) return pa - pb;

    return a.numero - b.numero;
  });
}

// --- Provider ---

interface ProviderProps {
  parecerId: string;
  children: ReactNode;
}

export function ParecerWorkspaceProvider({ parecerId, children }: ProviderProps) {
  const router = useRouter();

  const [parecer, setParecer] = useState<ParecerResponse | null>(null);
  const [itens, setItens] = useState<ItemParecerResponse[]>([]);
  const [documentos, setDocumentos] = useState<DocumentoResponse[]>([]);
  const [recomendacoes, setRecomendacoes] = useState<RecomendacaoResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [filters, setFiltersState] = useState<Filters>({
    status: "",
    prioridade: "",
    busca: "",
  });

  const [analyzing, setAnalyzing] = useState(false);
  const [analysisMessage, setAnalysisMessage] = useState("");
  const [analysisStage, setAnalysisStage] = useState("");
  const [analysisPercent, setAnalysisPercent] = useState(0);
  const [analysisError, setAnalysisError] = useState("");
  const [analysisProfile, setAnalysisProfile] =
    useState<PerfilAnalise>("padrao");
  const [customItemCount, setCustomItemCount] = useState(25);
  const [showSetupOverride, setShowSetupOverride] = useState(false);
  const [showCiclo, setShowCiclo] = useState(false);
  const [previewItems, setPreviewItems] = useState<PreviewItemCandidato[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [previewResumo, setPreviewResumo] = useState("");
  const [showPreviewDialog, setShowPreviewDialog] = useState(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // --- Data loading ---

  const loadParecer = useCallback(async () => {
    try {
      const data = await patecApi.pareceres.get(parecerId);
      setParecer(data);
      return data;
    } catch {
      return null;
    }
  }, [parecerId]);

  const loadItens = useCallback(async () => {
    try {
      const data = await patecApi.itens.list(parecerId);
      setItens(data);
    } catch {
      // silently fail
    }
  }, [parecerId]);

  const loadDocumentos = useCallback(async () => {
    try {
      const docs = await patecApi.documentos.list(parecerId);
      setDocumentos(docs);
    } catch {
      // silently fail
    }
  }, [parecerId]);

  const loadRecomendacoes = useCallback(async () => {
    try {
      const recs = await patecApi.recomendacoes.list(parecerId);
      setRecomendacoes(recs);
    } catch {
      // silently fail
    }
  }, [parecerId]);

  const refreshAll = useCallback(async () => {
    await Promise.all([loadParecer(), loadItens(), loadDocumentos(), loadRecomendacoes()]);
  }, [loadParecer, loadItens, loadDocumentos, loadRecomendacoes]);

  // --- Polling ---

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (profile?: PerfilAnalise) => {
      const selectedProfile = ANALYSIS_PROFILE_OPTIONS.find(
        (o) => o.value === profile
      );
      stopPolling();
      setAnalyzing(true);
      setAnalysisMessage(
        selectedProfile
          ? `Iniciando analise (${selectedProfile.label})...`
          : "Iniciando analise..."
      );
      setAnalysisStage("queued");
      setAnalysisPercent(2);
      setAnalysisError("");

      pollingRef.current = setInterval(async () => {
        try {
          const status = await patecApi.analise.status(parecerId);

          if (status.message) setAnalysisMessage(status.message);
          if (typeof status.progress_percent === "number")
            setAnalysisPercent(status.progress_percent);
          if (status.stage) setAnalysisStage(status.stage);

          if (status.status_processamento === "concluido") {
            stopPolling();
            setAnalyzing(false);
            setAnalysisPercent(100);
            setAnalysisStage("completed");
            setAnalysisMessage("Analise concluida com sucesso.");
            setShowSetupOverride(false);
            await refreshAll();
          } else if (status.status_processamento === "erro") {
            stopPolling();
            setAnalyzing(false);
            setAnalysisPercent(100);
            setAnalysisStage("error");
            setAnalysisError(status.message || "Erro durante a analise");
            await loadParecer();
          }
        } catch (err) {
          const message = err instanceof Error ? err.message.toLowerCase() : "";
          if (
            message.includes("nao autenticado") ||
            message.includes("401")
          ) {
            stopPolling();
            setAnalyzing(false);
            setAnalysisError("Sessao expirada. Faca login novamente.");
          }
        }
      }, 3000);
    },
    [parecerId, stopPolling, refreshAll, loadParecer]
  );

  // --- Initial load ---

  useEffect(() => {
    const load = async () => {
      try {
        const data = await patecApi.pareceres.get(parecerId);
        setParecer(data);
        await Promise.all([loadItens(), loadDocumentos(), loadRecomendacoes()]);
        if (data.status_processamento === "processando") {
          startPolling();
        }
      } catch {
        setNotFound(true);
      } finally {
        setLoading(false);
      }
    };
    load();

    return () => stopPolling();
  }, [parecerId, loadItens, loadDocumentos, loadRecomendacoes, startPolling, stopPolling]);

  // --- Filtered & sorted items ---

  const filteredItens = useMemo(() => {
    let result = itens;

    if (filters.status) {
      result = result.filter((i) => i.status === filters.status);
    }
    if (filters.prioridade) {
      result = result.filter((i) => i.prioridade === filters.prioridade);
    }
    if (filters.busca) {
      const q = filters.busca.toLowerCase();
      result = result.filter(
        (i) =>
          i.descricao_requisito.toLowerCase().includes(q) ||
          (i.justificativa_tecnica && i.justificativa_tecnica.toLowerCase().includes(q)) ||
          (i.categoria && i.categoria.toLowerCase().includes(q)) ||
          (i.valor_requerido && i.valor_requerido.toLowerCase().includes(q)) ||
          (i.valor_fornecedor && i.valor_fornecedor.toLowerCase().includes(q))
      );
    }

    return sortByUrgency(result);
  }, [itens, filters]);

  const selectedItem = useMemo(
    () => filteredItens.find((i) => i.id === selectedItemId) ?? null,
    [filteredItens, selectedItemId]
  );

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { A: 0, B: 0, C: 0, D: 0, E: 0 };
    for (const item of itens) {
      counts[item.status] = (counts[item.status] || 0) + 1;
    }
    return counts;
  }, [itens]);

  const hasResults = (parecer?.total_itens ?? 0) > 0;
  const hasEngDocs = documentos.some((d) => d.tipo === "engenharia");
  const hasFornDocs = documentos.some((d) => d.tipo === "fornecedor");
  const canAnalyze =
    hasEngDocs && hasFornDocs && parecer?.status_processamento !== "processando";

  // --- Actions ---

  const selectItem = useCallback((id: string | null) => {
    setSelectedItemId(id);
  }, []);

  const selectNextItem = useCallback(() => {
    if (filteredItens.length === 0) return;
    const idx = filteredItens.findIndex((i) => i.id === selectedItemId);
    const next = idx < filteredItens.length - 1 ? idx + 1 : 0;
    setSelectedItemId(filteredItens[next].id);
  }, [filteredItens, selectedItemId]);

  const selectPreviousItem = useCallback(() => {
    if (filteredItens.length === 0) return;
    const idx = filteredItens.findIndex((i) => i.id === selectedItemId);
    const prev = idx > 0 ? idx - 1 : filteredItens.length - 1;
    setSelectedItemId(filteredItens[prev].id);
  }, [filteredItens, selectedItemId]);

  const updateItem = useCallback(
    async (id: string, data: ItemParecerUpdate) => {
      await patecApi.itens.update(parecerId, id, data);
      await Promise.all([loadItens(), loadParecer()]);
    },
    [parecerId, loadItens, loadParecer]
  );

  const setFilters = useCallback((partial: Partial<Filters>) => {
    setFiltersState((prev) => ({ ...prev, ...partial }));
  }, []);

  const startAnalysis = useCallback(async () => {
    if (!parecer) return;
    setAnalysisError("");
    setShowSetupOverride(false);
    const resolvedProfile: PerfilAnalise =
      analysisProfile === "personalizado"
        ? `custom_${Math.max(1, Math.min(customItemCount, 100))}`
        : analysisProfile;
    try {
      await patecApi.analise.iniciar(parecer.id, resolvedProfile);
      startPolling(resolvedProfile);
    } catch (err) {
      setAnalysisError(
        err instanceof Error ? err.message : "Erro ao iniciar analise"
      );
    }
  }, [parecer, analysisProfile, customItemCount, startPolling]);

  const loadPreview = useCallback(async (feedback?: string) => {
    if (!parecer) return;
    setPreviewLoading(true);
    setPreviewError("");
    const resolvedProfile: PerfilAnalise =
      analysisProfile === "personalizado"
        ? `custom_${Math.max(1, Math.min(customItemCount, 100))}`
        : analysisProfile;
    try {
      const result = await patecApi.analise.preview(parecer.id, resolvedProfile, feedback);
      setPreviewItems(result.itens_candidatos);
      setPreviewResumo(result.resumo);
      setShowPreviewDialog(true);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "Erro ao gerar preview");
    } finally {
      setPreviewLoading(false);
    }
  }, [parecer, analysisProfile, customItemCount]);

  const approveAndAnalyze = useCallback(async () => {
    if (!parecer) return;
    setShowPreviewDialog(false);
    setAnalysisError("");
    const resolvedProfile: PerfilAnalise =
      analysisProfile === "personalizado"
        ? `custom_${Math.max(1, Math.min(customItemCount, 100))}`
        : analysisProfile;
    try {
      await patecApi.analise.iniciar(parecer.id, resolvedProfile, previewItems);
      startPolling(resolvedProfile);
    } catch (err) {
      setAnalysisError(err instanceof Error ? err.message : "Erro ao iniciar analise");
    }
  }, [parecer, analysisProfile, customItemCount, previewItems, startPolling]);

  const deleteParecer = useCallback(async () => {
    if (!parecer) return;
    await patecApi.pareceres.delete(parecer.id);
    router.push("/dashboard/parecer-tecnico");
  }, [parecer, router]);

  // --- Context value ---

  const value: WorkspaceContextValue = useMemo(
    () => ({
      parecer,
      itens,
      filteredItens,
      selectedItemId,
      selectedItem,
      documentos,
      recomendacoes,
      filters,
      loading,
      notFound,
      analyzing,
      analysisMessage,
      analysisStage,
      analysisPercent,
      analysisError,
      analysisProfile,
      customItemCount,
      hasResults,
      hasEngDocs,
      hasFornDocs,
      canAnalyze,
      statusCounts,
      showSetupOverride,
      setShowSetupOverride,
      showCiclo,
      setShowCiclo,
      previewItems,
      previewLoading,
      previewError,
      previewResumo,
      showPreviewDialog,
      setShowPreviewDialog,
      loadPreview,
      approveAndAnalyze,
      selectItem,
      selectNextItem,
      selectPreviousItem,
      updateItem,
      refreshAll,
      loadDocumentos,
      setFilters,
      startAnalysis,
      setAnalysisProfile,
      setCustomItemCount,
      deleteParecer,
    }),
    [
      parecer,
      itens,
      filteredItens,
      selectedItemId,
      selectedItem,
      documentos,
      recomendacoes,
      filters,
      loading,
      notFound,
      analyzing,
      analysisMessage,
      analysisStage,
      analysisPercent,
      analysisError,
      analysisProfile,
      customItemCount,
      hasResults,
      hasEngDocs,
      hasFornDocs,
      canAnalyze,
      statusCounts,
      showSetupOverride,
      showCiclo,
      previewItems,
      previewLoading,
      previewError,
      previewResumo,
      showPreviewDialog,
      loadPreview,
      approveAndAnalyze,
      selectItem,
      selectNextItem,
      selectPreviousItem,
      updateItem,
      refreshAll,
      loadDocumentos,
      setFilters,
      startAnalysis,
      setAnalysisProfile,
      setCustomItemCount,
      deleteParecer,
    ]
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    throw new Error("useWorkspace must be used within ParecerWorkspaceProvider");
  }
  return ctx;
}
