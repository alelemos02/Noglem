"use client";

/**
 * Thread — a conversa: timeline congelada + mensagens efêmeras da sessão +
 * streaming do chat RAG + passo ativo (fala da JulIA + widget interativo).
 */

import { useEffect, useRef } from "react";
import { useConversation } from "./conversation-provider";
import { mensagemDoPasso } from "./script";
import { TimelineEntryView, JuliaSpeech } from "./julia-message";
import { StepWidget } from "./step-widget";
import { ItemsBrowserWidget } from "./widgets/items-browser-widget";
import { RastreabilidadeWidget } from "./widgets/rastreabilidade-widget";
import { SpecUploadWidget } from "./widgets/spec-upload-widget";
import { UploadWidget } from "./widgets/upload-widget";
import { ReanalisarWidget } from "./widgets/reanalisar-widget";
import { FecharWidget } from "./widgets/fechar-widget";
import type { TimelineEntry } from "./types";

function EphemeralEntry({ entry }: { entry: TimelineEntry }) {
  if (entry.kind !== "widget") return <TimelineEntryView entry={entry} />;
  return (
    <div className="pl-10">
      {entry.widget === "items-browser" ? (
        <ItemsBrowserWidget focusNumero={entry.focusNumero} />
      ) : entry.widget === "rastreabilidade" ? (
        <RastreabilidadeWidget />
      ) : entry.widget === "upload" ? (
        <UploadWidget tipo={entry.tipo} hint={entry.hint} />
      ) : entry.widget === "spec-upload" ? (
        <SpecUploadWidget />
      ) : entry.widget === "reanalisar" ? (
        <ReanalisarWidget />
      ) : entry.widget === "fechar" ? (
        <FecharWidget />
      ) : null}
    </div>
  );
}

export function Thread() {
  const {
    snapshot,
    step,
    timeline,
    ephemeral,
    streamingContent,
    actionError,
    clearActionError,
  } = useConversation();

  const endRef = useRef<HTMLDivElement>(null);
  const stepId = step?.id;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [timeline.length, ephemeral.length, streamingContent, stepId]);

  if (!snapshot || !step) return null;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-10">
        {/* Passado congelado (derivado do BD) */}
        {timeline.map((entry) => (
          <TimelineEntryView key={entry.key} entry={entry} />
        ))}

        {/* Passo ativo: fala da JulIA + widget interativo */}
        <JuliaSpeech markdown={mensagemDoPasso(step, snapshot)} />
        <div className="pl-10">
          <StepWidget />
        </div>

        {/* Mensagens efêmeras da sessão (chat livre, avisos, widgets por comando) */}
        {ephemeral.map((entry) => (
          <EphemeralEntry key={entry.key} entry={entry} />
        ))}

        {/* Resposta do chat RAG em streaming */}
        {streamingContent && (
          <JuliaSpeech markdown={streamingContent} streaming />
        )}

        {/* Erro de ação */}
        {actionError && (
          <div className="ml-10 flex items-start justify-between gap-3 rounded-lg border border-danger/30 bg-danger-subtle px-4 py-3">
            <p className="text-sm text-danger-text">{actionError}</p>
            <button
              onClick={clearActionError}
              className="shrink-0 text-xs text-fg-subtle hover:text-fg"
            >
              fechar
            </button>
          </div>
        )}

        <div ref={endRef} />
      </div>
    </div>
  );
}
