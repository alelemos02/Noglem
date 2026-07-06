"use client";

import { useState, useCallback } from "react";
import { FileText, Download, X, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { Dropzone } from "@/components/ui/dropzone";
import { Alert } from "@/components/ui/alert";
import { toast } from "@/components/ui/toast";

interface Annotation {
  document_number: string;
  page: number;
  annotation_type: string;
  author: string;
  date: string;
  comment: string;
  marked_text: string;
  subject: string;
  ai_analysis: string;
}

interface FileResult {
  filename: string;
  annotations: Annotation[];
  error?: string;
  page_count: number;
}

interface ProcessResponse {
  results: FileResult[];
  total_annotations: number;
  total_files: number;
}

const TYPE_COLORS: Record<string, string> = {
  Text: "bg-warning-subtle text-warning",
  FreeText: "bg-success-subtle text-success",
  Highlight: "bg-info-subtle text-info",
  Underline: "bg-accent-subtle text-accent",
  StrikeOut: "bg-danger-subtle text-danger",
  Squiggly: "bg-surface-1 text-fg-muted",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function PdfCommentsPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [response, setResponse] = useState<ProcessResponse | null>(null);
  const [error, setError] = useState("");

  const addFiles = useCallback((incoming: File[]) => {
    const pdfs = incoming.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (pdfs.length < incoming.length) {
      setError("Apenas arquivos PDF são aceitos.");
    } else {
      setError("");
    }
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name));
      return [...prev, ...pdfs.filter((f) => !existing.has(f.name))];
    });
    setResponse(null);
  }, []);

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
    setResponse(null);
  };

  const reset = () => {
    setFiles([]);
    setResponse(null);
    setError("");
  };

  const handleProcess = async () => {
    if (!files.length || isProcessing) return;
    setIsProcessing(true);
    setError("");

    try {
      const formData = new FormData();
      for (const f of files) formData.append("files", f);

      const res = await fetch("/api/pdf-comments", { method: "POST", body: formData });

      if (res.status === 413) {
        throw new Error("Arquivo muito grande para o upload via browser (limite ~4 MB). Reduza o arquivo e tente novamente.");
      }

      let data: ProcessResponse & { error?: string };
      try {
        data = await res.json();
      } catch {
        throw new Error(`Resposta inesperada do servidor (HTTP ${res.status}). Tente novamente.`);
      }

      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setResponse(data);
      toast.success("Extração concluída", {
        description: `${data.total_annotations} comentário(s) em ${data.total_files} arquivo(s).`,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleExport = async () => {
    if (!response || isExporting) return;
    setIsExporting(true);

    try {
      const res = await fetch("/api/pdf-comments/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ results: response.results }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ error: "Erro desconhecido" }));
        throw new Error(data.error);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "comentarios.xlsx";
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Excel gerado", { description: "comentarios.xlsx" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao gerar Excel");
    } finally {
      setIsExporting(false);
    }
  };

  const allAnnotations = response?.results.flatMap((r) => r.annotations ?? []) ?? [];
  const preview = allAnnotations.slice(0, 50);
  const hasErrors = response?.results.some((r) => r.error) ?? false;

  return (
    <div className="space-y-6">
      <PageHeader tool="pdf-comments" />

      {/* Upload */}
      <Card className="gap-3 py-4">
        <CardHeader>
          <CardTitle className="text-sm">Selecionar arquivos PDF</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Dropzone
            onFiles={addFiles}
            accept=".pdf"
            multiple
            label="Arraste PDFs ou clique para selecionar"
            hint="Múltiplos arquivos · Recomendado até 4 MB por arquivo"
            disabled={isProcessing}
          />

          {/* File list */}
          {files.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-edge">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-edge bg-surface-1">
                    <th className="px-4 py-2 text-left font-medium text-fg-muted">Arquivo</th>
                    <th className="px-4 py-2 text-right font-medium text-fg-muted">Tamanho</th>
                    <th className="w-10 px-2 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {files.map((f, idx) => {
                    const isOversized = f.size > 4 * 1024 * 1024;
                    return (
                    <tr key={idx} className="border-b border-edge last:border-0">
                      <td className="flex items-center gap-2 px-4 py-2">
                        <FileText className="h-4 w-4 shrink-0 text-fg-subtle" />
                        <span className="truncate text-fg">{f.name}</span>
                        {isOversized && (
                          <span className="ml-1 shrink-0 rounded bg-warning-subtle px-1.5 py-0.5 text-xs text-warning">
                            &gt;4 MB — pode falhar
                          </span>
                        )}
                      </td>
                      <td className={`px-4 py-2 text-right font-mono tabular-nums ${isOversized ? "text-warning" : "text-fg-muted"}`}>
                        {formatBytes(f.size)}
                      </td>
                      <td className="px-2 py-2 text-center">
                        <button
                          onClick={() => removeFile(idx)}
                          disabled={isProcessing}
                          className="text-fg-subtle hover:text-danger disabled:opacity-40"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  )})}
                </tbody>
              </table>
            </div>
          )}

          {error && <Alert variant="danger">{error}</Alert>}

          <div className="flex gap-3">
            <Button
              onClick={handleProcess}
              disabled={files.length === 0}
              loading={isProcessing}
              className="flex-1"
            >
              {isProcessing ? "Processando..." : "Extrair comentários"}
            </Button>
            <Button variant="outline" onClick={reset} disabled={isProcessing}>
              Limpar
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {response && (
        <>
          {/* Summary bar */}
          <div className="flex items-center gap-7 rounded-lg border border-edge bg-surface-1 px-5 py-4">
            <div>
              <p className="microlabel mb-0.5 text-[10px]">Comentários</p>
              <p className="font-mono text-xl font-medium tabular-nums text-fg">
                {response.total_annotations}
              </p>
            </div>
            <div>
              <p className="microlabel mb-0.5 text-[10px]">Arquivos</p>
              <p className="font-mono text-xl font-medium tabular-nums text-fg">
                {response.total_files}
              </p>
            </div>
            {hasErrors && (
              <div className="flex items-center gap-1.5 text-sm text-danger">
                <AlertTriangle className="h-4 w-4" />
                {response.results.filter((r) => r.error).length} com erro
              </div>
            )}
            <div className="ml-auto">
              <Button
                onClick={handleExport}
                disabled={isExporting || response.total_annotations === 0}
                loading={isExporting}
                className="gap-2"
              >
                <Download className="h-4 w-4" />
                {isExporting ? "Gerando..." : "Baixar Excel"}
              </Button>
            </div>
          </div>

          {/* Per-file status */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-fg-muted">
                Arquivos processados
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {response.results.map((r, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between rounded-lg border border-edge bg-surface-1 px-4 py-2 text-sm"
                >
                  <div className="flex items-center gap-2 truncate">
                    {r.error ? (
                      <AlertTriangle className="h-4 w-4 shrink-0 text-danger" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                    )}
                    <span className="truncate text-fg">{r.filename}</span>
                  </div>
                  <span className="ml-4 shrink-0 font-mono tabular-nums text-fg-muted">
                    {r.error ? (
                      <span className="text-danger">{r.error}</span>
                    ) : (
                      `${r.annotations?.length ?? 0} comentários · ${r.page_count} pág.`
                    )}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* No annotations warning */}
          {response.total_annotations === 0 && !hasErrors && (
            <Alert variant="warning">
              Nenhuma anotação encontrada. Verifique se os PDFs possuem comentários
              nativos (adicionados via Acrobat ou similar).
            </Alert>
          )}

          {/* Annotations table */}
          {preview.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  Pré-visualização
                  {allAnnotations.length > 50 && (
                    <span className="ml-2 text-xs font-normal text-fg-subtle">
                      (50 de {allAnnotations.length} — baixe o Excel para ver todos)
                    </span>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="max-h-[480px] overflow-auto">
                  <table className="w-full min-w-[800px] text-xs">
                    <thead className="sticky top-0 z-10 bg-surface-1">
                      <tr className="border-b border-edge">
                        <th className="px-3 py-2 text-left font-medium text-fg-muted">Documento</th>
                        <th className="w-12 px-3 py-2 text-center font-medium text-fg-muted">Pág.</th>
                        <th className="w-28 px-3 py-2 text-left font-medium text-fg-muted">Tipo</th>
                        <th className="w-32 px-3 py-2 text-left font-medium text-fg-muted">Autor</th>
                        <th className="w-32 px-3 py-2 text-left font-medium text-fg-muted">Data</th>
                        <th className="px-3 py-2 text-left font-medium text-fg-muted">Comentário</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.map((annot, idx) => (
                        <tr
                          key={idx}
                          className="border-b border-edge last:border-0 odd:bg-canvas even:bg-surface-1"
                        >
                          <td className="max-w-[180px] truncate px-3 py-2 text-fg" title={annot.document_number}>
                            {annot.document_number}
                          </td>
                          <td className="px-3 py-2 text-center font-mono tabular-nums text-fg-muted">
                            {annot.page}
                          </td>
                          <td className="px-3 py-2">
                            <Badge
                              variant="secondary"
                              className={`text-xs ${TYPE_COLORS[annot.annotation_type] ?? ""}`}
                            >
                              {annot.annotation_type}
                            </Badge>
                          </td>
                          <td className="max-w-[120px] truncate px-3 py-2 text-fg-muted">
                            {annot.author || "—"}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 font-mono tabular-nums text-fg-subtle">
                            {annot.date || "—"}
                          </td>
                          <td className="max-w-xs px-3 py-2 text-fg">
                            <span className="line-clamp-2 whitespace-pre-wrap break-words">
                              {annot.comment || annot.marked_text || "—"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
