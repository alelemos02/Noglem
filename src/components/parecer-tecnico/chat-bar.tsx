"use client";

import { useState } from "react";
import { MessageSquare, Minimize2, Maximize2 } from "lucide-react";
import { ChatPanelWrapper } from "./chat-panel-wrapper";

export function ChatBar() {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="border-t border-border bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 shrink-0 text-text-secondary" />
          <span className="text-sm font-semibold text-text-primary">Chat IA</span>
          <span className="text-xs text-text-tertiary">
            — Converse com o especialista sobre este parecer
          </span>
        </div>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="rounded-md p-1 text-text-tertiary transition-colors hover:bg-surface-hover hover:text-text-primary"
          aria-label={expanded ? "Minimizar chat" : "Expandir chat"}
        >
          {expanded ? (
            <Minimize2 className="h-3.5 w-3.5" />
          ) : (
            <Maximize2 className="h-3.5 w-3.5" />
          )}
        </button>
      </div>

      {/* Chat panel — always mounted to preserve message history */}
      <div
        className={`overflow-hidden border-t border-border transition-all duration-200 ${
          expanded ? "h-[360px]" : "h-0"
        }`}
      >
        <div className="h-[360px]">
          <ChatPanelWrapper />
        </div>
      </div>
    </div>
  );
}
