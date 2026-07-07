"use client";

/**
 * ReanalisarWidget — confirmação do comando "reanalisar": dispara uma nova
 * análise R1 contra os requisitos aprovados do banco.
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";

export function ReanalisarWidget() {
  const { startAnalysis } = useConversation();
  const [running, setRunning] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  if (confirmed) return null;

  const handleConfirm = async () => {
    setRunning(true);
    try {
      await startAnalysis();
      setConfirmed(true);
    } catch {
      // erro exibido pelo provider
    } finally {
      setRunning(false);
    }
  };

  return (
    <WidgetFrame title="Reanalisar a proposta?">
      <p className="mb-3 text-xs text-fg-muted">
        Vou rodar a análise de novo contra os requisitos aprovados do caso.
        Os itens atuais serão regenerados (resultados idênticos podem vir do
        cache).
      </p>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={() => setConfirmed(true)}>
          Cancelar
        </Button>
        <Button size="sm" onClick={handleConfirm} loading={running}>
          Confirmar reanálise
        </Button>
      </div>
    </WidgetFrame>
  );
}
