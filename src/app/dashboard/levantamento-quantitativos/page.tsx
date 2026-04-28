"use client";

import { useState, useCallback } from "react";
import { HardHat, Upload, Download, FileX, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// ── Types ──────────────────────────────────────────────────────────────────

interface ItemQuantitativo {
  item: string;
  quantidade: number | null;
  raio: number | null;
  largura: number | null;
  comprimento: number | null;
  altura: number | null;
  altura_escavacao: number | null;
  concreto_estr: number | null;
  formas_in_situ: number | null;
  grout: number | null;
  c_magro: number | null;
  escav_h_menor_1_2: number | null;
  reat_h_menor_1_2: number | null;
  bota_fora: number | null;
  estacas: number | null;
}

interface ResultadoPreview {
  documento: string;
  tanques: string[];
  total_tanques: number;
  fonte_extracao: string;
  itens: ItemQuantitativo[];
  total_1_tanque: Record<string, number>;
  total_geral: Record<string, number>;
}

// ── Column definitions ─────────────────────────────────────────────────────

const COLS_GEO: { key: keyof ItemQuantitativo; label: string }[] = [
  { key: "quantidade",      label: "QTDE" },
  { key: "raio",            label: "RAIO (m)" },
  { key: "largura",         label: "LARGURA (m)" },
  { key: "comprimento",     label: "COMPR. (m)" },
  { key: "altura",          label: "ALTURA (m)" },
  { key: "altura_escavacao",label: "H. ESCAV. (m)" },
];

const COLS_CALC: { key: keyof ItemQuantitativo; totalKey: string; label: string }[] = [
  { key: "concreto_estr",      totalKey: "concreto_estr",      label: "CONCRETO ESTR (m³)" },
  { key: "formas_in_situ",     totalKey: "formas_in_situ",     label: "FORMAS IN SITU (m²)" },
  { key: "grout",              totalKey: "grout",              label: "GROUT (m³)" },
  { key: "c_magro",            totalKey: "c_magro",            label: "C. MAGRO (m³)" },
  { key: "escav_h_menor_1_2",  totalKey: "escav_h_menor_1_2",  label: "ESCAV h<1,2 (m³)" },
  { key: "reat_h_menor_1_2",   totalKey: "reat_h_menor_1_2",   label: "REAT h<1,2 (m³)" },
  { key: "bota_fora",          totalKey: "bota_fora",          label: "BOTA FORA (m³)" },
  { key: "estacas",            totalKey: "estacas",            label: "ESTACAS (m)" },
];

// ── Helpers ────────────────────────────────────────────────────────────────

function fmt(v: number | null | undefined, decimals = 4): string {
  if (v == null || v === 0) return "—";
  return v.toLocaleString("pt-BR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtTotal(v: number | undefined, decimals = 4): string {
  if (v == null || v === 0) return "—";
  return v.toLocaleString("pt-BR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

// ── Component ──────────────────────────────────────────────────────────────

export default function LevantamentoQuantitativosPage() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState("");
  const [resultado, setResultado] = useState<ResultadoPreview | null>(null);

  const handleFile = useCallback((f: File) => {
    if (f.type !== "application/pdf") {
      setError("Apenas arquivos PDF são aceitos.");
      return;
    }
    setFile(f);
    setError("");
    setResultado(null);
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

  const handleAnalyze = async () => {
    if (!file) return;
    setIsAnalyzing(true);
    setError("");
    setResultado(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/civil/preview", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Erro ao processar o PDF");
      }

      setResultado(data as ResultadoPreview);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleDownload = async () => {
    if (!file) return;
    setIsDownloading(true);
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
        throw new Error(data.error || "Erro ao gerar Excel");
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
      setIsDownloading(false);
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
            Processe desenhos de fundação de tanques PDF e visualize ou exporte os quantitativos
          </p>
        </div>
        <Badge variant="info" className="ml-auto">Beta</Badge>
      </div>

      {/* Upload + actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Desenho de Fundação (PDF)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label
            className={cn(
              "flex min-h-[160px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors",
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
                <FileText className="h-7 w-7 text-text-secondary" />
                <p className="text-sm font-medium text-text-primary">{file.name}</p>
                <p className="text-xs text-text-tertiary">
                  {(file.size / 1024).toFixed(0)} KB · Clique para trocar
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 text-center px-4">
                <Upload className="h-7 w-7 text-text-tertiary" />
                <p className="text-sm font-medium text-text-secondary">
                  Arraste o PDF aqui ou clique para selecionar
                </p>
                <p className="text-xs text-text-tertiary">
                  Desenhos de fundação de tanques no formato Petrobras N-381
                </p>
              </div>
            )}
          </label>

          <div className="flex gap-3 justify-center">
            <Button
              size="lg"
              onClick={handleAnalyze}
              disabled={!file || isAnalyzing || isDownloading}
              className="gap-2 min-w-[180px]"
            >
              {isAnalyzing ? "Analisando..." : "Analisar PDF"}
            </Button>

            <Button
              size="lg"
              variant="outline"
              onClick={handleDownload}
              disabled={!file || isAnalyzing || isDownloading}
              className="gap-2"
            >
              <Download className="h-4 w-4" />
              {isDownloading ? "Gerando..." : "Baixar Excel"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-error/30 bg-error-muted p-4">
          <FileX className="h-5 w-5 shrink-0 text-error mt-0.5" />
          <p className="text-sm text-error-text">{error}</p>
        </div>
      )}

      {/* Results */}
      {resultado && (
        <div className="space-y-4">
          {/* Doc header */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 rounded-lg border border-border bg-surface px-4 py-3">
            <div>
              <span className="text-xs text-text-tertiary">Documento</span>
              <p className="text-sm font-mono font-medium text-text-primary">{resultado.documento}</p>
            </div>
            <div>
              <span className="text-xs text-text-tertiary">Tanques</span>
              <p className="text-sm font-medium text-text-primary">
                {resultado.tanques.length > 0 ? resultado.tanques.join(" / ") : "—"}
              </p>
            </div>
            <div>
              <span className="text-xs text-text-tertiary">Total de tanques</span>
              <p className="text-sm font-mono tabular-nums font-medium text-text-primary">
                {resultado.total_tanques}
              </p>
            </div>
          </div>

          {/* Geometry table */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-text-secondary uppercase tracking-wide">
                Geometria Extraída
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono tabular-nums">
                  <thead>
                    <tr className="border-b border-border bg-bg-secondary">
                      <th className="sticky left-0 z-10 bg-bg-secondary px-4 py-2 text-left font-medium text-text-secondary min-w-[200px]">
                        ITEM
                      </th>
                      {COLS_GEO.map((c) => (
                        <th key={c.key} className="px-3 py-2 text-right font-medium text-text-secondary whitespace-nowrap">
                          {c.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {resultado.itens.map((item, i) => (
                      <tr
                        key={i}
                        className={cn(
                          "border-b border-border/50",
                          i % 2 === 1 ? "bg-bg-secondary/50" : "bg-bg-primary"
                        )}
                      >
                        <td className="sticky left-0 z-10 px-4 py-2 font-sans text-xs font-medium text-text-primary"
                            style={{ backgroundColor: i % 2 === 1 ? "var(--color-bg-secondary)" : "var(--color-bg-primary)" }}>
                          {item.item}
                        </td>
                        {COLS_GEO.map((c) => (
                          <td key={c.key} className="px-3 py-2 text-right text-text-secondary">
                            {fmt(item[c.key] as number | null)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Quantities table */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-text-secondary uppercase tracking-wide">
                Quantitativos Calculados
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono tabular-nums">
                  <thead>
                    <tr className="border-b border-border bg-bg-secondary">
                      <th className="sticky left-0 z-10 bg-bg-secondary px-4 py-2 text-left font-medium text-text-secondary min-w-[200px]">
                        ITEM
                      </th>
                      {COLS_CALC.map((c) => (
                        <th key={c.key} className="px-3 py-2 text-right font-medium text-text-secondary whitespace-nowrap">
                          {c.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {resultado.itens.map((item, i) => (
                      <tr
                        key={i}
                        className={cn(
                          "border-b border-border/50",
                          i % 2 === 1 ? "bg-bg-secondary/50" : "bg-bg-primary"
                        )}
                      >
                        <td className="sticky left-0 z-10 px-4 py-2 font-sans text-xs font-medium text-text-primary"
                            style={{ backgroundColor: i % 2 === 1 ? "var(--color-bg-secondary)" : "var(--color-bg-primary)" }}>
                          {item.item}
                        </td>
                        {COLS_CALC.map((c) => (
                          <td key={c.key} className="px-3 py-2 text-right text-text-secondary">
                            {fmt(item[c.key] as number | null)}
                          </td>
                        ))}
                      </tr>
                    ))}

                    {/* Total 1 tanque */}
                    <tr className="border-t-2 border-border bg-success-muted">
                      <td className="sticky left-0 z-10 bg-success-muted px-4 py-2 font-sans text-xs font-bold text-success">
                        TOTAL PARA 1 TANQUE
                      </td>
                      {COLS_CALC.map((c) => (
                        <td key={c.key} className="px-3 py-2 text-right font-bold text-success">
                          {fmtTotal(resultado.total_1_tanque[c.totalKey])}
                        </td>
                      ))}
                    </tr>

                    {/* Total geral */}
                    <tr className="border-t border-border bg-info-muted">
                      <td className="sticky left-0 z-10 bg-info-muted px-4 py-2 font-sans text-xs font-bold text-info">
                        TOTAL ({resultado.total_tanques} TANQUE{resultado.total_tanques !== 1 ? "S" : ""})
                      </td>
                      {COLS_CALC.map((c) => (
                        <td key={c.key} className="px-3 py-2 text-right font-bold text-info">
                          {fmtTotal(resultado.total_geral[c.totalKey])}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Download CTA after results */}
          <div className="flex justify-end">
            <Button
              onClick={handleDownload}
              disabled={isDownloading}
              className="gap-2"
            >
              <Download className="h-4 w-4" />
              {isDownloading ? "Gerando Excel..." : "Exportar para Excel"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
