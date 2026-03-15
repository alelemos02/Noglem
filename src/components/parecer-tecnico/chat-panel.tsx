"use client";

import {
  useEffect,
  useState,
  useRef,
  useCallback,
  forwardRef,
  useImperativeHandle,
} from "react";
import { Button } from "@/components/ui/button";
import { ChatMessage, StreamingMessage } from "./chat-message";
import {
  patecApi,
  type ChatMessageResponse,
  type ItemParecerResponse,
} from "@/lib/patec-api";

export interface ChatPanelHandle {
  setInput: (text: string) => void;
}

interface ChatPanelProps {
  parecerId: string;
  onTableUpdated: () => void;
  contextItem?: ItemParecerResponse | null;
  fillHeight?: boolean;
}

export const ChatPanel = forwardRef<ChatPanelHandle, ChatPanelProps>(
  function ChatPanel(
    { parecerId, onTableUpdated, contextItem, fillHeight },
    ref
  ) {
    const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
    const [inputValue, setInputValue] = useState("");
    const [regenerar, setRegenerar] = useState(false);
    const [sending, setSending] = useState(false);
    const [streamingContent, setStreamingContent] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useImperativeHandle(ref, () => ({
      setInput: (text: string) => {
        setInputValue(text);
        setTimeout(() => textareaRef.current?.focus(), 0);
      },
    }));

    const scrollToBottom = useCallback(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, []);

    useEffect(() => {
      let cancelled = false;
      async function load() {
        try {
          const data = await patecApi.chat.historico(parecerId);
          if (!cancelled) {
            setMessages(data.messages);
            setLoading(false);
          }
        } catch {
          if (!cancelled) setLoading(false);
        }
      }
      load();
      return () => {
        cancelled = true;
      };
    }, [parecerId]);

    useEffect(() => {
      scrollToBottom();
    }, [messages, streamingContent, scrollToBottom]);

    const handleSend = useCallback(async () => {
      const text = inputValue.trim();
      if (!text || sending) return;

      setError(null);
      setSending(true);
      setStreamingContent("");

      let messageToSend = text;
      if (contextItem) {
        const ctx = [
          `Item ${contextItem.numero}`,
          `Status: ${contextItem.status}`,
          contextItem.descricao_requisito &&
            `Requisito: ${contextItem.descricao_requisito}`,
          contextItem.valor_requerido &&
            `Valor requerido: ${contextItem.valor_requerido}`,
          contextItem.valor_fornecedor &&
            `Valor fornecedor: ${contextItem.valor_fornecedor}`,
          contextItem.norma_referencia &&
            `Norma: ${contextItem.norma_referencia}`,
        ]
          .filter(Boolean)
          .join(" - ");
        messageToSend = `[Contexto: ${ctx}]\n\n${text}`;
      }

      const tempUserMsg: ChatMessageResponse = {
        id: `temp-${Date.now()}`,
        papel: "user",
        conteudo: text,
        ordem: messages.length + 1,
        gerou_nova_tabela: false,
        criado_em: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempUserMsg]);
      setInputValue("");
      setRegenerar(false);

      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }

      let accumulated = "";
      try {
        await patecApi.chat.sendMessage(
          parecerId,
          messageToSend,
          regenerar,
          (chunk: string) => {
            accumulated += chunk;
            setStreamingContent(accumulated);
          },
          (data: { message_id: string; table_updated: boolean }) => {
            const assistantMsg: ChatMessageResponse = {
              id: data.message_id,
              papel: "assistant",
              conteudo: accumulated,
              ordem: messages.length + 2,
              gerou_nova_tabela: data.table_updated,
              criado_em: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, assistantMsg]);
            setStreamingContent("");

            if (data.table_updated) {
              onTableUpdated();
            }
          },
          (errorMsg: string) => {
            setError(errorMsg);
            setStreamingContent("");
          }
        );
      } catch {
        setError("Falha inesperada ao enviar mensagem");
        setStreamingContent("");
      } finally {
        setSending(false);
      }
    }, [
      inputValue,
      sending,
      regenerar,
      parecerId,
      messages.length,
      onTableUpdated,
      contextItem,
    ]);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    };

    const handleClearHistory = async () => {
      if (
        !confirm(
          "Tem certeza que deseja limpar todo o historico de conversa?"
        )
      )
        return;
      try {
        await patecApi.chat.clearHistory(parecerId);
        setMessages([]);
        setError(null);
      } catch {
        setError("Erro ao limpar historico");
      }
    };

    const handleTextareaInput = (
      e: React.ChangeEvent<HTMLTextAreaElement>
    ) => {
      setInputValue(e.target.value);
      const el = e.target;
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 150) + "px";
    };

    if (loading) {
      return (
        <div className="flex items-center justify-center py-8 text-sm text-text-tertiary">
          Carregando historico...
        </div>
      );
    }

    return (
      <div className={`flex flex-col ${fillHeight ? "h-full" : ""}`}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2">
          <p className="text-xs text-text-tertiary">
            Converse com o especialista de IA sobre o parecer tecnico.
          </p>
          {messages.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="text-xs text-text-tertiary hover:text-red-400"
              onClick={handleClearHistory}
            >
              Limpar
            </Button>
          )}
        </div>

        {/* Messages area */}
        <div
          className={`overflow-y-auto border-t border-border ${
            fillHeight ? "flex-1" : ""
          }`}
          style={
            fillHeight ? undefined : { maxHeight: "450px", minHeight: "120px" }
          }
        >
          <div className="p-4">
            {messages.length === 0 && !streamingContent && (
              <div className="py-8 text-center">
                <p className="mb-2 text-sm text-text-tertiary">
                  Nenhuma mensagem ainda.
                </p>
                <p className="text-xs text-text-disabled">
                  Exemplos: &quot;Por que o item 5 foi rejeitado?&quot; ou
                  &quot;A faixa de medicao do transmissor atende ISA-5.1?&quot;
                </p>
              </div>
            )}
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            {streamingContent && (
              <StreamingMessage content={streamingContent} />
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Error display */}
        {error && (
          <div className="mx-4 my-2 rounded-md bg-red-900/20 p-2 text-xs text-red-400">
            {error}
          </div>
        )}

        {/* Input area */}
        <div className="space-y-2 border-t border-border p-3">
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={handleTextareaInput}
                onKeyDown={handleKeyDown}
                placeholder="Digite sua pergunta..."
                disabled={sending}
                rows={1}
                className="w-full resize-none rounded-md border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-tertiary focus:border-accent focus:ring-1 focus:ring-accent disabled:opacity-50"
                style={{ minHeight: "38px" }}
              />
            </div>
            <Button
              onClick={handleSend}
              disabled={!inputValue.trim() || sending}
              size="sm"
              className="h-9"
            >
              {sending ? "..." : "Enviar"}
            </Button>
          </div>

          {/* Regeneration toggle */}
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={regenerar}
              onChange={(e) => setRegenerar(e.target.checked)}
              disabled={sending}
              className="rounded border-border text-accent focus:ring-accent"
            />
            <span className="text-xs text-text-secondary">
              Gerar nova tabela (incorporar alteracoes discutidas)
            </span>
          </label>
        </div>
      </div>
    );
  }
);
