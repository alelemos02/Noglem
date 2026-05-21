"use client";

import { useState } from "react";
import { ChevronUp, MessageSquare } from "lucide-react";
import { ChatPanelWrapper } from "./chat-panel-wrapper";

export function ChatBar() {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-t border-border bg-surface">
      {/* Toggle strip */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
      >
        <ChevronUp
          className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${expanded ? "" : "rotate-180"}`}
        />
        <MessageSquare className="h-3.5 w-3.5 shrink-0" />
        <span className="font-medium">Chat IA</span>
        <span className="text-text-tertiary">— Converse com o especialista sobre o parecer tecnico</span>
      </button>

      {/* Expanded chat area */}
      {expanded && (
        <div className="h-[380px] border-t border-border">
          <ChatPanelWrapper />
        </div>
      )}
    </div>
  );
}
