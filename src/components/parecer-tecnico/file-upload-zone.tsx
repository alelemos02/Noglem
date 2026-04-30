"use client";

import { useState, useRef } from "react";
import { patecApi, type DocumentoResponse } from "@/lib/patec-api";

interface FileUploadZoneProps {
  parecerId: string;
  tipo: "engenharia" | "fornecedor";
  label: string;
  documentos: DocumentoResponse[];
  onUploadComplete: () => void;
}

export function FileUploadZone({ parecerId, tipo, label, documentos, onUploadComplete }: FileUploadZoneProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = documentos.filter((d) => d.tipo === tipo);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError("");
    try {
      for (const file of Array.from(files)) {
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
      <p className="mb-2 text-sm font-medium text-text-secondary">{label}</p>
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
        className={`cursor-pointer rounded-lg border-2 border-dashed p-4 text-center transition-colors ${
          dragOver ? "border-info bg-info-muted" : "border-border hover:border-border-hover"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.xlsx"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        <p className="text-sm text-text-tertiary">
          {uploading ? "Enviando..." : "Arraste arquivos ou clique para selecionar"}
        </p>
        <p className="mt-1 text-xs text-text-disabled">PDF, DOCX, XLSX (max 50MB)</p>
      </div>

      {error && <p className="mt-2 text-xs text-error-text">{error}</p>}

      {filtered.length > 0 && (
        <ul className="mt-3 space-y-1">
          {filtered.map((doc) => (
            <li key={doc.id} className="flex items-center justify-between rounded-md bg-surface-hover px-3 py-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="truncate text-sm text-text-primary">{doc.nome_arquivo}</span>
                {doc.tamanho_bytes && (
                  <span className="flex-shrink-0 text-xs text-text-tertiary">{formatSize(doc.tamanho_bytes)}</span>
                )}
              </div>
              <button onClick={() => handleDelete(doc.id)} className="ml-2 text-xs text-text-tertiary hover:text-error-text">
                Remover
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
