"use client";

import { useState, useCallback } from "react";
import { MessageSquareText, Upload, FileText, Download, X, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

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
  Text: "bg-warning-muted text-warning",
  FreeText: "bg-success-muted text-success",
  Highlight: "bg-info-muted text-info",
  Underline: "bg-accent-muted text-accent",
  StrikeOut: "bg-error-muted text-error",
  Squiggly: "bg-surface text-text-secondary",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function PdfCommentsPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
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

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      addFiles(Array.from(e.dataTransfer.files));
    },
    [addFiles]
  );

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(Array.from(e.target.files));
    e.target.value = "";
  };

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
      const data = await res.json();

      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setResponse(data);
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
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-info-muted">
          <MessageSquareText className="h-6 w-6 text-info" />
        </div>
        <div>
          <h1 className="font-heading text-2xl font-bold text-text-primary">MarkTrace</h1>
          <p className="text-sm text-text-secondary">
            Extração automática de comentários e anotações de revisão em PDFs
          </p>
        </div>
        <Badge variant="info" className="ml-auto">
          Beta
        </Badge>
      </div>

      {/* Upload */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Selecionar arquivos PDF</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            className={`flex min-h-[160px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors ${
              isDragging ? "border-accent bg-accent-muted" : "border-border hover:border-accent/50"
            }`}
          >
            <label className="flex cursor-pointer flex-col items-center gap-2 px-6 py-4 text-center">
              <Upload className="h-10 w-10 text-text-tertiary" />
              <p className="font-medium text-text-secondary">
                Arraste PDFs aqui ou{" "}
                <span className="text-accent underline">clique para selecionar</span>
              </p>
              <p className="text-xs text-text-tertiary">
                Múltiplos arquivos · Máx. 100 MB por arquivo
              </p>
              <input
                type="file"
                multiple
                accept=".pdf"
                onChange={handleFileInput}
                className="hidden"
              />
            </label>
          </div>

          {/* File list */}
          {files.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-bg-secondary">
                    <th className="px-4 py-2 text-left font-medium text-text-secondary">Arquivo</th>
                    <th className="px-4 py-2 text-right font-medium text-text-secondary">Tamanho</th>
                    <th className="w-10 px-2 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {files.map((f, idx) => (
                    <tr key={idx} className="border-b border-border last:border-0">
                      <td className="flex items-center gap-2 px-4 py-2">
                        <FileText className="h-4 w-4 shrink-0 text-text-tertiary" />
                        <span className="truncate text-text-primary">{f.name}</span>
                      </td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums text-text-secondary">
                        {formatBytes(f.size)}
                      </td>
                      <td className="px-2 py-2 text-center">
                        <button
                          onClick={() => removeFile(idx)}
                          disabled={isProcessing}
                          className="text-text-tertiary hover:text-error disabled:opacity-40"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-error/30 bg-error-muted px-4 py-3 text-sm text-error">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <Button
              onClick={handleProcess}
              disabled={files.length === 0 || isProcessing}
              loading={isProcessing}
              className="flex-1"
            >
              {isProcessing ? "Processando..." : "Extrair Comentários"}
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
          <div className="flex items-center gap-6 rounded-lg border border-border bg-surface p-4">
            <div className="text-center">
              <p className="font-mono tabular-nums text-2xl font-bold text-text-primary">
                {response.total_annotations}
              </p>
              <p className="text-xs text-text-secondary">Comentários</p>
            </div>
            <div className="h-8 w-px bg-border" />
            <div className="text-center">
              <p className="font-mono tabular-nums text-2xl font-bold text-text-primary">
                {response.total_files}
              </p>
              <p className="text-xs text-text-secondary">Arquivos</p>
            </div>
            {hasErrors && (
              <>
                <div className="h-8 w-px bg-border" />
                <div className="flex items-center gap-1 text-sm text-error">
                  <AlertTriangle className="h-4 w-4" />
                  {response.results.filter((r) => r.error).length} com erro
                </div>
              </>
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
              <CardTitle className="text-sm font-medium text-text-secondary">
                Arquivos processados
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {response.results.map((r, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between rounded-lg border border-border bg-bg-secondary px-4 py-2 text-sm"
                >
                  <div className="flex items-center gap-2 truncate">
                    {r.error ? (
                      <AlertTriangle className="h-4 w-4 shrink-0 text-error" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                    )}
                    <span className="truncate text-text-primary">{r.filename}</span>
                  </div>
                  <span className="ml-4 shrink-0 font-mono tabular-nums text-text-secondary">
                    {r.error ? (
                      <span className="text-error">{r.error}</span>
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
            <div className="flex items-center gap-3 rounded-lg border border-warning/30 bg-warning-muted px-4 py-3 text-sm text-warning">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              Nenhuma anotação encontrada. Verifique se os PDFs possuem comentários nativos (adicionados via Acrobat ou similar).
            </div>
          )}

          {/* Annotations table */}
          {preview.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  Pré-visualização
                  {allAnnotations.length > 50 && (
                    <span className="ml-2 text-xs font-normal text-text-tertiary">
                      (50 de {allAnnotations.length} — baixe o Excel para ver todos)
                    </span>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="max-h-[480px] overflow-auto">
                  <table className="w-full min-w-[800px] text-xs">
                    <thead className="sticky top-0 z-10 bg-bg-secondary">
                      <tr className="border-b border-border">
                        <th className="px-3 py-2 text-left font-medium text-text-secondary">Documento</th>
                        <th className="w-12 px-3 py-2 text-center font-medium text-text-secondary">Pág.</th>
                        <th className="w-28 px-3 py-2 text-left font-medium text-text-secondary">Tipo</th>
                        <th className="w-32 px-3 py-2 text-left font-medium text-text-secondary">Autor</th>
                        <th className="w-32 px-3 py-2 text-left font-medium text-text-secondary">Data</th>
                        <th className="px-3 py-2 text-left font-medium text-text-secondary">Comentário</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.map((annot, idx) => (
                        <tr
                          key={idx}
                          className="border-b border-border last:border-0 odd:bg-bg-primary even:bg-bg-secondary"
                        >
                          <td className="max-w-[180px] truncate px-3 py-2 text-text-primary" title={annot.document_number}>
                            {annot.document_number}
                          </td>
                          <td className="px-3 py-2 text-center font-mono tabular-nums text-text-secondary">
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
                          <td className="max-w-[120px] truncate px-3 py-2 text-text-secondary">
                            {annot.author || "—"}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 font-mono tabular-nums text-text-tertiary">
                            {annot.date || "—"}
                          </td>
                          <td className="max-w-xs px-3 py-2 text-text-primary">
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
