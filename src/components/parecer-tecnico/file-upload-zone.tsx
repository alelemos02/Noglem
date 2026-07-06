"use client";

import { useState } from "react";
import { patecApi, type DocumentoResponse } from "@/lib/patec-api";
import { Dropzone } from "@/components/ui/dropzone";
import { toast } from "@/components/ui/toast";

interface FileUploadZoneProps {
  parecerId: string;
  tipo: "engenharia" | "fornecedor" | "anexo_engenharia";
  label: string;
  documentos: DocumentoResponse[];
  onUploadComplete: () => void;
}

export function FileUploadZone({ parecerId, tipo, label, documentos, onUploadComplete }: FileUploadZoneProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const filtered = documentos.filter((d) => d.tipo === tipo);

  const handleFiles = async (files: File[]) => {
    if (files.length === 0) return;
    setUploading(true);
    setError("");
    try {
      for (const file of files) {
        await patecApi.documentos.upload(parecerId, tipo, file);
      }
      onUploadComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro no upload");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId: string) => {
    try {
      await patecApi.documentos.delete(parecerId, docId);
      onUploadComplete();
      toast.success("Documento removido");
    } catch {
      setError("Erro ao remover documento");
    }
  };

  const formatSize = (bytes: number | null) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  };

  return (
    <div>
      <p className="mb-2 text-sm font-medium text-fg-muted">{label}</p>
      <Dropzone
        onFiles={handleFiles}
        accept=".pdf,.docx,.xlsx"
        multiple
        compact
        loading={uploading}
        error={error}
        hint="PDF, DOCX, XLSX (máx. 50 MB)"
      />

      {filtered.length > 0 && (
        <ul className="mt-3 space-y-1">
          {filtered.map((doc) => (
            <li key={doc.id} className="flex items-center justify-between rounded-md border border-edge bg-surface-2 px-3 py-2">
              <div className="flex min-w-0 items-center gap-2">
                <span className="truncate text-sm text-fg">{doc.nome_arquivo}</span>
                {doc.tamanho_bytes && (
                  <span className="flex-shrink-0 font-mono text-xs tabular-nums text-fg-subtle">{formatSize(doc.tamanho_bytes)}</span>
                )}
              </div>
              <button onClick={() => handleDelete(doc.id)} className="ml-2 text-xs text-fg-subtle transition-colors hover:text-danger-text">
                Remover
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
