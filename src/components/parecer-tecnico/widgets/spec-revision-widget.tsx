"use client";

/**
 * SpecRevisionWidget — decisão sobre o diff da revisão de especificação
 * (blocos 37-40 → W7). Adaptado de spec-revision-panel.tsx; o resultado
 * vira mensagem da JulIA em vez de alert().
 */

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { VersaoSpecResponse } from "@/lib/patec-api";
import { useConversation } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";

const CENARIO_INFO: Record<
  string,
  { label: string; tone: "success" | "info" | "warning" }
> = {
  A: { label: "Cenário A — nada mudou", tone: "success" },
  B: { label: "Cenário B — apenas itens novos", tone: "info" },
  C: { label: "Cenário C — itens alterados/removidos", tone: "warning" },
};

export function SpecRevisionWidget({ versao }: { versao: VersaoSpecResponse }) {
  const { aplicarSpec, descartarSpec } = useConversation();
  const diff = versao.resumo_diff;

  // Seleção default: todos os novos marcados (re-derivada se a versão mudar)
  const [versaoKey, setVersaoKey] = useState(versao.id);
  const [novosIncluidos, setNovosIncluidos] = useState<Set<number>>(
    () => new Set(diff?.novos.map((_, i) => i) ?? [])
  );
  if (versaoKey !== versao.id) {
    setVersaoKey(versao.id);
    setNovosIncluidos(new Set(diff?.novos.map((_, i) => i) ?? []));
  }

  const [aplicando, setAplicando] = useState(false);
  const [descartando, setDescartando] = useState(false);

  if (!diff) return null;

  const cenario = versao.cenario;

  const handleAplicar = async () => {
    setAplicando(true);
    try {
      await aplicarSpec(versao.id, [...novosIncluidos]);
    } catch {
      // erro exibido pelo provider
    } finally {
      setAplicando(false);
    }
  };

  const handleDescartar = async () => {
    setDescartando(true);
    try {
      await descartarSpec(versao.id);
    } catch {
      // erro exibido pelo provider
    } finally {
      setDescartando(false);
    }
  };

  return (
    <WidgetFrame title={`Revisão de especificação v${versao.numero_versao}`}>
      <div className="space-y-3">
        {cenario && (
          <Badge variant={CENARIO_INFO[cenario]?.tone ?? "info"} dot>
            {CENARIO_INFO[cenario]?.label ?? cenario}
          </Badge>
        )}
        {diff.resumo && (
          <p className="rounded-lg bg-canvas px-3 py-2 text-xs text-fg-muted">
            {diff.resumo}
          </p>
        )}

        {diff.alterados.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-warning-text">
              Alterados ({diff.alterados.length}) — voltam ao fornecedor perdendo
              a classificação prévia
            </p>
            {diff.alterados.map((a) => (
              <div
                key={a.numero}
                className="rounded-lg border border-warning/30 bg-warning-subtle/40 p-2"
              >
                <p className="text-xs font-bold text-fg">
                  Item #{a.numero}
                </p>
                {Object.entries(a.campos_alterados).map(([campo, m]) => (
                  <p key={campo} className="text-[11px] text-fg-muted">
                    <span className="font-mono">{campo}</span>:{" "}
                    <span className="text-danger/80 line-through">{m.antes}</span> →{" "}
                    <span className="text-success-text">{m.depois}</span>
                  </p>
                ))}
                {a.justificativa && (
                  <p className="text-[11px] italic text-fg-subtle">
                    {a.justificativa}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {diff.removidos.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-danger-text">
              Removidos ({diff.removidos.length}) — serão desativados (histórico
              preservado)
            </p>
            <p className="text-[11px] text-fg-muted">
              Itens: {diff.removidos.map((n) => `#${n}`).join(", ")}
            </p>
          </div>
        )}

        {diff.novos.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-info-text">
              Novos ({diff.novos.length}) — confirme quais incluir
            </p>
            {diff.novos.map((n, idx) => (
              <label
                key={idx}
                className="flex cursor-pointer items-start gap-2 rounded-lg border border-edge bg-canvas p-2"
              >
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={novosIncluidos.has(idx)}
                  onChange={(e) => {
                    setNovosIncluidos((prev) => {
                      const next = new Set(prev);
                      if (e.target.checked) next.add(idx);
                      else next.delete(idx);
                      return next;
                    });
                  }}
                />
                <div>
                  <p className="text-xs text-fg">
                    {n.descricao_requisito}
                  </p>
                  {n.valor_requerido && (
                    <p className="font-mono text-[11px] text-fg-muted">
                      {n.valor_requerido}
                    </p>
                  )}
                </div>
              </label>
            ))}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDescartar}
            loading={descartando}
            disabled={aplicando}
          >
            Descartar revisão
          </Button>
          <Button onClick={handleAplicar} loading={aplicando} disabled={descartando}>
            Aplicar revisão (W7)
          </Button>
        </div>
      </div>
    </WidgetFrame>
  );
}
