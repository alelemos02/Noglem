"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { patecApi, type ExportFormat } from "@/lib/patec-api";

export function ExportButton({ parecerId }: { parecerId: string }) {
  const [formato, setFormato] = useState<ExportFormat>("pdf");
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const { blob, filename } = await patecApi.exportacoes.download(parecerId, formato);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silently fail
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex items-center gap-1">
      <select
        value={formato}
        onChange={(e) => setFormato(e.target.value as ExportFormat)}
        className="h-8 rounded-md border border-border bg-surface px-2 text-xs text-text-secondary focus:border-border-focus outline-none"
      >
        <option value="pdf">PDF</option>
        <option value="xlsx">XLSX</option>
        <option value="docx">DOCX</option>
      </select>
      <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting}>
        {exporting ? "..." : "Exportar"}
      </Button>
    </div>
  );
}
