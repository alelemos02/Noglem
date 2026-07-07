"use client";

/**
 * SpecUploadWidget — entrada do caminho lateral de revisão de especificação
 * (bloco 35): upload da nova revisão do documento de engenharia → diff R4.
 * Invocado por comando ("revisar especificação").
 */

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";

export function SpecUploadWidget() {
  const { criarSpecVersao } = useConversation();
  const [enviando, setEnviando] = useState(false);
  const [enviado, setEnviado] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setEnviando(true);
    try {
      await criarSpecVersao(file);
      // Sucesso: trava o widget para o usuário não reenviar (geraria "já existe")
      // e sinaliza que a comparação está rodando (acompanhada pela barra abaixo).
      setEnviado(true);
    } catch {
      // erro exibido pelo provider — mantém o botão ativo para nova tentativa
    } finally {
      setEnviando(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  if (enviado) {
    return (
      <WidgetFrame title="Revisão da especificação">
        <p className="text-xs text-fg-muted">
          ✓ Revisão enviada. Estou comparando com os requisitos aprovados do caso
          — acompanhe o progresso aqui na conversa. Quando terminar, te mostro o
          que mudou para você decidir.
        </p>
      </WidgetFrame>
    );
  }

  return (
    <WidgetFrame title="Revisão da especificação">
      <p className="mb-3 text-xs text-fg-muted">
        A especificação mudou? Envie a nova revisão do documento de engenharia —
        eu comparo com os requisitos aprovados do caso e te mostro o que mudou
        antes de aplicar qualquer coisa.
      </p>
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.docx,.xlsx"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFile(f);
        }}
      />
      <Button
        variant="secondary"
        size="sm"
        onClick={() => fileRef.current?.click()}
        loading={enviando}
      >
        Enviar nova revisão
      </Button>
    </WidgetFrame>
  );
}
