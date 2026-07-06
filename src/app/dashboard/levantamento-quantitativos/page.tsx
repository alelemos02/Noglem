"use client";

import { useState, useCallback } from "react";
import { Download, FileText, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Dropzone } from "@/components/ui/dropzone";
import { Alert } from "@/components/ui/alert";
import { toast } from "@/components/ui/toast";
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
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState("");
  const [resultado, setResultado] = useState<ResultadoPreview | null>(null);

  const handleFiles = useCallback((files: File[]) => {
    const f = files[0];
    if (!f) return;
    if (f.type !== "application/pdf" && !f.name.toLowerCase().endsWith(".pdf")) {
      setError("Apenas arquivos PDF são aceitos.");
      return;
    }
    setFile(f);
    setError("");
    setResultado(null);
  }, []);

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
      toast.success("Análise concluída", {
        description: `${(data as ResultadoPreview).total_tanques} tanque(s) identificado(s).`,
      });
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
      toast.success("Excel gerado");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader tool="levantamento-quantitativos" />

      {/* Upload + actions */}
      <Card className="gap-3 py-4">
        <CardHeader>
          <CardTitle className="text-sm">Desenho de fundação (PDF)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Dropzone
            onFiles={handleFiles}
            accept=".pdf"
            label="Arraste o PDF ou clique para selecionar"
            hint="Desenhos de fundação de tanques no formato Petrobras N-381"
            disabled={isAnalyzing || isDownloading}
          />
          {file && (
            <div className="flex items-center gap-3 rounded-md border border-edge bg-surface-2 px-3.5 py-2.5">
              <FileText className="h-4 w-4 shrink-0 text-fg-subtle" />
              <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-fg">{file.name}</span>
              <span className="shrink-0 font-mono text-xs tabular-nums text-fg-subtle">
                {(file.size / 1024).toFixed(0)} KB
              </span>
              <button
                onClick={() => { setFile(null); setResultado(null); setError(""); }}
                disabled={isAnalyzing || isDownloading}
                className="shrink-0 rounded-sm p-1 text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg"
                title="Remover arquivo"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          <div className="flex gap-3 justify-center">
            <Button
              size="lg"
              onClick={handleAnalyze}
              disabled={!file || isDownloading}
              loading={isAnalyzing}
              className="gap-2 min-w-[180px]"
            >
              {isAnalyzing ? "Analisando..." : "Analisar PDF"}
            </Button>

            <Button
              size="lg"
              variant="outline"
              onClick={handleDownload}
              disabled={!file || isAnalyzing}
              loading={isDownloading}
              className="gap-2"
            >
              {!isDownloading && <Download className="h-4 w-4" />}
              {isDownloading ? "Gerando..." : "Baixar Excel"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Error */}
      {error && <Alert variant="danger">{error}</Alert>}

      {/* Results */}
      {resultado && (
        <div className="space-y-4">
          {/* Doc header */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 rounded-lg border border-edge bg-surface-1 px-4 py-3">
            <div>
              <span className="text-xs text-fg-subtle">Documento</span>
              <p className="text-sm font-mono font-medium text-fg">{resultado.documento}</p>
            </div>
            <div>
              <span className="text-xs text-fg-subtle">Tanques</span>
              <p className="text-sm font-medium text-fg">
                {resultado.tanques.length > 0 ? resultado.tanques.join(" / ") : "—"}
              </p>
            </div>
            <div>
              <span className="text-xs text-fg-subtle">Total de tanques</span>
              <p className="text-sm font-mono tabular-nums font-medium text-fg">
                {resultado.total_tanques}
              </p>
            </div>
          </div>

          {/* Geometry table */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-fg-muted uppercase tracking-wide">
                Geometria Extraída
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono tabular-nums">
                  <thead>
                    <tr className="border-b border-edge bg-surface-1">
                      <th className="sticky left-0 z-10 bg-surface-1 px-4 py-2 text-left font-medium text-fg-muted min-w-[200px]">
                        ITEM
                      </th>
                      {COLS_GEO.map((c) => (
                        <th key={c.key} className="px-3 py-2 text-right font-medium text-fg-muted whitespace-nowrap">
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
                          "border-b border-edge/50",
                          i % 2 === 1 ? "bg-surface-1/50" : "bg-canvas"
                        )}
                      >
                        <td className="sticky left-0 z-10 px-4 py-2 font-sans text-xs font-medium text-fg"
                            style={{ backgroundColor: i % 2 === 1 ? "var(--surface-1)" : "var(--canvas)" }}>
                          {item.item}
                        </td>
                        {COLS_GEO.map((c) => (
                          <td key={c.key} className="px-3 py-2 text-right text-fg-muted">
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
              <CardTitle className="text-sm text-fg-muted uppercase tracking-wide">
                Quantitativos Calculados
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono tabular-nums">
                  <thead>
                    <tr className="border-b border-edge bg-surface-1">
                      <th className="sticky left-0 z-10 bg-surface-1 px-4 py-2 text-left font-medium text-fg-muted min-w-[200px]">
                        ITEM
                      </th>
                      {COLS_CALC.map((c) => (
                        <th key={c.key} className="px-3 py-2 text-right font-medium text-fg-muted whitespace-nowrap">
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
                          "border-b border-edge/50",
                          i % 2 === 1 ? "bg-surface-1/50" : "bg-canvas"
                        )}
                      >
                        <td className="sticky left-0 z-10 px-4 py-2 font-sans text-xs font-medium text-fg"
                            style={{ backgroundColor: i % 2 === 1 ? "var(--surface-1)" : "var(--canvas)" }}>
                          {item.item}
                        </td>
                        {COLS_CALC.map((c) => (
                          <td key={c.key} className="px-3 py-2 text-right text-fg-muted">
                            {fmt(item[c.key] as number | null)}
                          </td>
                        ))}
                      </tr>
                    ))}

                    {/* Total 1 tanque */}
                    <tr className="border-t-2 border-edge bg-success-subtle">
                      <td className="sticky left-0 z-10 bg-success-subtle px-4 py-2 font-sans text-xs font-bold text-success">
                        TOTAL PARA 1 TANQUE
                      </td>
                      {COLS_CALC.map((c) => (
                        <td key={c.key} className="px-3 py-2 text-right font-bold text-success">
                          {fmtTotal(resultado.total_1_tanque[c.totalKey])}
                        </td>
                      ))}
                    </tr>

                    {/* Total geral */}
                    <tr className="border-t border-edge bg-info-subtle">
                      <td className="sticky left-0 z-10 bg-info-subtle px-4 py-2 font-sans text-xs font-bold text-info">
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
