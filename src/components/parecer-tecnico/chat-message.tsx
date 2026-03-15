"use client";

import Markdown from "react-markdown";
import type { ChatMessageResponse } from "@/lib/patec-api";

interface ChatMessageProps {
  message: ChatMessageResponse;
  isStreaming?: boolean;
}

export function ChatMessage({ message, isStreaming }: ChatMessageProps) {
  const isUser = message.papel === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 ${
          isUser
            ? "bg-accent text-white"
            : "border border-border bg-surface text-text-primary"
        }`}
      >
        <div className="mb-1 flex items-center gap-2">
          <span
            className={`text-xs font-semibold ${isUser ? "text-white/70" : "text-text-secondary"}`}
          >
            {isUser ? "Voce" : "Especialista IA"}
          </span>
          {message.gerou_nova_tabela && (
            <span className="rounded-full border border-green-700/50 bg-green-900/40 px-2 py-0.5 text-xs text-green-400">
              Tabela atualizada
            </span>
          )}
          {isStreaming && (
            <span className="inline-flex items-center gap-1 text-xs text-text-tertiary">
              <span className="animate-pulse">●</span> digitando...
            </span>
          )}
        </div>
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm">{message.conteudo}</p>
        ) : (
          <div className="prose prose-sm prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-headings:my-2 text-sm">
            <Markdown>{message.conteudo}</Markdown>
          </div>
        )}
        <p
          className={`mt-1 text-xs ${isUser ? "text-white/50" : "text-text-tertiary"}`}
        >
          {new Date(message.criado_em).toLocaleTimeString("pt-BR", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>
    </div>
  );
}

interface StreamingMessageProps {
  content: string;
}

export function StreamingMessage({ content }: StreamingMessageProps) {
  return (
    <div className="mb-3 flex justify-start">
      <div className="max-w-[85%] rounded-lg border border-border bg-surface px-4 py-3 text-text-primary">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-xs font-semibold text-text-secondary">
            Especialista IA
          </span>
          <span className="inline-flex items-center gap-1 text-xs text-text-tertiary">
            <span className="animate-pulse">●</span> digitando...
          </span>
        </div>
        <div className="prose prose-sm prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-headings:my-2 text-sm">
          <Markdown>{content}</Markdown>
        </div>
      </div>
    </div>
  );
}
