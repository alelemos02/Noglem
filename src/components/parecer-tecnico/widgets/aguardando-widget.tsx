"use client";

/**
 * AguardandoWidget — ciclo aguardando resposta do fornecedor:
 * exportar carta de pendências, importar carta preenchida (.xlsx,
 * vínculo determinístico) ou carregar resposta livre (RodadaWidget).
 */

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";
import { RodadaWidget } from "./rodada-widget";

export function AguardandoWidget() {
  const { downloadCarta, reimportarRespostas } = useConversation();
  const [showRodada, setShowRodada] = useState(false);
  const [baixandoCarta, setBaixandoCarta] = useState(false);
  const [importando, setImportando] = useState(false);
  const [importMsg, setImportMsg] = useState("");
  const importRef = useRef<HTMLInputElement>(null);

  const handleCarta = async () => {
    setBaixandoCarta(true);
    try {
      await downloadCarta();
    } catch {
      // erro exibido pelo provider
    } finally {
      setBaixandoCarta(false);
    }
  };

  const handleImport = async (file: File) => {
    setImportando(true);
    setImportMsg("");
    try {
      const msg = await reimportarRespostas(file);
      setImportMsg(msg);
    } catch {
      // erro exibido pelo provider
    } finally {
      setImportando(false);
      if (importRef.current) importRef.current.value = "";
    }
  };

  if (showRodada) {
    return (
      <div className="space-y-2">
        <RodadaWidget onDone={() => setShowRodada(false)} />
        <button
          onClick={() => setShowRodada(false)}
          className="pl-1 text-xs text-fg-subtle hover:text-fg"
        >
          ← Voltar
        </button>
      </div>
    );
  }

  return (
    <WidgetFrame>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={handleCarta} loading={baixandoCarta}>
          Exportar carta de pendências
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setShowRodada(true)}>
          Carregar resposta do fornecedor
        </Button>
        <input
          ref={importRef}
          type="file"
          accept=".xlsx"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleImport(f);
          }}
        />
        <Button
          size="sm"
          variant="ghost"
          className="text-fg-subtle"
          onClick={() => importRef.current?.click()}
          loading={importando}
          title="Caminho estruturado: importa a carta preenchida (vínculos pelo ITEM_ID)"
        >
          Importar carta preenchida (.xlsx)
        </Button>
      </div>
      {importMsg && (
        <p className="mt-3 rounded-lg bg-success-subtle px-3 py-2 text-xs text-success-text">
          {importMsg}
        </p>
      )}
    </WidgetFrame>
  );
}
