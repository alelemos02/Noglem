"use client";

import { useState, useCallback } from "react";
import { Table, Upload, FileText, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { splitPdfBySize } from "@/lib/pdf-split";

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

const SIZE_LIMIT = 4 * 1024 * 1024; // 4 MB — limite hard do Vercel por request

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Extrai as tabelas de um único arquivo (já dentro do limite de upload).
 * Faz retry com backoff em 429 (rate limit), já que o auto-split dispara várias
 * partes em sequência.
 */
async function extractTablesFromFile(file: File): Promise<ExtractResult> {
  for (let attempt = 0; ; attempt++) {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch("/api/pdf/extract", {
      method: "POST",
      body: formData,
    });

    if (response.status === 413) {
      throw new Error(
        "Uma das partes ainda ficou grande demais para o servidor. Tente um PDF com páginas mais leves."
      );
    }

    if (response.status === 429 && attempt < 4) {
      await sleep(1500 * (attempt + 1)); // 1.5s, 3s, 4.5s, 6s
      continue;
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.error || "Erro na extração");
    }

    return data as ExtractResult;
  }
}

export default function PdfExtractorPage() {
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);

  const willSplit = file ? file.size > SIZE_LIMIT : false;

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
    setProgress(null);
    try {
      // Arquivo dentro do limite: envia direto.
      if (file.size <= SIZE_LIMIT) {
        const data = await extractTablesFromFile(file);
        setResult({ ...data, filename: file.name });
        return;
      }

      // Arquivo grande: divide no navegador e processa parte por parte.
      const chunks = await splitPdfBySize(file, SIZE_LIMIT);
      const mergedTables: TableData[] = [];
      let totalPages = 0;

      for (let i = 0; i < chunks.length; i++) {
        if (i > 0) await sleep(300); // espaça os envios pra não saturar o rate limit
        setProgress({ current: i + 1, total: chunks.length });
        const chunkFile = new File([chunks[i].blob], `parte-${i + 1}.pdf`, {
          type: "application/pdf",
        });
        const data = await extractTablesFromFile(chunkFile);

        totalPages += data.total_pages;
        const offset = chunks[i].startPage - 1; // remapeia para a página original
        for (const t of data.tables) {
          mergedTables.push({ ...t, page: t.page + offset });
        }
      }

      setResult({
        filename: file.name,
        total_pages: totalPages,
        tables_found: mergedTables.length,
        tables: mergedTables,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro desconhecido";
      setError(message);
      console.error("Erro na extração:", err);
    } finally {
      setIsProcessing(false);
      setProgress(null);
    }
  };

  const handleDownload = async () => {
    if (!result) return;

    setIsDownloading(true);
    setError("");
    try {
      // Gera o Excel a partir das tabelas já extraídas (funciona inclusive quando
      // o PDF original foi grande demais para reenviar — fluxo de auto-split).
      const response = await fetch("/api/pdf/extract/excel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: result.filename,
          tables: result.tables,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "Erro ao gerar Excel");
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${result.filename.replace(/\.pdf$/i, "")}_tabelas.xlsx`;
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
                <FileText className={`h-12 w-12 ${willSplit ? "text-warning" : "text-success"}`} />
                <p className="font-medium">{file.name}</p>
                <p className={`text-sm ${willSplit ? "text-warning font-medium" : "text-muted-foreground"}`}>
                  {(file.size / 1024 / 1024).toFixed(2)} MB
                  {willSplit && " — será dividido automaticamente"}
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

      {/* Size notice */}
      {file && !result && willSplit && (
        <div className="rounded-lg border border-warning/50 bg-warning-muted p-3 text-center text-sm text-warning">
          Este PDF passa de 4 MB (limite do servidor). Ele será{" "}
          <strong>dividido automaticamente em partes</strong> no seu navegador antes
          do envio, e o resultado é consolidado num só.
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
                {progress
                  ? `Processando parte ${progress.current} de ${progress.total}...`
                  : willSplit
                    ? "Dividindo o PDF..."
                    : "Extraindo tabelas..."}
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
