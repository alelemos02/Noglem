"use client";

/**
 * InputBar — entrada de texto sempre disponível na base da tela.
 * Pipeline: comando local (commands.ts) → senão, chat RAG (SSE).
 */

import { useState, useRef, useCallback } from "react";
import { ArrowUp, Paperclip } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";
import { useConversation } from "./conversation-provider";
import { matchCommand } from "./commands";

type UploadTipo = "engenharia" | "fornecedor" | "anexo_engenharia";

function uploadTarget(conversation: ReturnType<typeof useConversation>): {
  tipo: UploadTipo;
  label: string;
} {
  const stepId = conversation.step?.id;
  if (
    stepId === "analise.docs_forn" ||
    stepId === "setup.docs_forn" ||
    stepId === "ciclo.aguardando_fornecedor" ||
    stepId === "verificacao.aguardando_proposta"
  ) {
    return { tipo: "fornecedor", label: "documento do fornecedor" };
  }
  if (stepId === "spec.diff_decisao" || stepId === "spec.comparando") {
    return { tipo: "anexo_engenharia", label: "anexo da engenharia" };
  }
  return { tipo: "engenharia", label: "documento da engenharia" };
}

export function InputBar() {
  const conversation = useConversation();
  const { chatSending, sendFreeText, pushEphemeral, uploadDocumento } = conversation;
  const [value, setValue] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = useCallback(async () => {
    const text = value.trim();
    if (!text || chatSending) return;
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    const command = matchCommand(text);
    if (command) {
      // ecoa o comando do usuário na thread antes de executá-lo
      pushEphemeral({
        kind: "user",
        key: `cmd-user-${Date.now()}`,
        at: new Date().toISOString(),
        text,
      });
      await command.run(conversation);
      return;
    }
    await sendFreeText(text);
  }, [value, chatSending, conversation, sendFreeText, pushEphemeral]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0 || uploading) return;
      const target = uploadTarget(conversation);
      setUploading(true);
      setUploadStatus("Preparando envio...");
      try {
        await uploadDocumento(target.tipo, files, (file, progress) => {
          if (progress.phase === "uploading") {
            setUploadStatus(
              progress.percent == null
                ? `Enviando ${file.name}...`
                : `Enviando ${file.name}: ${progress.percent}%`
            );
          } else if (progress.phase === "processing") {
            setUploadStatus(`Processando ${file.name}...`);
          }
        });
        const count = files.length;
        pushEphemeral({
          kind: "event",
          key: `upload-input-${Date.now()}`,
          at: new Date().toISOString(),
          title: "Arquivo anexado",
          detail: `${count} ${count === 1 ? "arquivo enviado" : "arquivos enviados"} como ${target.label}`,
          tone: "success",
        });
      } catch {
        // O provider exibe o erro no bloco de ação.
      } finally {
        setUploading(false);
        setUploadStatus("");
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    },
    [conversation, pushEphemeral, uploadDocumento, uploading]
  );

  return (
    <div className="border-t border-edge bg-canvas/95 backdrop-blur">
      <div className="mx-auto w-full max-w-4xl px-4 py-3">
        <div className="flex items-end gap-2 rounded-xl border border-edge bg-surface-1 px-3 py-2 transition-colors focus-within:border-accent">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.webp"
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={chatSending || uploading}
            aria-label="Anexar arquivo"
            title="Anexar arquivo"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-fg-subtle transition-colors hover:bg-surface-2 hover:text-fg disabled:opacity-40"
          >
            {uploading ? (
              <Spinner size="sm" />
            ) : (
              <Paperclip className="h-4 w-4" />
            )}
          </button>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Pergunte algo à JulIA ou digite um comando (ex: ver itens)..."
            disabled={chatSending}
            rows={1}
            className="max-h-40 flex-1 resize-none bg-transparent py-1 text-sm text-fg outline-none placeholder:text-fg-subtle disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!value.trim() || chatSending}
            aria-label="Enviar"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-fg transition-colors hover:bg-accent-hover disabled:opacity-40"
          >
            {chatSending ? (
              <Spinner size="sm" />
            ) : (
              <ArrowUp className="h-4 w-4" strokeWidth={2.5} />
            )}
          </button>
        </div>
        {uploadStatus && (
          <p className="mt-1 px-1 text-xs text-fg-subtle">{uploadStatus}</p>
        )}
      </div>
    </div>
  );
}
