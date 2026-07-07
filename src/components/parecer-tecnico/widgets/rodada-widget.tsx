"use client";

/**
 * RodadaWidget — entrada da resposta do fornecedor (blocos 21-22), inline.
 * Adaptado de rodada-upload-dialog.tsx: 4 tipos como cards + arquivo/texto.
 */

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import type { TipoRodada } from "@/lib/patec-api";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";

const TIPOS: Array<{
  value: TipoRodada;
  numero: number;
  label: string;
  descricao: string;
}> = [
  {
    value: "PROPOSTA_REVISADA",
    numero: 1,
    label: "Proposta totalmente revisada",
    descricao:
      "O fornecedor reemitiu a proposta completa incorporando as correções. Exige o documento.",
  },
  {
    value: "RESPOSTA_ITENS",
    numero: 2,
    label: "Respostas aos itens",
    descricao:
      "O fornecedor respondeu ponto a ponto às pendências, sem reemitir a proposta.",
  },
  {
    value: "RESPOSTA_ITENS_PROPOSTA_POSTERIOR",
    numero: 3,
    label: "Respostas + proposta depois",
    descricao:
      "Respostas pontuais agora; a proposta revisada será enviada em seguida.",
  },
  {
    value: "EMAIL_AVULSO",
    numero: 4,
    label: "E-mail avulso",
    descricao: "Material informal: e-mails, esclarecimentos parciais.",
  },
];

export function RodadaWidget({ onDone }: { onDone?: () => void }) {
  const { criarRodada } = useConversation();
  const [tipo, setTipo] = useState<TipoRodada>("RESPOSTA_ITENS");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [textoColado, setTextoColado] = useState("");
  const [enviando, setEnviando] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const exigeArquivo = tipo === "PROPOSTA_REVISADA";
  const podeEnviar = exigeArquivo
    ? !!arquivo
    : !!arquivo || textoColado.trim().length > 0;

  const handleEnviar = async () => {
    setEnviando(true);
    try {
      await criarRodada(tipo, {
        arquivo: arquivo ?? undefined,
        textoColado: textoColado.trim() || undefined,
      });
      onDone?.();
    } catch {
      // erro exibido pelo provider
    } finally {
      setEnviando(false);
    }
  };

  return (
    <WidgetFrame title="Como o fornecedor respondeu?">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {TIPOS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTipo(t.value)}
            disabled={enviando}
            className={`rounded-lg border p-3 text-left transition-colors ${
              tipo === t.value
                ? "border-accent bg-accent-subtle"
                : "border-edge bg-canvas hover:border-edge-strong"
            }`}
          >
            <p className="text-sm font-medium text-fg">
              Tipo {t.numero} — {t.label}
            </p>
            <p className="mt-0.5 text-xs text-fg-subtle">{t.descricao}</p>
          </button>
        ))}
      </div>

      <div className="mt-3 space-y-2">
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.xlsx"
            className="hidden"
            onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
          />
          <Button
            size="sm"
            variant="secondary"
            onClick={() => fileRef.current?.click()}
            disabled={enviando}
          >
            {arquivo ? "Trocar arquivo" : "Selecionar arquivo"}
          </Button>
          {arquivo && (
            <span className="flex min-w-0 items-center gap-2 text-xs text-fg-muted">
              <span className="truncate">{arquivo.name}</span>
              <button
                className="shrink-0 text-danger/80 hover:text-danger"
                onClick={() => {
                  setArquivo(null);
                  if (fileRef.current) fileRef.current.value = "";
                }}
              >
                remover
              </button>
            </span>
          )}
        </div>

        {tipo !== "PROPOSTA_REVISADA" && (
          <textarea
            value={textoColado}
            onChange={(e) => setTextoColado(e.target.value)}
            placeholder={
              tipo === "EMAIL_AVULSO"
                ? "Ou cole o conteúdo do e-mail aqui..."
                : "Ou cole o texto da resposta aqui..."
            }
            rows={4}
            disabled={enviando}
            className="w-full resize-none rounded-lg border border-edge bg-canvas px-3 py-2 text-sm text-fg outline-none placeholder:text-fg-subtle focus:border-accent"
          />
        )}
      </div>

      <div className="mt-3 flex justify-end">
        <Button
          onClick={handleEnviar}
          disabled={!podeEnviar || enviando}
          loading={enviando}
        >
          Enviar para a JulIA vincular
        </Button>
      </div>
    </WidgetFrame>
  );
}
