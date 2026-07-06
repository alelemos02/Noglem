"use client";

import { useRef, useState } from "react";
import { MessageSquare, ChevronUp, ChevronDown } from "lucide-react";
import { ChatPanel } from "./chat-panel";
import { useWorkspace } from "./workspace-context";

export function ChatBar() {
  const [expanded, setExpanded] = useState(false);
  const { parecer, selectedItem, refreshAll } = useWorkspace();
  const chatInputRef = useRef<{ setInput: (text: string) => void }>(null);

  if (!parecer) return null;

  return (
    <div className="border-t-2 border-edge bg-surface-1">
      {/* Header strip */}
      <div className="flex items-center justify-between px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <MessageSquare className="h-4 w-4 shrink-0 text-accent" />
          <span className="text-sm font-semibold text-fg">Chat IA</span>
          {selectedItem ? (
            <span className="truncate text-xs text-fg-subtle">
              — Item {selectedItem.numero}: {selectedItem.descricao_requisito}
            </span>
          ) : (
            <span className="text-xs text-fg-subtle">
              — Especialista de IA para este parecer
            </span>
          )}
        </div>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="ml-4 flex shrink-0 items-center gap-1 rounded px-2 py-1 text-xs text-fg-subtle transition-colors hover:bg-surface-2 hover:text-fg"
        >
          {expanded ? (
            <>
              <ChevronDown className="h-3.5 w-3.5" />
              <span>Minimizar</span>
            </>
          ) : (
            <>
              <ChevronUp className="h-3.5 w-3.5" />
              <span>Ver histórico</span>
            </>
          )}
        </button>
      </div>

      {/*
       * Single ChatPanel — always mounted so message history is preserved.
       * showMessages toggles the messages DOM section; hideHeader removes
       * ChatPanel's own header (we have one above). fillHeight only applies
       * when expanded so the messages area fills the fixed-height container.
       */}
      <div className={`border-t border-edge ${expanded ? "h-[340px]" : ""}`}>
        <ChatPanel
          ref={chatInputRef}
          parecerId={parecer.id}
          contextItem={selectedItem}
          onTableUpdated={refreshAll}
          showMessages={expanded}
          hideHeader
          fillHeight={expanded}
        />
      </div>
    </div>
  );
}
