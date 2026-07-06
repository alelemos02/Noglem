"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogBody,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useWorkspace } from "./workspace-context";

const PRIORIDADE_VARIANT: Record<string, "error" | "warning" | "secondary"> = {
  ALTA: "error",
  MEDIA: "warning",
  BAIXA: "secondary",
};

export function PreviewDialog() {
  const {
    previewItems,
    previewLoading,
    previewError,
    previewResumo,
    showPreviewDialog,
    setShowPreviewDialog,
    loadPreview,
    approveAndAnalyze,
  } = useWorkspace();

  const [localFeedback, setLocalFeedback] = useState("");
  const [regenerating, setRegenerating] = useState(false);

  const handleRegenerate = async () => {
    if (!localFeedback.trim()) return;
    setRegenerating(true);
    await loadPreview(localFeedback);
    setRegenerating(false);
    setLocalFeedback("");
  };

  const isLoading = previewLoading || regenerating;

  return (
    <Dialog open={showPreviewDialog} onOpenChange={setShowPreviewDialog}>
      <DialogContent>
        <DialogHeader>
          <div>
            <DialogTitle>Revisão de Itens — Pré-visualização</DialogTitle>
            <DialogDescription>
              Revise os requisitos que serão verificados. Use o campo de feedback para ajustar antes de aprovar.
            </DialogDescription>
          </div>
        </DialogHeader>

        <DialogBody>
          {/* Resumo executivo */}
          {previewResumo && !isLoading && (
            <div className="mb-4 rounded-lg bg-info-subtle p-3">
              <p className="text-sm text-info">{previewResumo}</p>
            </div>
          )}

          {/* Contagem */}
          {previewItems.length > 0 && !isLoading && (
            <p className="mb-3 font-mono tabular-nums text-xs text-fg-muted">
              {previewItems.length}{" "}
              {previewItems.length === 1 ? "requisito identificado" : "requisitos identificados"}
            </p>
          )}

          {/* Erro */}
          {previewError && (
            <div className="mb-4 rounded-lg bg-danger-subtle p-3">
              <p className="text-sm text-danger">{previewError}</p>
            </div>
          )}

          {/* Skeleton de loading */}
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full rounded-lg" />
              ))}
            </div>
          ) : (
            /* Lista de itens */
            <div className="space-y-2">
              {previewItems.map((item) => (
                <div
                  key={item.numero}
                  className="rounded-lg border border-edge bg-surface-1 p-3"
                >
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 w-6 shrink-0 font-mono tabular-nums text-xs text-fg-subtle">
                      {item.numero}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <span className="text-xs font-medium text-fg-muted">
                          {item.categoria}
                        </span>
                        <Badge variant={PRIORIDADE_VARIANT[item.prioridade] ?? "secondary"} dot>
                          {item.prioridade}
                        </Badge>
                        {item.norma_referencia && (
                          <Badge variant="outline">
                            {item.norma_referencia}
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-fg">{item.descricao_requisito}</p>
                      {item.referencia_engenharia && (
                        <p className="mt-1 truncate text-xs text-fg-subtle">
                          Ref: {item.referencia_engenharia}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Feedback */}
          <div className="mt-6 space-y-2">
            <label className="block text-sm font-medium text-fg">
              Feedback para ajuste (opcional)
            </label>
            <p className="text-xs text-fg-muted">
              Descreva o que mudar: “adicionar item sobre protocolo HART”, “remover itens de documentação”, “focar apenas em segurança”, etc.
            </p>
            <textarea
              value={localFeedback}
              onChange={(e) => setLocalFeedback(e.target.value)}
              placeholder='Ex: "Adicionar item específico sobre certificação ATEX. Remover requisitos de prazo de entrega."'
              rows={3}
              className="w-full resize-none rounded-lg border border-edge bg-canvas px-3 py-2 text-sm text-fg placeholder:text-fg-subtle outline-none focus:border-accent focus:ring-1 focus:ring-accent"
            />
          </div>
        </DialogBody>

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => setShowPreviewDialog(false)}
            disabled={isLoading}
          >
            Cancelar
          </Button>
          <Button
            variant="secondary"
            onClick={handleRegenerate}
            disabled={isLoading || !localFeedback.trim()}
            loading={regenerating}
          >
            Regenerar
          </Button>
          <Button
            onClick={approveAndAnalyze}
            disabled={previewItems.length === 0 || isLoading}
          >
            Aprovar e Analisar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
