"use client";

/**
 * UploadWidget — dropzone inline na conversa.
 * Usado para docs de engenharia, do fornecedor e anexos.
 */

import { useState } from "react";
import { Dropzone } from "@/components/ui/dropzone";
import { Spinner } from "@/components/ui/spinner";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";
import type { UploadProgress } from "@/lib/patec-api";

function formatSize(bytes: number | null): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

type UploadRow = {
  id: string;
  name: string;
  size: number;
  phase: UploadProgress["phase"];
  percent: number | null;
};

function uploadLabel(row: UploadRow): string {
  if (row.phase === "queued") return "Na fila";
  if (row.phase === "uploading") {
    return row.percent == null ? "Enviando..." : `Enviando ${row.percent}%`;
  }
  if (row.phase === "processing") return "Processando documento...";
  if (row.phase === "done") return "Concluído";
  return "Falhou";
}

export function UploadWidget({
  tipo,
  hint,
}: {
  tipo: "engenharia" | "fornecedor" | "anexo_engenharia";
  hint: string;
}) {
  const { snapshot, uploadDocumento, deleteDocumento } = useConversation();
  const [uploading, setUploading] = useState(false);
  const [uploadRows, setUploadRows] = useState<UploadRow[]>([]);

  const docs = snapshot?.documentos.filter((d) => d.tipo === tipo) ?? [];

  const handleFiles = async (selected: File[]) => {
    if (selected.length === 0) return;
    const rows = selected.map((file) => ({
      id: `${file.name}-${file.size}-${file.lastModified}`,
      name: file.name,
      size: file.size,
      phase: "queued" as const,
      percent: 0,
    }));
    setUploadRows(rows);
    setUploading(true);
    try {
      await uploadDocumento(tipo, selected, (file, progress) => {
        const id = `${file.name}-${file.size}-${file.lastModified}`;
        setUploadRows((current) =>
          current.map((row) => (row.id === id ? { ...row, ...progress } : row))
        );
      });
      setTimeout(() => {
        setUploadRows((current) => current.filter((row) => row.phase !== "done"));
      }, 1200);
    } catch {
      setUploadRows((current) =>
        current.map((row) =>
          row.phase === "done" ? row : { ...row, phase: "error", percent: null }
        )
      );
      // erro exibido pelo provider (actionError)
    } finally {
      setUploading(false);
    }
  };

  return (
    <WidgetFrame>
      <Dropzone
        onFiles={handleFiles}
        accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.webp"
        multiple
        maxSizeMB={50}
        loading={uploading}
        label={hint}
        hint="PDF, DOCX, XLSX, PNG, JPG ou WEBP (máx 50MB) — arraste ou clique"
        compact
      />

      {uploadRows.length > 0 && (
        <ul className="mt-3 space-y-2">
          {uploadRows.map((row) => (
            <li
              key={row.id}
              className="rounded-md border border-edge bg-canvas px-3 py-2"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm text-fg">{row.name}</p>
                  <p className="text-xs text-fg-subtle">
                    {formatSize(row.size)} · {uploadLabel(row)}
                  </p>
                </div>
                {row.phase === "processing" && (
                  <Spinner size="xs" className="shrink-0 text-accent" />
                )}
              </div>
              <div className="mt-2 h-1 overflow-hidden rounded-full bg-surface-2">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    row.phase === "error" ? "bg-danger" : "bg-accent"
                  }`}
                  style={{
                    width: `${row.phase === "processing" ? 100 : (row.percent ?? 18)}%`,
                  }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}

      {docs.length > 0 && (
        <ul className="mt-3 space-y-1">
          {docs.map((doc) => (
            <li
              key={doc.id}
              className="rounded-md bg-surface-2 px-3 py-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-sm text-fg">
                    {doc.nome_arquivo}
                  </span>
                  {doc.tamanho_bytes != null && (
                    <span className="shrink-0 text-xs text-fg-subtle">
                      {formatSize(doc.tamanho_bytes)}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => deleteDocumento(doc.id).catch(() => {})}
                  className="ml-2 shrink-0 text-xs text-fg-subtle hover:text-danger-text"
                >
                  Remover
                </button>
              </div>
              {doc.aviso_extracao && (
                <p className="mt-1.5 flex items-start gap-1.5 text-xs text-warning-text">
                  <span aria-hidden="true">⚠</span>
                  <span>{doc.aviso_extracao}</span>
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </WidgetFrame>
  );
}
