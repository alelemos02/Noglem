"use client";

import { useState, useCallback } from "react";
import { HardHat, Upload, Download, FileX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export default function LevantamentoQuantitativosPage() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState("");

  const handleFile = useCallback((f: File) => {
    if (f.type !== "application/pdf") {
      setError("Apenas arquivos PDF são aceitos.");
      return;
    }
    setFile(f);
    setError("");
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const dropped = e.dataTransfer.files[0];
      if (dropped) handleFile(dropped);
    },
    [handleFile]
  );

  const handleProcess = async () => {
    if (!file) return;

    setIsProcessing(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/civil/processar", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({ error: "Erro no servidor" }));
        throw new Error(data.error || "Erro ao processar o PDF");
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      a.download = match ? match[1] : `quantitativo_${file.name.replace(".pdf", "")}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-surface border border-border">
          <HardHat className="h-6 w-6 text-text-secondary" />
        </div>
        <div>
          <h1 className="text-2xl font-heading font-bold text-text-primary">
            Levantamento de Quantitativos
          </h1>
          <p className="text-sm text-text-secondary">
            Processe desenhos de fundação de tanques PDF e gere planilha Excel de quantitativos
          </p>
        </div>
        <Badge variant="info" className="ml-auto">Beta</Badge>
      </div>

      {/* Upload area */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Desenho de Fundação (PDF)</CardTitle>
        </CardHeader>
        <CardContent>
          <label
            className={cn(
              "flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors",
              isDragging
                ? "border-border-focus bg-surface-hover"
                : "border-border hover:border-border-hover hover:bg-surface-hover"
            )}
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
          >
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
              }}
            />
            {file ? (
              <div className="flex flex-col items-center gap-2 text-center">
                <Download className="h-8 w-8 text-text-secondary" />
                <p className="text-sm font-medium text-text-primary">{file.name}</p>
                <p className="text-xs text-text-tertiary">
                  {(file.size / 1024).toFixed(0)} KB · Clique para trocar
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 text-center px-4">
                <Upload className="h-8 w-8 text-text-tertiary" />
                <p className="text-sm font-medium text-text-secondary">
                  Arraste o PDF aqui ou clique para selecionar
                </p>
                <p className="text-xs text-text-tertiary">
                  Aceita desenhos de fundação de tanques no formato Petrobras N-381
                </p>
              </div>
            )}
          </label>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-error/30 bg-error-muted p-4">
          <FileX className="h-5 w-5 shrink-0 text-error mt-0.5" />
          <p className="text-sm text-error-text">{error}</p>
        </div>
      )}

      {/* Action */}
      <div className="flex justify-center">
        <Button
          size="lg"
          onClick={handleProcess}
          disabled={!file || isProcessing}
          className="gap-2 min-w-[220px]"
        >
          {isProcessing ? (
            "Processando..."
          ) : (
            <>
              <Download className="h-4 w-4" />
              Processar e Baixar Excel
            </>
          )}
        </Button>
      </div>

      {/* Info */}
      <Card>
        <CardContent className="pt-6">
          <p className="text-xs text-text-tertiary leading-relaxed">
            A extração usa análise vetorial, texto nativo e OCR para identificar geometrias de
            fundação (raios, alturas, estacas) e calcular quantitativos de concreto estrutural,
            formas, concreto magro, escavação e estacas HP310×110. O arquivo Excel gerado segue
            o formato padrão Petrobras com totais por tanque e total geral.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
