"use client";

/**
 * VerificacaoWidget — verificação final (blocos 29-33), inline.
 * Três modos pelo passo ativo:
 * - "aguardando_proposta": upload da proposta final → executa R3
 * - "validar": resultado R3 + validação humana W5
 * - "dispensada": bifurcação Tipo 1 → validação W5 direta
 * Adaptado de verificacao-final-panel.tsx.
 */

import { useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  patecApi,
  type ResultadoValidado,
} from "@/lib/patec-api";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";

const CONFORMIDADE_VARIANT: Record<
  string,
  "success" | "warning" | "error" | "secondary"
> = {
  CONFORME: "success",
  PARCIAL: "warning",
  NAO_CONFORME: "error",
};

const RESULTADO_LABELS: Record<ResultadoValidado, string> = {
  CONFORME: "Conforme",
  CONFORME_COM_PENDENCIA: "Conforme com pendência",
  NAO_CONFORME: "Não conforme",
};

export function VerificacaoWidget({
  modo,
}: {
  modo: "aguardando_proposta" | "validar" | "dispensada";
}) {
  const { parecerId, snapshot, executarVerificacao, validarVerificacao, refreshSnapshot } =
    useConversation();
  const [enviando, setEnviando] = useState(false);
  const [validando, setValidando] = useState(false);
  const [resultado, setResultado] = useState<ResultadoValidado>("CONFORME");
  const [observacoes, setObservacoes] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const verificacao = snapshot?.verificacao;

  const enviarPropostaFinal = async (file: File) => {
    setEnviando(true);
    try {
      // Cria a rodada de proposta final e dispara a verificação R3
      const r = await patecApi.ciclo.criarRodada(parecerId, "PROPOSTA_REVISADA", {
        arquivo: file,
        propostaFinal: true,
      });
      await executarVerificacao(r.rodada_id);
    } catch {
      await refreshSnapshot();
    } finally {
      setEnviando(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const validar = async () => {
    setValidando(true);
    try {
      await validarVerificacao(resultado, observacoes || undefined);
    } catch {
      // erro exibido pelo provider
    } finally {
      setValidando(false);
    }
  };

  // --- Modo: aguardando proposta final ---
  if (modo === "aguardando_proposta") {
    return (
      <WidgetFrame>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.docx,.xlsx"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) enviarPropostaFinal(f);
          }}
        />
        <Button onClick={() => fileRef.current?.click()} loading={enviando}>
          Carregar proposta final e verificar
        </Button>
      </WidgetFrame>
    );
  }

  // --- Modos: validar (com resultado R3) e dispensada (W5 direto) ---
  return (
    <WidgetFrame title="Validação final (W5)">
      {/* Resultado da verificação LLM (R3) */}
      {modo === "validar" && verificacao?.resultado_ia && (
        <div className="mb-4 space-y-2">
          {verificacao.resultado_ia.resumo && (
            <p className="rounded-lg bg-canvas px-3 py-2 text-xs text-fg-muted">
              {verificacao.resultado_ia.resumo}
            </p>
          )}
          <div className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
            {verificacao.resultado_ia.itens.map((i) => (
              <div
                key={i.numero}
                className="rounded-lg border border-edge bg-canvas p-2"
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-fg-subtle">
                    #{i.numero}
                  </span>
                  <Badge
                    variant={CONFORMIDADE_VARIANT[i.conformidade] ?? "secondary"}
                    className="text-[10px]"
                  >
                    {i.conformidade.replace(/_/g, " ")}
                  </Badge>
                </div>
                {i.evidencia && (
                  <p className="mt-1 text-[11px] text-fg-muted">
                    “{i.evidencia}”
                  </p>
                )}
                {i.observacao && (
                  <p className="mt-0.5 text-[11px] text-fg-subtle">
                    {i.observacao}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Validação humana (W5) */}
      <div className="space-y-2">
        <div className="flex flex-wrap gap-2">
          {(Object.keys(RESULTADO_LABELS) as ResultadoValidado[]).map((r) => (
            <label
              key={r}
              className={`flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${
                resultado === r
                  ? "border-accent bg-accent-subtle text-fg"
                  : "border-edge bg-canvas text-fg-muted hover:border-edge-strong"
              }`}
            >
              <input
                type="radio"
                name="resultado-w5"
                className="sr-only"
                checked={resultado === r}
                onChange={() => setResultado(r)}
              />
              {RESULTADO_LABELS[r]}
            </label>
          ))}
        </div>
        <textarea
          value={observacoes}
          onChange={(e) => setObservacoes(e.target.value)}
          placeholder="Observações da validação (opcional)"
          rows={2}
          className="w-full resize-none rounded-lg border border-edge bg-canvas px-3 py-2 text-xs text-fg outline-none placeholder:text-fg-subtle focus:border-accent"
        />
        <div className="flex justify-end">
          <Button onClick={validar} loading={validando}>
            Validar verificação
          </Button>
        </div>
      </div>
    </WidgetFrame>
  );
}
