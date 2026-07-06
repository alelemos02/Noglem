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
            : "border border-edge bg-surface-1 text-fg"
        }`}
      >
        <div className="mb-1 flex items-center gap-2">
          <span
            className={`text-xs font-semibold ${isUser ? "text-white/70" : "text-fg-muted"}`}
          >
            {isUser ? "Voce" : "Especialista IA"}
          </span>
          {message.gerou_nova_tabela && (
            <span className="rounded-full border border-success/35 bg-success-subtle px-2 py-0.5 text-xs text-success">
              Tabela atualizada
            </span>
          )}
          {isStreaming && (
            <span className="inline-flex items-center gap-1 text-xs text-fg-subtle">
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
          className={`mt-1 text-xs ${isUser ? "text-white/50" : "text-fg-subtle"}`}
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
      <div className="max-w-[85%] rounded-lg border border-edge bg-surface-1 px-4 py-3 text-fg">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-xs font-semibold text-fg-muted">
            Especialista IA
          </span>
          <span className="inline-flex items-center gap-1 text-xs text-fg-subtle">
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
