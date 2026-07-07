"use client";

/**
 * FecharWidget — fechamento do caso (W6) inline: desfecho + observações.
 * Adaptado do FecharCasoDialog de ciclo-avaliacao-panel.tsx.
 */

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Desfecho } from "@/lib/patec-api";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";

const DESFECHO_INFO: Record<
  Desfecho,
  { label: string; variant: "success" | "warning" | "error" }
> = {
  APROVADO: { label: "Aprovado", variant: "success" },
  COM_PENDENCIA: { label: "Com pendência", variant: "warning" },
  REPROVADO: { label: "Reprovado", variant: "error" },
};

export function FecharWidget() {
  const { fecharCaso } = useConversation();
  const [desfecho, setDesfecho] = useState<Desfecho>("APROVADO");
  const [observacoes, setObservacoes] = useState("");
  const [fechando, setFechando] = useState(false);

  const handleFechar = async () => {
    setFechando(true);
    try {
      await fecharCaso(desfecho, observacoes || undefined);
    } catch {
      // erro exibido pelo provider
    } finally {
      setFechando(false);
    }
  };

  return (
    <WidgetFrame title="Fechar o caso (W6)">
      <div className="space-y-2">
        {(Object.keys(DESFECHO_INFO) as Desfecho[]).map((d) => (
          <label
            key={d}
            className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 transition-colors ${
              desfecho === d
                ? "border-accent bg-accent-subtle"
                : "border-edge bg-canvas hover:border-edge-strong"
            }`}
          >
            <input
              type="radio"
              name="desfecho"
              className="sr-only"
              checked={desfecho === d}
              onChange={() => setDesfecho(d)}
            />
            <Badge variant={DESFECHO_INFO[d].variant} dot>
              {DESFECHO_INFO[d].label}
            </Badge>
          </label>
        ))}
      </div>
      <textarea
        value={observacoes}
        onChange={(e) => setObservacoes(e.target.value)}
        placeholder="Observações do fechamento (opcional)"
        rows={2}
        className="mt-3 w-full resize-none rounded-lg border border-edge bg-canvas px-3 py-2 text-sm text-fg outline-none placeholder:text-fg-subtle focus:border-accent"
      />
      <div className="mt-3 flex justify-end">
        <Button onClick={handleFechar} loading={fechando}>
          Confirmar fechamento
        </Button>
      </div>
    </WidgetFrame>
  );
}
