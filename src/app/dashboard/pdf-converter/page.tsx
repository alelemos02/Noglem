"use client";

import { useState, useCallback } from "react";
import { FileText, Upload, Download, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface ConvertResult {
  filename: string;
  original_size: number;
  converted_size: number;
  download_url: string;
}

export default function PdfConverterPage() {
  const [file, setFile] = useState<File | null>(null);
  const [isConverting, setIsConverting] = useState(false);
  const [result, setResult] = useState<ConvertResult | null>(null);
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

  const handleConvert = async () => {
    if (!file) return;

    setIsConverting(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/pdf/convert", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Erro na conversão");
      }

      setResult(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro desconhecido";
      setError(message);
      console.error("Erro na conversão:", err);
    } finally {
      setIsConverting(false);
    }
  };

  const handleDownload = async () => {
    if (!result) return;

    try {
      const response = await fetch(
        result.download_url
      );

      if (!response.ok) {
        throw new Error("Erro ao baixar arquivo");
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${file?.name.replace(".pdf", "") || "document"}.docx`;
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-orange-500/10">
          <FileText className="h-6 w-6 text-orange-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">PDF para Word</h1>
          <p className="text-muted-foreground">
            Converta PDFs para documentos Word editáveis
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
                <FileText className="h-12 w-12 text-orange-500" />
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
        <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-4 text-center text-sm text-red-500">
          {error}
        </div>
      )}

      {/* Progress/Action */}
      {file && (
        <Card>
          <CardContent className="pt-6">
            {isConverting ? (
              <div className="flex flex-col items-center gap-4">
                <div className="h-12 w-12 animate-spin rounded-full border-4 border-muted border-t-primary" />
                <p className="font-medium">Convertendo PDF para Word...</p>
                <p className="text-sm text-muted-foreground">
                  Isso pode levar alguns segundos dependendo do tamanho do arquivo
                </p>
              </div>
            ) : result ? (
              <div className="flex flex-col items-center gap-4">
                <CheckCircle className="h-12 w-12 text-green-500" />
                <p className="font-medium">Conversão concluída!</p>
                <div className="flex items-center gap-6 text-sm text-muted-foreground">
                  <span>Original: {formatSize(result.original_size)}</span>
                  <span>Convertido: {formatSize(result.converted_size)}</span>
                </div>
                <Button onClick={handleDownload} className="gap-2">
                  <Download className="h-4 w-4" />
                  Baixar documento Word
                </Button>
              </div>
            ) : (
              <div className="flex justify-center">
                <Button size="lg" onClick={handleConvert} className="gap-2">
                  <FileText className="h-4 w-4" />
                  Converter para Word
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
