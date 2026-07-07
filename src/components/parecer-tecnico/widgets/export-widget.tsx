"use client";

/**
 * ExportWidget — exportação do parecer (PDF/XLSX/DOCX) no fechamento.
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { ExportFormat } from "@/lib/patec-api";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";

const FORMATOS: Array<{ formato: ExportFormat; label: string }> = [
  { formato: "pdf", label: "PDF" },
  { formato: "xlsx", label: "Excel" },
  { formato: "docx", label: "Word" },
];

export function ExportWidget() {
  const { exportar } = useConversation();
  const [exporting, setExporting] = useState<ExportFormat | null>(null);

  const handleExport = async (formato: ExportFormat) => {
    setExporting(formato);
    try {
      await exportar(formato);
    } catch {
      // erro exibido pelo provider
    } finally {
      setExporting(null);
    }
  };

  return (
    <WidgetFrame>
      <div className="flex flex-wrap gap-2">
        {FORMATOS.map(({ formato, label }) => (
          <Button
            key={formato}
            variant="secondary"
            size="sm"
            onClick={() => handleExport(formato)}
            loading={exporting === formato}
            disabled={exporting !== null}
          >
            Exportar {label}
          </Button>
        ))}
      </div>
    </WidgetFrame>
  );
}
