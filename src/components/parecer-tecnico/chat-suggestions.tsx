"use client";

import { type ItemParecerResponse } from "@/lib/patec-api";
import { STATUS_LABELS } from "./workspace-context";

interface ChatSuggestionsProps {
  item: ItemParecerResponse | null;
  onSelect: (text: string) => void;
}

export function ChatSuggestions({ item, onSelect }: ChatSuggestionsProps) {
  if (!item) return null;

  const statusLabel = STATUS_LABELS[item.status] || item.status;

  const suggestions = [
    `Por que o item ${item.numero} foi classificado como "${statusLabel}"?`,
    "O valor proposto pelo fornecedor atende ao requisito da engenharia?",
    "Quais normas tecnicas se aplicam a este item?",
    "Sugira uma acao requerida para este item.",
  ];

  return (
    <div className="flex flex-wrap gap-1.5 border-b border-edge px-4 py-2">
      {suggestions.map((text) => (
        <button
          key={text}
          onClick={() => onSelect(text)}
          className="rounded-full border border-edge px-2.5 py-1 text-xs text-fg-subtle transition-colors hover:bg-surface-2 hover:text-fg"
        >
          {text.length > 50 ? text.slice(0, 47) + "..." : text}
        </button>
      ))}
    </div>
  );
}
