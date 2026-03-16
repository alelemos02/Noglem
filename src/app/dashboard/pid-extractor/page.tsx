"use client";

import { useState, useCallback } from "react";
import { Gauge, Upload, FileText, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface InstrumentData {
  tag: string;
  isa_type: string;
  description: string;
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

interface ExtractResult {
  filename: string;
  total_instruments: number;
  total_equipment: number;
  total_loops: number;
  total_warnings: number;
  total_errors: number;
  instruments: InstrumentData[];
  loops: LoopData[];
  warnings: string[];
  errors: string[];
}

export default function PidExtractorPage() {
  const [file, setFile] = useState<File | null>(null);
  const [profile, setProfile] = useState<"promon" | "technip">("promon");
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
      formData.append("profile", profile);

      const response = await fetch("/api/pid/extract", {
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
      formData.append("profile", profile);

      const response = await fetch("/api/pid/extract/download", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Erro ao gerar Excel");
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${file.name.replace(".pdf", "")}_instrument_index.xlsx`;
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
                <FileText className="h-12 w-12 text-warning" />
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
                  Arraste um PDF de P&ID ou clique para selecionar
                </p>
                <p className="text-sm text-muted-foreground">
                  Apenas P&IDs vetoriais (não escaneados)
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

          {/* Profile selector */}
          <div className="flex items-center gap-4">
            <span className="text-sm font-medium">Perfil de tags:</span>
            <div className="flex gap-2">
              <Button
                variant={profile === "promon" ? "default" : "outline"}
                size="sm"
                onClick={() => setProfile("promon")}
              >
                Promon / Nacional
              </Button>
              <Button
                variant={profile === "technip" ? "default" : "outline"}
                size="sm"
                onClick={() => setProfile("technip")}
              >
                Technip / Internacional
              </Button>
            </div>
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
                Extraindo instrumentos...
              </>
            ) : (
              <>
                <Gauge className="h-4 w-4" />
                Extrair Instrumentos
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
              <p className="text-2xl font-bold">{result.total_instruments}</p>
              <p className="text-xs text-muted-foreground">Instrumentos</p>
            </div>
            <div className="h-8 w-px bg-border" />
            <div className="text-center">
              <p className="text-2xl font-bold">{result.total_equipment}</p>
              <p className="text-xs text-muted-foreground">Equipamentos</p>
            </div>
            <div className="h-8 w-px bg-border" />
            <div className="text-center">
              <p className="text-2xl font-bold">{result.total_loops}</p>
              <p className="text-xs text-muted-foreground">Loops</p>
            </div>
            <div className="h-8 w-px bg-border" />
            <div className="text-center">
              <p className="text-2xl font-bold text-warning">{result.total_warnings}</p>
              <p className="text-xs text-muted-foreground">Avisos</p>
            </div>
            {result.total_errors > 0 && (
              <>
                <div className="h-8 w-px bg-border" />
                <div className="text-center">
                  <p className="text-2xl font-bold text-destructive">{result.total_errors}</p>
                  <p className="text-xs text-muted-foreground">Erros</p>
                </div>
              </>
            )}
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
                    Baixar Excel
                  </>
                )}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setResult(null);
                  setFile(null);
                  setError("");
                }}
              >
                Nova extração
              </Button>
            </div>
          </div>

          {/* Instruments Table */}
          {result.instruments.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  Instrument Index ({result.instruments.length} instrumentos)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr>
                        {["Tag", "Tipo ISA", "Descrição", "Área", "Equipamento", "Loop", "Folha", "Conf."].map(
                          (header) => (
                            <th
                              key={header}
                              className="border border-border bg-muted px-3 py-2 text-left font-medium"
                            >
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
                          </td>
                          <td className="border border-border px-3 py-2">{inst.isa_type}</td>
                          <td className="border border-border px-3 py-2">{inst.description}</td>
                          <td className="border border-border px-3 py-2">{inst.area}</td>
                          <td className="border border-border px-3 py-2">{inst.equipment}</td>
                          <td className="border border-border px-3 py-2">{inst.loop_id}</td>
                          <td className="border border-border px-3 py-2">{inst.sheet}</td>
                          <td className="border border-border px-3 py-2">
                            <span
                              className={
                                inst.confidence < 0.5
                                  ? "text-destructive font-medium"
                                  : inst.confidence < 0.8
                                    ? "text-warning font-medium"
                                    : ""
                              }
                            >
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
          )}

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-warning">
                  Avisos ({result.warnings.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {result.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* No instruments found */}
          {result.instruments.length === 0 && (
            <div className="rounded-lg border border-border bg-card p-8 text-center">
              <p className="text-muted-foreground">
                Nenhum instrumento encontrado neste PDF. Verifique se o P&ID é vetorial e se o perfil de tags está correto.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
