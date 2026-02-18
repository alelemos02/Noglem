"use client";

import { useState, useCallback } from "react";
import { FileText, Upload, Download, CheckCircle, FileType } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

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
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState("");

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFile = e.dataTransfer.files[0];
    const expectedType = mode === "convert" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

    if (droppedFile?.type === expectedType ||
      (mode === "format" && droppedFile?.name.endsWith(".docx"))) {
      setFile(droppedFile);
      setResult(null);
      setError("");
    } else {
      setError(`Formato inválido. Por favor envie um arquivo ${mode === "convert" ? "PDF" : "Word (.docx)"}.`);
    }
  }, [mode]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResult(null);
      setError("");
    }
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
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className={`flex h-12 w-12 items-center justify-center rounded-lg ${mode === "convert" ? "bg-warning-muted text-warning" : "bg-info-muted text-info"}`}>
          {mode === "convert" ? <FileText className="h-6 w-6" /> : <FileType className="h-6 w-6" />}
        </div>
        <div>
          <h1 className="text-2xl font-bold">Ferramentas de Documento</h1>
          <p className="text-muted-foreground">
            {mode === "convert" ? "Converta PDFs para documentos Word editáveis" : "Formate e limpe documentos Word (.docx)"}
          </p>
        </div>
        <Badge variant="secondary" className="ml-auto">Beta</Badge>
      </div>

      {/* Mode Switcher */}
      <div className="flex p-1 bg-muted rounded-lg w-fit">
        <button
          onClick={() => toggleMode("convert")}
          className={`px-4 py-2 text-sm font-medium rounded-md transition-all ${mode === "convert" ? "bg-background shadow text-foreground" : "text-muted-foreground hover:text-foreground"}`}
        >
          Converter PDF
        </button>
        <button
          onClick={() => toggleMode("format")}
          className={`px-4 py-2 text-sm font-medium rounded-md transition-all ${mode === "format" ? "bg-background shadow text-foreground" : "text-muted-foreground hover:text-foreground"}`}
        >
          Formatar Word
        </button>
      </div>

      {/* Upload Area */}
      <Card>
        <CardHeader>
          <CardTitle>Upload de {mode === "convert" ? "PDF" : "Word (.docx)"}</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            onDrop={handleDrop}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            className={`flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors ${isDragging
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50"
              }`}
          >
            {file ? (
              <div className="flex flex-col items-center gap-2">
                {mode === "convert" ? <FileText className="h-12 w-12 text-warning" /> : <FileType className="h-12 w-12 text-info" />}
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
                  Arraste um {mode === "convert" ? "PDF" : "Word"} ou clique para selecionar
                </p>
                <p className="text-sm text-muted-foreground">
                  Apenas arquivos {mode === "convert" ? ".pdf" : ".docx"} são aceitos
                </p>
                <input
                  type="file"
                  accept={mode === "convert" ? ".pdf" : ".docx"}
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

      {/* Progress/Action */}
      {file && (
        <Card>
          <CardContent className="pt-6">
            {isProcessing ? (
              <div className="flex flex-col items-center gap-4">
                <div className="h-12 w-12 animate-spin rounded-full border-4 border-muted border-t-primary" />
                <p className="font-medium">{mode === "convert" ? "Convertendo PDF para Word..." : "Formatando documento Word..."}</p>
                <p className="text-sm text-muted-foreground">
                  Isso pode levar alguns segundos dependendo do tamanho do arquivo
                </p>
              </div>
            ) : result ? (
              <div className="flex flex-col items-center gap-4">
                <CheckCircle className="h-12 w-12 text-success" />
                <p className="font-medium">{mode === "convert" ? "Conversão concluída!" : "Formatação concluída!"}</p>
                <div className="flex items-center gap-6 text-sm text-muted-foreground">
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
                  {mode === "convert" ? "Converter para Word" : "Formatar Documento"}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
