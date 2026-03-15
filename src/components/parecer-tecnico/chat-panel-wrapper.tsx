"use client";

import { useRef } from "react";
import { useWorkspace } from "./workspace-context";
import { ChatPanel } from "./chat-panel";
import { ChatSuggestions } from "./chat-suggestions";

export function ChatPanelWrapper() {
  const { parecer, selectedItem, refreshAll } = useWorkspace();
  const chatInputRef = useRef<{ setInput: (text: string) => void }>(null);

  if (!parecer) return null;

  const handleSuggestionSelect = (text: string) => {
    chatInputRef.current?.setInput(text);
  };

  return (
    <div className="flex h-full flex-col">
      {/* Context header */}
      {selectedItem && (
        <div className="border-b border-border bg-blue-900/20 px-4 py-2">
          <p className="text-xs font-medium text-blue-400">
            Discutindo Item {selectedItem.numero}
          </p>
          <p className="line-clamp-1 text-xs text-blue-400/70">
            {selectedItem.descricao_requisito}
          </p>
        </div>
      )}

      {/* Suggestions */}
      <ChatSuggestions item={selectedItem} onSelect={handleSuggestionSelect} />

      {/* Chat panel fills remaining space */}
      <div className="flex-1 overflow-hidden">
        <ChatPanel
          ref={chatInputRef}
          parecerId={parecer.id}
          contextItem={selectedItem}
          onTableUpdated={async () => {
            await refreshAll();
          }}
          fillHeight
        />
      </div>
    </div>
  );
}
