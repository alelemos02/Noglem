"use client";

import { useState, useCallback } from "react";
import {
  Gauge,
  FileText,
  Download,
  Circle,
  Square,
  Minus,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Info,
  X,
  SearchX,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { Dropzone } from "@/components/ui/dropzone";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toast";

/* ─── Types ─── */

interface InstrumentData {
  tag: string;
  isa_type: string;
  description: string;
  symbol: string;
  classification: string;
  is_physical: boolean;
  furnished_by_package: boolean;
  area: string;
  tag_number: string;
  qualifier: string;
  equipment: string;
  loop_id: string;
  line_number: string;
  sheet: string;
  confidence: number;
}

interface LoopData {
  loop_id: string;
  instruments: string[];
  is_complete: boolean;
  missing: string[];
}

interface LineNumberData {
  full_tag: string;
  diameter: string;
  spec_class: string;
  line_id: string;
  service_code: string;
}

interface DrawingNoteData {
  number: number;
  text: string;
  affects_instruments: boolean;
}

interface DrawingMetadataData {
  document_number: string;
  revision: string;
  title: string;
  area: string;
  sheet_number: string;
  date: string;
}

interface ExtractResult {
  filename: string;
  total_instruments: number;
  total_equipment: number;
  total_loops: number;
  total_line_numbers: number;
  total_warnings: number;
  total_errors: number;
  instruments: InstrumentData[];
  loops: LoopData[];
  line_numbers: LineNumberData[];
  notes: DrawingNoteData[];
  metadata: DrawingMetadataData[];
  warnings: string[];
  errors: string[];
}

type ResultTab = "instruments" | "loops" | "validation" | "info";

const SIZE_LIMIT = 4 * 1024 * 1024; // 4 MB — Vercel hard limit per request

/* ─── Helpers ─── */

function mergeResults(results: ExtractResult[]): ExtractResult {
  return {
    filename: results.map((r) => r.filename).join(", "),
    total_instruments: results.reduce((s, r) => s + r.total_instruments, 0),
    total_equipment: results.reduce((s, r) => s + r.total_equipment, 0),
    total_loops: results.reduce((s, r) => s + r.total_loops, 0),
    total_line_numbers: results.reduce((s, r) => s + (r.total_line_numbers ?? 0), 0),
    total_warnings: results.reduce((s, r) => s + r.total_warnings, 0),
    total_errors: results.reduce((s, r) => s + r.total_errors, 0),
    instruments: results.flatMap((r) => r.instruments),
    loops: results.flatMap((r) => r.loops),
    line_numbers: results.flatMap((r) => r.line_numbers),
    notes: results.flatMap((r) => r.notes),
    metadata: results.flatMap((r) => r.metadata),
    warnings: results.flatMap((r) => r.warnings),
    errors: results.flatMap((r) => r.errors),
  };
}

function SymbolIcon({ symbol }: { symbol: string }) {
  switch (symbol) {
    case "square":
      return <Square className="h-3.5 w-3.5" />;
    case "hline":
      return <Minus className="h-3.5 w-3.5" />;
    default:
      return <Circle className="h-3.5 w-3.5" />;
  }
}

function ClassificationBadge({ classification, isPhysical }: { classification: string; isPhysical: boolean }) {
  if (isPhysical) {
    return <Badge variant="success" className="text-xs whitespace-nowrap">{classification}</Badge>;
  }
  return <Badge variant="error" className="text-xs whitespace-nowrap">{classification}</Badge>;
}

function getDownloadFilename(disposition: string | null, fallback: string) {
  const match = disposition?.match(/filename="?([^"]+)"?/i);
  return match?.[1] ?? fallback;
}

/* ─── Component ─── */

export default function PidExtractorPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingIndex, setProcessingIndex] = useState(-1);
  const [exportingIndex, setExportingIndex] = useState(-1);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<ResultTab>("instruments");

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  const oversizedFiles = new Set(files.filter((f) => f.size > SIZE_LIMIT).map((f) => f.name));
  const canExtract = files.length > 0 && oversizedFiles.size === 0;

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const pdfs = Array.from(incoming).filter((f) => f.type === "application/pdf");
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name));
      return [...prev, ...pdfs.filter((f) => !existing.has(f.name))];
    });
    setResult(null);
    setError("");
  }, []);

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setResult(null);
    setError("");
  };

  const buildFormData = (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("profile", "promon");
    formData.append("use_llm", "false");
    return formData;
  };

  const buildBatchUploadFormData = (batchId: string, file: File, index: number) => {
    const formData = new FormData();
    formData.append("batch_id", batchId);
    formData.append("index", String(index));
    formData.append("file", file);
    return formData;
  };

  const buildBatchFinalizeFormData = (batchId: string) => {
    const formData = new FormData();
    formData.append("batch_id", batchId);
    formData.append("profile", "promon");
    formData.append("use_llm", "false");
    return formData;
  };

  const readApiError = async (response: Response, fallback: string) => {
    const data = await response.json().catch(() => null) as { error?: string } | null;
    return data?.error || fallback;
  };

  const startBatch = async () => {
    const response = await fetch("/api/pid/extract/batch/start", { method: "POST" });
    const data = await response.json().catch(() => null) as { batch_id?: string; error?: string } | null;

    if (!response.ok || !data?.batch_id) {
      throw new Error(data?.error || "Erro ao iniciar exportação consolidada");
    }

    return data.batch_id;
  };

  const uploadBatchFiles = async (batchId: string) => {
    for (let i = 0; i < files.length; i++) {
      setExportingIndex(i);
      const response = await fetch("/api/pid/extract/batch/upload", {
        method: "POST",
        body: buildBatchUploadFormData(batchId, files[i], i),
      });

      if (!response.ok) {
        throw new Error(await readApiError(response, `Erro ao enviar "${files[i].name}"`));
      }
    }
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const downloadBatchArtifact = async (
    route: "/api/pid/extract/batch/download" | "/api/pid/extract/batch/preview",
    fallbackFilename: string
  ) => {
    const batchId = await startBatch();
    await uploadBatchFiles(batchId);

    const response = await fetch(route, {
      method: "POST",
      body: buildBatchFinalizeFormData(batchId),
    });

    if (!response.ok) {
      throw new Error(await readApiError(response, "Erro ao gerar arquivo consolidado"));
    }

    const blob = await response.blob();
    const filename = getDownloadFilename(response.headers.get("content-disposition"), fallbackFilename);
    downloadBlob(blob, filename);
  };

  const extractOne = async (file: File, attempt = 0): Promise<ExtractResult> => {
    const response = await fetch("/api/pid/extract", {
      method: "POST",
      body: buildFormData(file),
    });
    const text = await response.text();
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(text);
    } catch {
      if (response.status === 413) {
        throw new Error(`"${file.name}" é muito grande para o servidor. Reduza para menos de 4 MB.`);
      }
      throw new Error(`Resposta inesperada (${response.status}) ao processar "${file.name}": ${text.slice(0, 120)}`);
    }
    if (response.status === 429 && attempt < 3) {
      await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)));
      return extractOne(file, attempt + 1);
    }
    if (!response.ok) throw new Error((data.error as string) || `Erro ao processar "${file.name}"`);
    return data as unknown as ExtractResult;
  };

  const handleExtract = async () => {
    if (!canExtract) return;
    setIsProcessing(true);
    setError("");
    const allResults: ExtractResult[] = [];
    try {
      for (let i = 0; i < files.length; i++) {
        setProcessingIndex(i);
        if (i > 0) await new Promise((r) => setTimeout(r, 400));
        allResults.push(await extractOne(files[i]));
      }
      const merged = mergeResults(allResults);
      setResult(merged);
      setActiveTab("instruments");
      toast.success("Extração concluída", {
        description: `${merged.total_instruments} instrumento(s) em ${files.length} arquivo(s).`,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setIsProcessing(false);
      setProcessingIndex(-1);
    }
  };

  const handleDownload = async () => {
    if (!files.length) return;
    setIsDownloading(true);
    try {
      if (files.length > 1) {
        await downloadBatchArtifact("/api/pid/extract/batch/download", "instrument_index_consolidado.xlsx");
      } else {
        const file = files[0];
        const response = await fetch("/api/pid/extract/download", {
          method: "POST",
          body: buildFormData(file),
        });
        if (!response.ok) throw new Error(`Erro ao gerar Excel para "${file.name}"`);
        const blob = await response.blob();
        downloadBlob(blob, `${file.name.replace(".pdf", "")}_instrument_index.xlsx`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setIsDownloading(false);
      setExportingIndex(-1);
    }
  };

  const handleDownloadPdf = async () => {
    if (!files.length) return;
    setIsDownloadingPdf(true);
    try {
      if (files.length > 1) {
        await downloadBatchArtifact("/api/pid/extract/batch/preview", "pids_anotados_consolidado.pdf");
      } else {
        const file = files[0];
        const response = await fetch("/api/pid/extract/preview", {
          method: "POST",
          body: buildFormData(file),
        });
        if (!response.ok) throw new Error(`Erro ao gerar PDF anotado para "${file.name}"`);
        const blob = await response.blob();
        downloadBlob(blob, `${file.name.replace(".pdf", "")}_anotado.pdf`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setIsDownloadingPdf(false);
      setExportingIndex(-1);
    }
  };

  const tabs: { key: ResultTab; label: string; count?: number }[] = [
    { key: "instruments", label: "Instrumentos", count: result?.total_instruments },
    { key: "loops", label: "Loops", count: result?.total_loops },
    { key: "validation", label: "Validação", count: (result?.total_warnings ?? 0) + (result?.total_errors ?? 0) },
    { key: "info", label: "Info Desenho", count: result?.metadata?.length },
  ];

  return (
    <div className="space-y-6">
      <PageHeader tool="pid-extractor" />

      {/* Upload Area */}
      <Card className="gap-3 py-4">
        <CardHeader>
          <CardTitle className="text-sm">Upload de P&ID</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Dropzone
            onFiles={addFiles}
            accept=".pdf"
            multiple
            compact={files.length > 0}
            label="Arraste PDFs de P&ID ou clique para selecionar"
            hint="Múltiplos arquivos · Apenas P&IDs vetoriais"
            disabled={isProcessing || isDownloading || isDownloadingPdf}
          />

          {files.length > 0 && (
            <div className="space-y-1">
              {files.map((f, i) => {
                const isOversized = oversizedFiles.has(f.name);
                const isActive = processingIndex === i || exportingIndex === i;
                return (
                  <div
                    key={f.name}
                    className={`flex items-center gap-2.5 rounded-md border px-3 py-2 text-sm ${
                      isOversized
                        ? "border-danger/40 bg-danger-subtle"
                        : isActive
                          ? "border-accent/40 bg-accent-subtle"
                          : "border-edge bg-surface-1"
                    }`}
                  >
                    <FileText className={`h-4 w-4 shrink-0 ${isOversized ? "text-danger" : "text-fg-subtle"}`} />
                    <span className="flex-1 truncate text-[13px] font-medium">{f.name}</span>
                    {isActive && <Spinner size="xs" className="text-accent" />}
                    <span className={`shrink-0 font-mono text-xs tabular-nums ${isOversized ? "font-semibold text-danger" : "text-fg-subtle"}`}>
                      {(f.size / 1024 / 1024).toFixed(2)} MB
                      {isOversized && " — acima do limite"}
                    </span>
                    {!isProcessing && !isDownloading && !isDownloadingPdf && (
                      <button
                        onClick={() => removeFile(i)}
                        className="ml-1 shrink-0 rounded-sm p-0.5 text-fg-subtle transition-colors hover:text-fg"
                        title="Remover arquivo"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                );
              })}

              {/* Totals row */}
              <div className={`flex items-center justify-between rounded-md px-3 py-1.5 font-mono text-[11px] tabular-nums ${
                oversizedFiles.size > 0 ? "bg-danger-subtle text-danger" : "bg-surface-1 text-fg-subtle"
              }`}>
                <span>{files.length} arquivo{files.length > 1 ? "s" : ""}</span>
                <span>Total: {(totalSize / 1024 / 1024).toFixed(2)} MB</span>
              </div>
            </div>
          )}

          {/* Size limit notice */}
          <Alert variant={oversizedFiles.size > 0 ? "danger" : "warning"}>
            <strong className="text-fg">Limite de 4 MB por arquivo.</strong>{" "}
            {oversizedFiles.size > 0
              ? "Um ou mais arquivos excedem o limite — remova-os ou substitua por versões menores antes de extrair."
              : "Cada arquivo é enviado individualmente. P&IDs com muitas páginas podem exceder esse limite — divida antes de fazer o upload."}
          </Alert>
        </CardContent>
      </Card>

      {/* Error */}
      {error && <Alert variant="danger">{error}</Alert>}

      {/* Extract Button */}
      {files.length > 0 && !result && (
        <div className="flex justify-center">
          <Button size="lg" onClick={handleExtract} disabled={!canExtract} loading={isProcessing} className="gap-2">
            {isProcessing ? (
              files.length > 1
                ? `Processando ${processingIndex + 1} de ${files.length}...`
                : "Extraindo instrumentos..."
            ) : (
              <>
                <Gauge className="h-4 w-4" />
                {files.length > 1 ? `Extrair ${files.length} arquivos` : "Extrair instrumentos"}
              </>
            )}
          </Button>
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Summary Bar */}
          <div className="flex flex-wrap items-center gap-7 rounded-lg border border-edge bg-surface-1 px-5 py-4">
            {[
              { value: result.total_instruments, label: "Instrumentos" },
              { value: result.total_equipment, label: "Equipamentos" },
              { value: result.total_loops, label: "Loops" },
              { value: result.total_line_numbers ?? 0, label: "Linhas" },
              { value: result.total_warnings, label: "Avisos", className: "text-warning" },
              ...(result.total_errors > 0
                ? [{ value: result.total_errors, label: "Erros", className: "text-danger" }]
                : []),
            ].map((item) => (
              <div key={item.label}>
                <p className="microlabel mb-0.5 text-[10px]">{item.label}</p>
                <p className={`font-mono text-xl font-medium tabular-nums ${item.className ?? "text-fg"}`}>{item.value}</p>
              </div>
            ))}

            <div className="ml-auto flex flex-wrap gap-2">
              <Button onClick={handleDownload} disabled={isDownloadingPdf} loading={isDownloading} className="gap-2">
                {isDownloading ? (
                  files.length > 1 ? `Enviando ${exportingIndex + 1 || 1} de ${files.length}...` : "Gerando..."
                ) : (
                  <>
                    <Download className="h-4 w-4" />
                    {files.length > 1 ? "Baixar Excel consolidado" : "Baixar Excel"}
                  </>
                )}
              </Button>
              <Button onClick={handleDownloadPdf} disabled={isDownloading} loading={isDownloadingPdf} variant="outline" className="gap-2">
                {isDownloadingPdf ? (
                  files.length > 1 ? `Enviando ${exportingIndex + 1 || 1} de ${files.length}...` : "Gerando..."
                ) : (
                  <>
                    <FileText className="h-4 w-4" />
                    {files.length > 1 ? "Baixar PDF anotado consolidado" : "Baixar PDF anotado"}
                  </>
                )}
              </Button>
              <Button
                variant="ghost"
                onClick={() => { setResult(null); setFiles([]); setError(""); }}
              >
                Nova extração
              </Button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-edge">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab.key
                    ? "border-accent text-fg"
                    : "border-transparent text-fg-muted hover:text-fg"
                }`}
              >
                {tab.label}
                {tab.count !== undefined && tab.count > 0 && (
                  <span className={`font-mono text-xs tabular-nums ${
                    activeTab === tab.key ? "text-accent" : "text-fg-subtle"
                  }`}>
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Tab: Instruments */}
          {activeTab === "instruments" && (
            <>
              {result.instruments.length > 0 ? (
                <Card>
                  <CardContent className="pt-4">
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse text-sm">
                        <thead>
                          <tr>
                            {["Tag", "Tipo ISA", "Descrição", "Símbolo", "Classificação", "Equipamento", "Loop", "Folha", "Conf."].map(
                              (header) => (
                                <th key={header} className="border border-edge bg-surface-1 px-3 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-fg-subtle">
                                  {header}
                                </th>
                              )
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {result.instruments.map((inst, i) => (
                            <tr key={i} className="hover:bg-surface-2/50">
                              <td className="border border-edge px-3 py-2 font-mono font-medium">
                                {inst.tag}
                                {inst.furnished_by_package && (
                                  <Badge variant="info" className="ml-1 text-xs">F</Badge>
                                )}
                              </td>
                              <td className="border border-edge px-3 py-2">{inst.isa_type}</td>
                              <td className="border border-edge px-3 py-2">{inst.description}</td>
                              <td className="border border-edge px-3 py-2">
                                <div className="flex items-center gap-1.5">
                                  <SymbolIcon symbol={inst.symbol} />
                                  <span className="text-xs text-fg-muted capitalize">{inst.symbol}</span>
                                </div>
                              </td>
                              <td className="border border-edge px-3 py-2">
                                <ClassificationBadge classification={inst.classification} isPhysical={inst.is_physical} />
                              </td>
                              <td className="border border-edge px-3 py-2">{inst.equipment}</td>
                              <td className="border border-edge px-3 py-2">{inst.loop_id}</td>
                              <td className="border border-edge px-3 py-2">{inst.sheet}</td>
                              <td className="border border-edge px-3 py-2">
                                <span className={
                                  inst.confidence < 0.5
                                    ? "text-danger font-medium"
                                    : inst.confidence < 0.8
                                      ? "text-warning font-medium"
                                      : ""
                                }>
                                  {Math.round(inst.confidence * 100)}%
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <EmptyState
                  icon={SearchX}
                  title="Nenhum instrumento encontrado"
                  description="Verifique se o P&ID é vetorial e se o perfil de tags está correto — arquivos raster não são suportados."
                />
              )}
            </>
          )}

          {/* Tab: Loops */}
          {activeTab === "loops" && (
            <Card>
              <CardContent className="pt-4">
                {result.loops.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr>
                          {["Loop ID", "Instrumentos", "Completo?", "Faltantes"].map((header) => (
                            <th key={header} className="border border-edge bg-surface-1 px-3 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-fg-subtle">
                              {header}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.loops.map((loop, i) => (
                          <tr key={i} className="hover:bg-surface-2/50">
                            <td className="border border-edge px-3 py-2 font-mono font-medium">{loop.loop_id}</td>
                            <td className="border border-edge px-3 py-2">
                              <div className="flex flex-wrap gap-1">
                                {loop.instruments.map((tag, j) => (
                                  <Badge key={j} variant="secondary" className="text-xs">{tag}</Badge>
                                ))}
                              </div>
                            </td>
                            <td className="border border-edge px-3 py-2">
                              {loop.is_complete ? (
                                <Badge variant="success" className="gap-1">
                                  <CheckCircle2 className="h-3 w-3" /> Sim
                                </Badge>
                              ) : (
                                <Badge variant="warning" className="gap-1">
                                  <AlertTriangle className="h-3 w-3" /> Não
                                </Badge>
                              )}
                            </td>
                            <td className="border border-edge px-3 py-2 text-fg-muted">
                              {loop.missing.join(", ")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="py-8 text-center text-fg-muted">Nenhum loop detectado.</p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Tab: Validation */}
          {activeTab === "validation" && (
            <div className="space-y-4">
              {result.errors.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base text-danger">
                      <XCircle className="h-4 w-4" />
                      Erros ({result.errors.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1.5 text-sm">
                      {result.errors.map((e, i) => (
                        <li key={i} className="rounded border border-danger/30 bg-danger-subtle px-3 py-2">{e}</li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {result.warnings.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base text-warning">
                      <AlertTriangle className="h-4 w-4" />
                      Avisos ({result.warnings.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1.5 text-sm">
                      {result.warnings.map((w, i) => (
                        <li key={i} className="rounded border border-warning/30 bg-warning-subtle px-3 py-2">{w}</li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {result.errors.length === 0 && result.warnings.length === 0 && (
                <EmptyState
                  icon={CheckCircle2}
                  title="Nenhum problema de validação"
                  description="Todos os instrumentos e loops passaram nas verificações."
                />
              )}
            </div>
          )}

          {/* Tab: Drawing Info */}
          {activeTab === "info" && (
            <Card>
              <CardContent className="pt-4">
                {result.metadata && result.metadata.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      <thead>
                        <tr>
                          {["Doc. Number", "Revisão", "Título", "Área", "Folha", "Data"].map((header) => (
                            <th key={header} className="border border-edge bg-surface-1 px-3 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-fg-subtle">
                              {header}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.metadata.map((meta, i) => (
                          <tr key={i} className="hover:bg-surface-2/50">
                            <td className="border border-edge px-3 py-2 font-mono">{meta.document_number}</td>
                            <td className="border border-edge px-3 py-2">{meta.revision}</td>
                            <td className="border border-edge px-3 py-2">{meta.title}</td>
                            <td className="border border-edge px-3 py-2">{meta.area}</td>
                            <td className="border border-edge px-3 py-2">{meta.sheet_number}</td>
                            <td className="border border-edge px-3 py-2">{meta.date}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="py-8 text-center text-fg-muted">
                    Nenhuma informação de título/carimbo extraída.
                  </p>
                )}

                {result.notes && result.notes.length > 0 && (
                  <div className="mt-6">
                    <h3 className="mb-3 flex items-center gap-2 text-sm font-medium">
                      <Info className="h-4 w-4" />
                      Notas do Desenho ({result.notes.length})
                    </h3>
                    <ul className="space-y-1.5 text-sm">
                      {result.notes.map((note, i) => (
                        <li key={i} className="rounded border border-edge bg-surface-2/50 px-3 py-2">
                          <span className="font-medium">Nota {note.number}:</span> {note.text}
                          {note.affects_instruments && (
                            <Badge variant="warning" className="ml-2 text-xs">Afeta instrumentos</Badge>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
