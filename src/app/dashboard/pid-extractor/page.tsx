"use client";

import { useState, useCallback } from "react";
import {
  Gauge,
  Upload,
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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

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

/* ─── Component ─── */

export default function PidExtractorPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingIndex, setProcessingIndex] = useState(-1);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [isDragging, setIsDragging] = useState(false);
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

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(e.target.files);
    e.target.value = "";
  };

  const buildFormData = (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("profile", "promon");
    formData.append("use_llm", "false");
    return formData;
  };

  const handleExtract = async () => {
    if (!canExtract) return;
    setIsProcessing(true);
    setError("");
    const allResults: ExtractResult[] = [];
    try {
      for (let i = 0; i < files.length; i++) {
        setProcessingIndex(i);
        const file = files[i];
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
        if (!response.ok) throw new Error((data.error as string) || `Erro ao processar "${file.name}"`);
        allResults.push(data as unknown as ExtractResult);
      }
      setResult(mergeResults(allResults));
      setActiveTab("instruments");
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
      for (const file of files) {
        const response = await fetch("/api/pid/extract/download", {
          method: "POST",
          body: buildFormData(file),
        });
        if (!response.ok) throw new Error(`Erro ao gerar Excel para "${file.name}"`);
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${file.name.replace(".pdf", "")}_instrument_index.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setIsDownloading(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!files.length) return;
    setIsDownloadingPdf(true);
    try {
      for (const file of files) {
        const response = await fetch("/api/pid/extract/preview", {
          method: "POST",
          body: buildFormData(file),
        });
        if (!response.ok) throw new Error(`Erro ao gerar PDF anotado para "${file.name}"`);
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${file.name.replace(".pdf", "")}_anotado.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setIsDownloadingPdf(false);
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
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-warning-muted">
          <Gauge className="h-6 w-6 text-warning" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Extrator de P&ID</h1>
          <p className="text-muted-foreground">
            Extraia instrumentos de P&IDs vetoriais e gere o Instrument Index
          </p>
        </div>
        <Badge variant="secondary" className="ml-auto">Beta</Badge>
      </div>

      {/* Upload Area */}
      <Card>
        <CardHeader>
          <CardTitle>Upload de P&ID</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            className={`rounded-lg border-2 border-dashed transition-colors ${
              isDragging
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50"
            }`}
          >
            {files.length > 0 ? (
              <div className="space-y-1 p-3">
                {files.map((f, i) => {
                  const isOversized = oversizedFiles.has(f.name);
                  const isActive = processingIndex === i;
                  return (
                    <div
                      key={f.name}
                      className={`flex items-center gap-2 rounded border px-3 py-2 text-sm ${
                        isOversized
                          ? "border-error/40 bg-error-muted"
                          : isActive
                            ? "border-primary/40 bg-primary/5"
                            : "border-border bg-surface"
                      }`}
                    >
                      <FileText className={`h-4 w-4 shrink-0 ${isOversized ? "text-error" : "text-warning"}`} />
                      <span className="flex-1 truncate font-medium">{f.name}</span>
                      {isActive && (
                        <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                      )}
                      <span className={`font-mono tabular-nums text-xs shrink-0 ${isOversized ? "text-error font-semibold" : "text-text-secondary"}`}>
                        {(f.size / 1024 / 1024).toFixed(2)} MB
                        {isOversized && " — acima do limite"}
                      </span>
                      {!isProcessing && (
                        <button
                          onClick={() => removeFile(i)}
                          className="ml-1 shrink-0 rounded p-0.5 text-text-tertiary hover:text-text-primary"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  );
                })}

                {/* Totals row */}
                <div className={`flex items-center justify-between rounded px-3 py-1.5 text-xs font-medium ${
                  totalSize > SIZE_LIMIT ? "bg-error-muted text-error" : "bg-surface text-text-secondary"
                }`}>
                  <span>{files.length} arquivo{files.length > 1 ? "s" : ""}</span>
                  <span className="font-mono tabular-nums">
                    Total: {(totalSize / 1024 / 1024).toFixed(2)} MB / 4,00 MB
                    {totalSize > SIZE_LIMIT && " ⚠"}
                  </span>
                </div>

                {/* Add more */}
                {!isProcessing && (
                  <label className="flex cursor-pointer items-center gap-1.5 px-1 pt-1 text-xs text-text-secondary hover:text-text-primary">
                    <Upload className="h-3.5 w-3.5" />
                    Adicionar mais arquivos
                    <input type="file" accept=".pdf" multiple onChange={handleFileSelect} className="hidden" />
                  </label>
                )}
              </div>
            ) : (
              <label className="flex min-h-[180px] cursor-pointer flex-col items-center justify-center gap-2 p-6">
                <Upload className="h-12 w-12 text-muted-foreground" />
                <p className="font-medium">Arraste PDFs de P&ID ou clique para selecionar</p>
                <p className="text-sm text-muted-foreground">Múltiplos arquivos suportados · Apenas P&IDs vetoriais</p>
                <input type="file" accept=".pdf" multiple onChange={handleFileSelect} className="hidden" />
              </label>
            )}
          </div>

          {/* Size limit notice */}
          <div className={`flex items-start gap-2 rounded-lg px-3 py-2.5 text-sm ${
            totalSize > SIZE_LIMIT && files.length > 0
              ? "bg-error-muted text-error"
              : "bg-warning-muted text-warning"
          }`}>
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              <strong>Limite de 4 MB por arquivo.</strong>{" "}
              {totalSize > SIZE_LIMIT && files.length > 0
                ? "Um ou mais arquivos excedem o limite — remova-os ou substitua por versões menores antes de extrair."
                : "Cada arquivo é enviado individualmente. P&IDs com muitas páginas podem exceder esse limite — divida antes de fazer o upload."}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-error/50 bg-error-muted p-4 text-center text-sm text-error">
          {error}
        </div>
      )}

      {/* Extract Button */}
      {files.length > 0 && !result && (
        <div className="flex justify-center">
          <Button size="lg" onClick={handleExtract} disabled={isProcessing || !canExtract} className="gap-2">
            {isProcessing ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                {files.length > 1
                  ? `Processando ${processingIndex + 1} de ${files.length}...`
                  : "Extraindo instrumentos..."}
              </>
            ) : (
              <>
                <Gauge className="h-4 w-4" />
                {files.length > 1 ? `Extrair ${files.length} arquivos` : "Extrair Instrumentos"}
              </>
            )}
          </Button>
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Summary Bar */}
          <div className="flex flex-wrap items-center gap-4 rounded-lg border border-border bg-card p-4">
            {[
              { value: result.total_instruments, label: "Instrumentos" },
              { value: result.total_equipment, label: "Equipamentos" },
              { value: result.total_loops, label: "Loops" },
              { value: result.total_line_numbers ?? 0, label: "Linhas" },
              { value: result.total_warnings, label: "Avisos", className: "text-warning" },
              ...(result.total_errors > 0
                ? [{ value: result.total_errors, label: "Erros", className: "text-destructive" }]
                : []),
            ].map((item, i) => (
              <div key={item.label} className="flex items-center gap-4">
                {i > 0 && <div className="h-8 w-px bg-border" />}
                <div className="text-center">
                  <p className={`text-2xl font-bold font-mono tabular-nums ${item.className ?? ""}`}>{item.value}</p>
                  <p className="text-xs text-muted-foreground">{item.label}</p>
                </div>
              </div>
            ))}

            <div className="ml-auto flex gap-2">
              <Button onClick={handleDownload} disabled={isDownloading} className="gap-2">
                {isDownloading ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    Gerando...
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4" />
                    {files.length > 1 ? `Baixar ${files.length} Excels` : "Baixar Excel"}
                  </>
                )}
              </Button>
              <Button onClick={handleDownloadPdf} disabled={isDownloadingPdf} variant="outline" className="gap-2">
                {isDownloadingPdf ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    Gerando...
                  </>
                ) : (
                  <>
                    <FileText className="h-4 w-4" />
                    {files.length > 1 ? `Baixar ${files.length} PDFs Anotados` : "Baixar PDF Anotado"}
                  </>
                )}
              </Button>
              <Button
                variant="outline"
                onClick={() => { setResult(null); setFiles([]); setError(""); }}
              >
                Nova extração
              </Button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-border">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium transition-colors ${
                  activeTab === tab.key
                    ? "border-b-2 border-primary text-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab.label}
                {tab.count !== undefined && tab.count > 0 && (
                  <span className={`rounded-full px-1.5 py-0.5 text-xs ${
                    activeTab === tab.key ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
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
                                <th key={header} className="border border-border bg-muted px-3 py-2 text-left font-medium">
                                  {header}
                                </th>
                              )
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {result.instruments.map((inst, i) => (
                            <tr key={i} className="hover:bg-muted/50">
                              <td className="border border-border px-3 py-2 font-mono font-medium">
                                {inst.tag}
                                {inst.furnished_by_package && (
                                  <Badge variant="info" className="ml-1 text-xs">F</Badge>
                                )}
                              </td>
                              <td className="border border-border px-3 py-2">{inst.isa_type}</td>
                              <td className="border border-border px-3 py-2">{inst.description}</td>
                              <td className="border border-border px-3 py-2">
                                <div className="flex items-center gap-1.5">
                                  <SymbolIcon symbol={inst.symbol} />
                                  <span className="text-xs text-muted-foreground capitalize">{inst.symbol}</span>
                                </div>
                              </td>
                              <td className="border border-border px-3 py-2">
                                <ClassificationBadge classification={inst.classification} isPhysical={inst.is_physical} />
                              </td>
                              <td className="border border-border px-3 py-2">{inst.equipment}</td>
                              <td className="border border-border px-3 py-2">{inst.loop_id}</td>
                              <td className="border border-border px-3 py-2">{inst.sheet}</td>
                              <td className="border border-border px-3 py-2">
                                <span className={
                                  inst.confidence < 0.5
                                    ? "text-destructive font-medium"
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
                <div className="rounded-lg border border-border bg-card p-8 text-center">
                  <p className="text-muted-foreground">
                    Nenhum instrumento encontrado neste PDF. Verifique se o P&ID é vetorial e se o perfil de tags está correto.
                  </p>
                </div>
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
                            <th key={header} className="border border-border bg-muted px-3 py-2 text-left font-medium">
                              {header}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.loops.map((loop, i) => (
                          <tr key={i} className="hover:bg-muted/50">
                            <td className="border border-border px-3 py-2 font-mono font-medium">{loop.loop_id}</td>
                            <td className="border border-border px-3 py-2">
                              <div className="flex flex-wrap gap-1">
                                {loop.instruments.map((tag, j) => (
                                  <Badge key={j} variant="secondary" className="text-xs">{tag}</Badge>
                                ))}
                              </div>
                            </td>
                            <td className="border border-border px-3 py-2">
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
                            <td className="border border-border px-3 py-2 text-muted-foreground">
                              {loop.missing.join(", ")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="py-8 text-center text-muted-foreground">Nenhum loop detectado.</p>
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
                    <CardTitle className="flex items-center gap-2 text-base text-destructive">
                      <XCircle className="h-4 w-4" />
                      Erros ({result.errors.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1.5 text-sm">
                      {result.errors.map((e, i) => (
                        <li key={i} className="rounded border border-error/30 bg-error-muted px-3 py-2">{e}</li>
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
                        <li key={i} className="rounded border border-warning/30 bg-warning-muted px-3 py-2">{w}</li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {result.errors.length === 0 && result.warnings.length === 0 && (
                <div className="rounded-lg border border-border bg-card p-8 text-center">
                  <CheckCircle2 className="mx-auto h-8 w-8 text-success mb-2" />
                  <p className="text-muted-foreground">Nenhum problema de validação encontrado.</p>
                </div>
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
                            <th key={header} className="border border-border bg-muted px-3 py-2 text-left font-medium">
                              {header}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.metadata.map((meta, i) => (
                          <tr key={i} className="hover:bg-muted/50">
                            <td className="border border-border px-3 py-2 font-mono">{meta.document_number}</td>
                            <td className="border border-border px-3 py-2">{meta.revision}</td>
                            <td className="border border-border px-3 py-2">{meta.title}</td>
                            <td className="border border-border px-3 py-2">{meta.area}</td>
                            <td className="border border-border px-3 py-2">{meta.sheet_number}</td>
                            <td className="border border-border px-3 py-2">{meta.date}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="py-8 text-center text-muted-foreground">
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
                        <li key={i} className="rounded border border-border bg-muted/50 px-3 py-2">
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
