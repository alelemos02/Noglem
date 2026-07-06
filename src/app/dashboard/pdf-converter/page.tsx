"use client";

import { useState } from "react";
import { FileText, Download, CheckCircle, FileType, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Dropzone } from "@/components/ui/dropzone";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

type Mode = "convert" | "format";

interface Result {
  filename: string;
  original_size: number;
  final_size: number; // Abstração para converted_size ou formatted_size
  download_url: string;
}

export default function PdfConverterPage() {
  const [mode, setMode] = useState<Mode>("convert");
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");

  const acceptFile = (files: File[]) => {
    const selected = files[0];
    if (!selected) return;
    const validExt = mode === "convert" ? ".pdf" : ".docx";
    if (!selected.name.toLowerCase().endsWith(validExt)) {
      setError(`Formato inválido. Envie um arquivo ${mode === "convert" ? "PDF" : "Word (.docx)"}.`);
      return;
    }
    setFile(selected);
    setResult(null);
    setError("");
  };

  const handleProcess = async () => {
    if (!file) return;

    setIsProcessing(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const endpoint = mode === "convert" ? "/api/pdf/convert" : "/api/pdf/format";

      const response = await fetch(endpoint, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Erro no processamento");
      }

      setResult({
        filename: data.filename,
        original_size: data.original_size,
        final_size: mode === "convert" ? data.converted_size : data.formatted_size,
        download_url: data.download_url
      });
      toast.success(mode === "convert" ? "Conversão concluída" : "Formatação concluída", {
        description: data.filename,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro desconhecido";
      setError(message);
      console.error("Erro:", err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownload = async () => {
    if (!result) return;

    try {
      // O download_url já vem com query params se necessário
      const response = await fetch(result.download_url);

      if (!response.ok) {
        throw new Error("Erro ao baixar arquivo");
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      // Usar o nome retornado pela API ou gerar um
      a.download = result.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro desconhecido";
      setError(message);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  };

  const toggleMode = (newMode: Mode) => {
    setMode(newMode);
    setFile(null);
    setResult(null);
    setError("");
  };

  return (
    <div className="space-y-6">
      <PageHeader
        tool="pdf-converter"
        description={
          mode === "convert"
            ? "Converta PDFs para documentos Word editáveis"
            : "Formate e limpe documentos Word (.docx)"
        }
      />

      {/* Mode Switcher */}
      <div className="flex w-fit rounded-md border border-edge bg-surface-1 p-0.5">
        <button
          onClick={() => toggleMode("convert")}
          className={cn(
            "rounded-sm px-4 py-1.5 text-[13px] font-medium transition-colors",
            mode === "convert" ? "bg-surface-3 text-fg" : "text-fg-muted hover:text-fg"
          )}
        >
          Converter PDF
        </button>
        <button
          onClick={() => toggleMode("format")}
          className={cn(
            "rounded-sm px-4 py-1.5 text-[13px] font-medium transition-colors",
            mode === "format" ? "bg-surface-3 text-fg" : "text-fg-muted hover:text-fg"
          )}
        >
          Formatar Word
        </button>
      </div>

      {/* Upload Area */}
      <Card className="gap-0 py-0">
        <CardContent className="p-4">
          <Dropzone
            onFiles={acceptFile}
            accept={mode === "convert" ? ".pdf" : ".docx"}
            label={`Arraste um ${mode === "convert" ? "PDF" : "Word"} ou clique para selecionar`}
            hint={`Apenas arquivos ${mode === "convert" ? ".pdf" : ".docx"} são aceitos`}
            disabled={isProcessing}
          />
          {file && (
            <div className="mt-3 flex items-center gap-3 rounded-md border border-edge bg-surface-2 px-3.5 py-2.5">
              {mode === "convert" ? (
                <FileText className="h-4 w-4 shrink-0 text-fg-subtle" />
              ) : (
                <FileType className="h-4 w-4 shrink-0 text-fg-subtle" />
              )}
              <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-fg">{file.name}</span>
              <span className="shrink-0 font-mono text-xs tabular-nums text-fg-subtle">
                {formatSize(file.size)}
              </span>
              <button
                onClick={() => {
                  setFile(null);
                  setResult(null);
                  setError("");
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

      {/* Progress/Action */}
      {file && (
        <Card className="gap-0 py-0">
          <CardContent className="p-6">
            {isProcessing ? (
              <div className="flex flex-col items-center gap-3">
                <Spinner size="lg" className="text-accent" />
                <p className="text-sm font-medium text-fg">
                  {mode === "convert" ? "Convertendo PDF para Word..." : "Formatando documento Word..."}
                </p>
                <p className="text-[13px] text-fg-muted">
                  Isso pode levar alguns segundos dependendo do tamanho do arquivo
                </p>
              </div>
            ) : result ? (
              <div className="flex flex-col items-center gap-4">
                <CheckCircle className="h-8 w-8 text-success" />
                <p className="text-sm font-medium text-fg">
                  {mode === "convert" ? "Conversão concluída" : "Formatação concluída"}
                </p>
                <div className="flex items-center gap-6 font-mono text-xs tabular-nums text-fg-muted">
                  <span>Original: {formatSize(result.original_size)}</span>
                  <span>Final: {formatSize(result.final_size)}</span>
                </div>
                <Button onClick={handleDownload} className="gap-2">
                  <Download className="h-4 w-4" />
                  Baixar documento
                </Button>
              </div>
            ) : (
              <div className="flex justify-center">
                <Button size="lg" onClick={handleProcess} className="gap-2">
                  {mode === "convert" ? <FileText className="h-4 w-4" /> : <FileType className="h-4 w-4" />}
                  {mode === "convert" ? "Converter para Word" : "Formatar documento"}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
