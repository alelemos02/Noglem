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
          <h2 className="text-xl font-bold text-text-primary">
            {hasResults ? "Reanalisar Parecer" : "Configurar Analise"}
          </h2>
          <p className="mt-1 text-sm text-text-secondary">
            {hasResults
              ? "Execute uma nova analise com os documentos atuais."
              : "Faca upload dos documentos e inicie a analise com IA."}
          </p>
        </div>

        {/* Document upload */}
        <div className="rounded-lg border border-border bg-surface p-6">
          <h3 className="mb-3 text-sm font-bold text-text-primary">
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
          <div className="mt-4 border-t border-border pt-4">
            <FileUploadZone
              parecerId={parecer.id}
              tipo="anexo_engenharia"
              label="Anexos / Documentos Complementares (opcional)"
              documentos={documentos}
              onUploadComplete={loadDocumentos}
            />
            <p className="mt-1.5 text-xs text-text-tertiary">
              Datasheets de referencia, normas internas, especificacoes gerais — usados como contexto de apoio pela IA.
            </p>
          </div>
        </div>

        {/* Analysis in progress */}
        {analyzing ? (
          <div className="space-y-4 rounded-lg border border-border bg-surface p-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-text-secondary">
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
              <p className="text-center text-sm text-text-secondary">
                {analysisMessage}
              </p>
            )}
            <p className="text-center text-xs text-text-tertiary">
              Este processo pode levar alguns minutos dependendo do tamanho dos
              documentos.
            </p>
          </div>
        ) : (
          <>
            {/* Profile selector */}
            {canAnalyze && (
              <div className="rounded-lg border border-border bg-surface p-6">
                <p className="text-sm font-semibold text-text-primary">
                  Quantidade de Itens a Analisar
                </p>
                <p className="mb-3 text-xs text-text-secondary">
                  Mais itens = analise mais detalhada e tempo maior de processamento.
                </p>
                <select
                  value={analysisProfile}
                  onChange={(e) =>
                    setAnalysisProfile(e.target.value as PerfilAnalise)
                  }
                  className="w-full rounded-md border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                >
                  {ANALYSIS_PROFILE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                {analysisProfile === "personalizado" && (
                  <div className="mt-3 flex items-center gap-3">
                    <label className="text-xs text-text-secondary whitespace-nowrap">
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
                      className="w-24 rounded-md border border-border bg-bg-primary px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                    />
                    <span className="text-xs text-text-tertiary">(max 100)</span>
                  </div>
                )}
                <p className="mt-2 text-xs text-text-secondary">
                  {selectedProfile.description}
                </p>
              </div>
            )}

            {/* Warnings */}
            {!hasEngDocs && (
              <p className="text-center text-sm text-yellow-400">
                Faca upload de pelo menos um documento de engenharia.
              </p>
            )}
            {!hasFornDocs && (
              <p className="text-center text-sm text-yellow-400">
                Faca upload de pelo menos um documento do fornecedor.
              </p>
            )}

            {/* Error */}
            {analysisError && (
              <div className="rounded-md bg-red-900/20 p-4">
                <p className="text-sm font-medium text-red-400">
                  {parecer.status_processamento === "erro"
                    ? "Erro durante a analise"
                    : "Erro"}
                </p>
                <p className="text-sm text-red-400/80">
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
                  <p className="text-xs text-text-tertiary">
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
