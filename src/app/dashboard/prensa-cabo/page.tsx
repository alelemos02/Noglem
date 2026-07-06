"use client";

import { PageHeader } from "@/components/ui/page-header";

export default function PrensaCaboPage() {
  return (
    <div className="flex h-[calc(100vh-7.5rem)] flex-col">
      <PageHeader
        tool="prensa-cabo"
        description="Seleção de prensa-cabos e geração de BOM — módulo externo, com visual próprio."
        className="mb-4 shrink-0"
      />
      <iframe
        src="/tools/prensa-cabo.html"
        className="w-full flex-1 rounded-lg border border-edge"
        title="Prensa Cabo Analyzer"
      />
    </div>
  );
}
