"use client";

import { useState } from "react";
import { Table, FileText, Download, SearchX, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Dropzone } from "@/components/ui/dropzone";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { Progress } from "@/components/ui/progress";
import { toast } from "@/components/ui/toast";
import { splitPdfBySize, getPdfPageCount } from "@/lib/pdf-split";

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
// Limita páginas por parte. Páginas escaneadas viram OCR (1 chamada de IA por
// página, ~40s cada); manter poucas páginas por request evita estourar o timeout
// (~60s) do Vercel quando elas são processadas em paralelo no backend.
const MAX_PAGES_PER_CHUNK = 4;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// 429 = rate limit; 5xx = timeout/instabilidade do backend (uma página de OCR que
// passou dos ~60s do Vercel devolve 504). Ambos são transitórios — vale reenviar a
// parte antes de desistir dela.
const RETRYABLE_STATUS = new Set([429, 500, 502, 503, 504]);
const MAX_ATTEMPTS = 4;

/**
 * Extrai as tabelas de um único arquivo (já dentro do limite de upload).
 * Faz retry com backoff em rate limit (429), timeout/erro do servidor (5xx) e
 * falha de rede — o auto-split dispara várias partes em sequência e uma página de
 * OCR lenta pode estourar o teto de ~60s do Vercel.
 */
async function extractTablesFromFile(file: File): Promise<ExtractResult> {
  for (let attempt = 0; ; attempt++) {
    const formData = new FormData();
    formData.append("file", file);

    let response: Response;
    try {
      response = await fetch("/api/pdf/extract", {
        method: "POST",
        body: formData,
      });
    } catch (networkErr) {
      // Conexão derrubada (ex.: função reciclada no meio do OCR). Tenta de novo.
      if (attempt < MAX_ATTEMPTS) {
        await sleep(1500 * (attempt + 1));
        continue;
      }
      throw networkErr;
    }

    if (response.status === 413) {
      throw new Error(
        "Uma das partes ainda ficou grande demais para o servidor. Tente um PDF com páginas mais leves."
      );
    }

    if (RETRYABLE_STATUS.has(response.status) && attempt < MAX_ATTEMPTS) {
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
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);

  const willSplit = file ? file.size > SIZE_LIMIT : false;

  const handleFiles = (files: File[]) => {
    const selectedFile = files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResult(null);
      setError("");
      setWarning("");
    }
  };

  const handleExtract = async () => {
    if (!file) return;

    setIsProcessing(true);
    setError("");
    setWarning("");
    setProgress(null);
    try {
      // Arquivo pequeno E com poucas páginas: envia direto (caminho rápido).
      // Mesmo abaixo do limite de tamanho, um PDF escaneado com muitas páginas
      // precisa ser dividido para o OCR caber no timeout do backend.
      if (file.size <= SIZE_LIMIT) {
        const pageCount = await getPdfPageCount(file);
        if (pageCount <= MAX_PAGES_PER_CHUNK) {
          const data = await extractTablesFromFile(file);
          setResult({ ...data, filename: file.name });
          toast.success("Extração concluída", {
            description: `${data.tables_found} tabela(s) em ${data.total_pages} página(s).`,
          });
          return;
        }
      }

      // Arquivo grande ou com muitas páginas: divide no navegador e processa parte por parte.
      const chunks = await splitPdfBySize(file, SIZE_LIMIT, MAX_PAGES_PER_CHUNK);
      const mergedTables: TableData[] = [];
      const failedRanges: string[] = [];
      let totalPages = 0;

      for (let i = 0; i < chunks.length; i++) {
        if (i > 0) await sleep(300); // espaça os envios pra não saturar o rate limit
        setProgress({ current: i + 1, total: chunks.length });
        const chunkFile = new File([chunks[i].blob], `parte-${i + 1}.pdf`, {
          type: "application/pdf",
        });
        const offset = chunks[i].startPage - 1; // remapeia para a página original

        try {
          const data = await extractTablesFromFile(chunkFile);
          totalPages += data.total_pages;
          for (const t of data.tables) {
            mergedTables.push({ ...t, page: t.page + offset });
          }
        } catch {
          // Uma parte falhou mesmo após os retries: NÃO aborta o documento inteiro.
          // Registra o intervalo de páginas e segue — o usuário fica com o resto.
          totalPages += chunks[i].pageCount;
          const last = chunks[i].startPage + chunks[i].pageCount - 1;
          failedRanges.push(
            chunks[i].pageCount > 1 ? `${chunks[i].startPage}–${last}` : `${chunks[i].startPage}`
          );
        }
      }

      // Só é erro de verdade se TODAS as partes falharam.
      if (failedRanges.length === chunks.length) {
        throw new Error(
          "Não foi possível extrair nenhuma parte do documento. O servidor pode estar sobrecarregado — tente de novo em instantes."
        );
      }

      if (failedRanges.length > 0) {
        setWarning(
          `Algumas páginas falharam após várias tentativas (provável timeout do servidor): ${failedRanges.join(", ")}. ` +
            "O restante foi extraído normalmente — você pode reenviar só essas páginas depois."
        );
      }

      setResult({
        filename: file.name,
        total_pages: totalPages,
        tables_found: mergedTables.length,
        tables: mergedTables,
      });
      toast.success("Extração concluída", {
        description: `${mergedTables.length} tabela(s) em ${totalPages} página(s).`,
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
      <PageHeader tool="pdf-extractor" />

      {/* Upload Area */}
      <Card className="gap-0 py-0">
        <CardContent className="p-4">
          <Dropzone
            onFiles={handleFiles}
            accept=".pdf"
            label="Arraste um PDF ou clique para selecionar"
            hint="Arquivos acima de 4 MB são divididos automaticamente no navegador"
            disabled={isProcessing}
          />
          {file && (
            <div className="mt-3 flex items-center gap-3 rounded-md border border-edge bg-surface-2 px-3.5 py-2.5">
              <FileText className={`h-4 w-4 shrink-0 ${willSplit ? "text-warning" : "text-fg-subtle"}`} />
              <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-fg">{file.name}</span>
              <span className={`shrink-0 font-mono text-xs tabular-nums ${willSplit ? "text-warning" : "text-fg-subtle"}`}>
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </span>
              <button
                onClick={() => {
                  setFile(null);
                  setResult(null);
                  setError("");
                  setWarning("");
                }}
                disabled={isProcessing}
                className="shrink-0 rounded-sm p-1 text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg"
                title="Remover arquivo"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Error Message */}
      {error && <Alert variant="danger">{error}</Alert>}

      {/* Warning (sucesso parcial — algumas partes falharam mas o resto saiu) */}
      {warning && <Alert variant="warning" title="Extração parcial">{warning}</Alert>}

      {/* Size notice */}
      {file && !result && willSplit && (
        <Alert variant="info">
          Este PDF passa de 4 MB (limite do servidor). Ele será{" "}
          <strong className="text-fg">dividido automaticamente em partes</strong> no seu
          navegador antes do envio, e o resultado é consolidado num só.
        </Alert>
      )}

      {/* Extract Button */}
      {file && !result && (
        <div className="flex justify-center">
          <Button
            size="lg"
            onClick={handleExtract}
            loading={isProcessing}
            className="gap-2"
          >
            {isProcessing ? (
              progress
                ? `Processando parte ${progress.current} de ${progress.total}...`
                : willSplit
                  ? "Dividindo o PDF..."
                  : "Extraindo tabelas..."
            ) : (
              <>
                <Table className="h-4 w-4" />
                Extrair tabelas
              </>
            )}
          </Button>
        </div>
      )}

      {/* Progress for multi-part / OCR runs */}
      {isProcessing && progress && (
        <div className="mx-auto max-w-md space-y-2">
          <Progress
            value={progress.current}
            max={progress.total}
            label={`Parte ${progress.current} de ${progress.total}`}
          />
          <p className="text-center text-xs text-fg-subtle">
            Páginas escaneadas são lidas por OCR (IA) — documentos grandes podem
            levar alguns minutos. Não feche a aba.
          </p>
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Summary */}
          <div className="flex items-center gap-7 rounded-lg border border-edge bg-surface-1 px-5 py-4">
            <div>
              <p className="microlabel mb-0.5 text-[10px]">Páginas</p>
              <p className="font-mono text-xl font-medium tabular-nums text-fg">{result.total_pages}</p>
            </div>
            <div>
              <p className="microlabel mb-0.5 text-[10px]">Tabelas</p>
              <p className="font-mono text-xl font-medium tabular-nums text-fg">{result.tables_found}</p>
            </div>
            <div className="ml-auto">
              <Button onClick={handleDownload} loading={isDownloading} className="gap-2">
                {isDownloading ? (
                  "Gerando..."
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
            <Card key={idx} className="gap-3 py-4">
              <CardHeader>
                <CardTitle className="text-sm">
                  Tabela {idx + 1}{" "}
                  <span className="font-mono text-xs font-normal text-fg-subtle">
                    — página {table.page}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto rounded-md border border-edge">
                  <table className="w-full border-collapse text-[13px]">
                    <thead>
                      <tr className="border-b border-edge-strong bg-surface-1">
                        {table.headers.map((header, i) => (
                          <th
                            key={i}
                            className="px-3 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-fg-subtle"
                          >
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {table.rows.map((row, i) => (
                        <tr key={i} className="border-b border-edge last:border-0 hover:bg-surface-2/50">
                          {row.map((cell, j) => (
                            <td key={j} className="px-3 py-2 text-fg-muted">
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
            <EmptyState
              icon={SearchX}
              title="Nenhuma tabela encontrada"
              description="O PDF foi processado, mas nenhuma estrutura de tabela foi identificada nas páginas."
            />
          )}
        </>
      )}
    </div>
  );
}
