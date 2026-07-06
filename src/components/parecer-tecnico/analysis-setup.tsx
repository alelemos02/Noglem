"use client";

import { Button } from "@/components/ui/button";
import { FileUploadZone } from "./file-upload-zone";
import { EstimativaCusto } from "./estimativa-custo";
import { PreviewDialog } from "./preview-dialog";
import {
  useWorkspace,
  ANALYSIS_PROFILE_OPTIONS,
  STAGE_LABELS,
} from "./workspace-context";
import type { PerfilAnalise } from "@/lib/patec-api";

export function AnalysisSetup() {
  const {
    parecer,
    documentos,
    loadDocumentos,
    analyzing,
    analysisMessage,
    analysisStage,
    analysisPercent,
    analysisError,
    analysisProfile,
    setAnalysisProfile,
    customItemCount,
    setCustomItemCount,
    startAnalysis,
    canAnalyze,
    hasEngDocs,
    hasFornDocs,
    hasResults,
    previewLoading,
    previewError,
    loadPreview,
  } = useWorkspace();

  if (!parecer) return null;

  const clampedPercent = Math.max(0, Math.min(100, analysisPercent));
  const currentStageLabel = STAGE_LABELS[analysisStage] || "Processando";
  const selectedProfile =
    ANALYSIS_PROFILE_OPTIONS.find((o) => o.value === analysisProfile) ||
    ANALYSIS_PROFILE_OPTIONS[1];

  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="w-full max-w-2xl space-y-6">
        {/* Title */}
        <div className="text-center">
          <h2 className="text-xl font-bold text-fg">
            {hasResults ? "Reanalisar Parecer" : "Configurar Analise"}
          </h2>
          <p className="mt-1 text-sm text-fg-muted">
            {hasResults
              ? "Execute uma nova analise com os documentos atuais."
              : "Faca upload dos documentos e inicie a analise com IA."}
          </p>
        </div>

        {/* Document upload */}
        <div className="rounded-lg border border-edge bg-surface-1 p-6">
          <h3 className="mb-3 text-sm font-bold text-fg">
            Documentos
          </h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <FileUploadZone
              parecerId={parecer.id}
              tipo="engenharia"
              label="Documentos da Engenharia"
              documentos={documentos}
              onUploadComplete={loadDocumentos}
            />
            <FileUploadZone
              parecerId={parecer.id}
              tipo="fornecedor"
              label="Documentos do Fornecedor"
              documentos={documentos}
              onUploadComplete={loadDocumentos}
            />
          </div>
          <div className="mt-4 border-t border-edge pt-4">
            <FileUploadZone
              parecerId={parecer.id}
              tipo="anexo_engenharia"
              label="Anexos / Documentos Complementares (opcional)"
              documentos={documentos}
              onUploadComplete={loadDocumentos}
            />
            <p className="mt-1.5 text-xs text-fg-subtle">
              Datasheets de referencia, normas internas, especificacoes gerais — usados como contexto de apoio pela IA.
            </p>
          </div>
        </div>

        {/* Analysis in progress */}
        {analyzing ? (
          <div className="space-y-4 rounded-lg border border-edge bg-surface-1 p-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-fg-muted">
                <span>Etapa: {currentStageLabel}</span>
                <span>{clampedPercent}%</span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-white/10">
                <div
                  className="h-2.5 rounded-full bg-accent transition-all duration-300"
                  style={{ width: `${clampedPercent}%` }}
                />
              </div>
            </div>
            <p className="text-center text-sm font-medium text-accent">
              Processando analise...
            </p>
            {analysisMessage && (
              <p className="text-center text-sm text-fg-muted">
                {analysisMessage}
              </p>
            )}
            <p className="text-center text-xs text-fg-subtle">
              Este processo pode levar alguns minutos dependendo do tamanho dos
              documentos.
            </p>
          </div>
        ) : (
          <>
            {/* Profile selector */}
            {canAnalyze && (
              <div className="rounded-lg border border-edge bg-surface-1 p-6">
                <p className="text-sm font-semibold text-fg">
                  Quantidade de Itens a Analisar
                </p>
                <p className="mb-3 text-xs text-fg-muted">
                  Mais itens = analise mais detalhada e tempo maior de processamento.
                </p>
                <select
                  value={analysisProfile}
                  onChange={(e) =>
                    setAnalysisProfile(e.target.value as PerfilAnalise)
                  }
                  className="w-full rounded-md border border-edge bg-canvas px-3 py-2 text-sm text-fg outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                >
                  {ANALYSIS_PROFILE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                {analysisProfile === "personalizado" && (
                  <div className="mt-3 flex items-center gap-3">
                    <label className="text-xs text-fg-muted whitespace-nowrap">
                      Numero de itens:
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={customItemCount}
                      onChange={(e) => {
                        const v = parseInt(e.target.value, 10);
                        if (!isNaN(v)) setCustomItemCount(Math.max(1, Math.min(v, 100)));
                      }}
                      className="w-24 rounded-md border border-edge bg-canvas px-3 py-1.5 text-sm text-fg outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                    />
                    <span className="text-xs text-fg-subtle">(max 100)</span>
                  </div>
                )}
                <p className="mt-2 text-xs text-fg-muted">
                  {selectedProfile.description}
                </p>
              </div>
            )}

            {/* Warnings */}
            {!hasEngDocs && (
              <p className="text-center text-sm text-warning">
                Faca upload de pelo menos um documento de engenharia.
              </p>
            )}
            {!hasFornDocs && (
              <p className="text-center text-sm text-warning">
                Faca upload de pelo menos um documento do fornecedor.
              </p>
            )}

            {/* Preview error */}
            {previewError && (
              <div className="rounded-md bg-danger-subtle p-4">
                <p className="text-sm font-medium text-danger">Erro ao carregar prévia</p>
                <p className="text-sm text-danger/80">{previewError}</p>
              </div>
            )}

            {/* Error */}
            {analysisError && (
              <div className="rounded-md bg-danger-subtle p-4">
                <p className="text-sm font-medium text-danger">
                  {parecer.status_processamento === "erro"
                    ? "Erro durante a analise"
                    : "Erro"}
                </p>
                <p className="text-sm text-danger-text">
                  {parecer.comentario_geral || analysisError}
                </p>
              </div>
            )}

            {/* Action button */}
            <div className="space-y-3 text-center">
              {hasResults ? (
                <Button
                  onClick={startAnalysis}
                  disabled={!canAnalyze}
                  size="lg"
                >
                  {parecer.status_processamento === "erro"
                    ? "Tentar Novamente"
                    : "Reanalisar"}
                </Button>
              ) : (
                <Button
                  onClick={() => loadPreview()}
                  disabled={!canAnalyze}
                  loading={previewLoading}
                  size="lg"
                >
                  Avançar
                </Button>
              )}

              {canAnalyze && !hasResults && (
                <>
                  <p className="text-xs text-fg-subtle">
                    Você poderá revisar os requisitos antes de iniciar a análise.
                  </p>
                  <EstimativaCusto parecerId={parecer.id} />
                </>
              )}
            </div>
          </>
        )}
      </div>

      <PreviewDialog />
    </div>
  );
}
