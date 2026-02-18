"use client";

import { useState, useCallback } from "react";
import { Table, Upload, FileText, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface TableData {
  page: number;
  table_index: number;
  headers: string[];
  rows: string[][];
}

interface ExtractResult {
  filename: string;
  total_pages: number;
  tables_found: number;
  tables: TableData[];
}

export default function PdfExtractorPage() {
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState("");

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile?.type === "application/pdf") {
      setFile(droppedFile);
      setResult(null);
      setError("");
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResult(null);
      setError("");
    }
  };

  const handleExtract = async () => {
    if (!file) return;

    setIsProcessing(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/pdf/extract", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Erro na extração");
      }

      setResult(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro desconhecido";
      setError(message);
      console.error("Erro na extração:", err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownload = async () => {
    if (!file) return;

    setIsDownloading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        "/api/pdf/extract/download",
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error("Erro ao gerar Excel");
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${file.name.replace(".pdf", "")}_tabelas.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro desconhecido";
      setError(message);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-success-muted">
          <Table className="h-6 w-6 text-success" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Extrator de Tabelas</h1>
          <p className="text-muted-foreground">
            Extraia tabelas de PDFs e exporte para Excel
          </p>
        </div>
        <Badge variant="secondary" className="ml-auto">Beta</Badge>
      </div>

      {/* Upload Area */}
      <Card>
        <CardHeader>
          <CardTitle>Upload de PDF</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            onDrop={handleDrop}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            className={`flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors ${
              isDragging
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50"
            }`}
          >
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <FileText className="h-12 w-12 text-success" />
                <p className="font-medium">{file.name}</p>
                <p className="text-sm text-muted-foreground">
                  {(file.size / 1024 / 1024).toFixed(2)} MB
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setFile(null);
                    setResult(null);
                    setError("");
                  }}
                >
                  Remover
                </Button>
              </div>
            ) : (
              <label className="flex cursor-pointer flex-col items-center gap-2">
                <Upload className="h-12 w-12 text-muted-foreground" />
                <p className="font-medium">
                  Arraste um PDF ou clique para selecionar
                </p>
                <p className="text-sm text-muted-foreground">
                  Apenas arquivos PDF são aceitos
                </p>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </label>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Error Message */}
      {error && (
        <div className="rounded-lg border border-error/50 bg-error-muted p-4 text-center text-sm text-error-text">
          {error}
        </div>
      )}

      {/* Extract Button */}
      {file && !result && (
        <div className="flex justify-center">
          <Button
            size="lg"
            onClick={handleExtract}
            disabled={isProcessing}
            className="gap-2"
          >
            {isProcessing ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                Extraindo tabelas...
              </>
            ) : (
              <>
                <Table className="h-4 w-4" />
                Extrair Tabelas
              </>
            )}
          </Button>
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Summary */}
          <div className="flex items-center gap-4 rounded-lg border border-border bg-card p-4">
            <div className="text-center">
              <p className="text-2xl font-bold">{result.total_pages}</p>
              <p className="text-xs text-muted-foreground">Páginas</p>
            </div>
            <div className="h-8 w-px bg-border" />
            <div className="text-center">
              <p className="text-2xl font-bold">{result.tables_found}</p>
              <p className="text-xs text-muted-foreground">Tabelas encontradas</p>
            </div>
            <div className="ml-auto">
              <Button onClick={handleDownload} disabled={isDownloading} className="gap-2">
                {isDownloading ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    Gerando...
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4" />
                    Baixar Excel
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Tables */}
          {result.tables.map((table, idx) => (
            <Card key={idx}>
              <CardHeader>
                <CardTitle className="text-base">
                  Tabela {idx + 1} — Página {table.page}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr>
                        {table.headers.map((header, i) => (
                          <th
                            key={i}
                            className="border border-border bg-muted px-3 py-2 text-left font-medium"
                          >
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {table.rows.map((row, i) => (
                        <tr key={i} className="hover:bg-muted/50">
                          {row.map((cell, j) => (
                            <td key={j} className="border border-border px-3 py-2">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          ))}

          {result.tables_found === 0 && (
            <div className="rounded-lg border border-border bg-card p-8 text-center">
              <p className="text-muted-foreground">
                Nenhuma tabela encontrada neste PDF.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
