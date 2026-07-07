"use client";

/**
 * ProgressWidget — barra de progresso genérica para tarefas assíncronas
 * (análise R1, vinculação W3, avaliação R2, verificação R3, spec diff R4).
 * Alimentado pelo polling consolidado do ConversationProvider.
 */

import { useConversation, STAGE_LABELS } from "../conversation-provider";
import { WidgetFrame } from "./widget-frame";
import { useEffect, useState } from "react";

const clampPercent = (value: number) => Math.max(2, Math.min(100, value));

function optimisticCap(targetPercent: number) {
  if (targetPercent >= 100) return 100;
  if (targetPercent >= 90) return 98;
  if (targetPercent >= 88) return 96;
  if (targetPercent >= 80) return 92;
  if (targetPercent >= 70) return 86;
  if (targetPercent >= 40) return 78;
  if (targetPercent >= 25) return 54;
  if (targetPercent >= 10) return 34;
  return 18;
}

function progressSpeed(targetPercent: number) {
  if (targetPercent >= 90) return 0.28;
  if (targetPercent >= 80) return 0.42;
  if (targetPercent >= 70) return 0.55;
  if (targetPercent >= 40) return 0.72;
  return 0.48;
}

function useSmoothProgress(targetPercent: number) {
  const [displayPercent, setDisplayPercent] = useState(targetPercent);

  useEffect(() => {
    let frame = 0;
    let previous = performance.now();

    const tick = (now: number) => {
      const elapsedSeconds = Math.min(1, (now - previous) / 1000);
      previous = now;

      setDisplayPercent((current) => {
        if (targetPercent >= 100) return 100;
        if (targetPercent < current - 8) return targetPercent;

        const floor = Math.max(current, targetPercent);
        const cap = optimisticCap(targetPercent);
        if (floor >= cap) return floor;

        const remaining = cap - floor;
        const step = Math.max(
          0.08,
          Math.min(0.75, remaining * 0.035 + progressSpeed(targetPercent))
        );

        return Math.min(cap, floor + step * elapsedSeconds);
      });

      frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [targetPercent]);

  return clampPercent(displayPercent);
}

export function ProgressWidget() {
  const { taskProgress } = useConversation();

  const percent = clampPercent(taskProgress?.percent ?? 2);
  const displayPercent = useSmoothProgress(percent);
  const stage = taskProgress?.stage ?? "queued";
  const message = taskProgress?.message ?? "Iniciando...";

  return (
    <WidgetFrame>
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium text-fg-muted">
            {STAGE_LABELS[stage] ?? stage}
          </span>
          <span className="font-mono tabular-nums text-fg-subtle">
            {Math.round(displayPercent)}%
          </span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-canvas">
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-300 ease-out"
            style={{ width: `${displayPercent}%` }}
          />
        </div>
        {message && <p className="text-xs text-fg-subtle">{message}</p>}
      </div>
    </WidgetFrame>
  );
}
