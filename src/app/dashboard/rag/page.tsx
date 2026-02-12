"use client";

import { useState, useRef, useEffect } from "react";
import { MessageSquare, Send, Upload, FileText, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
}

export default function RagPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [documents, setDocuments] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      const newDocs = Array.from(files).map((f) => f.name);
      setDocuments((prev) => [...prev, ...newDocs]);
    }
  };

  const handleRemoveDocument = (index: number) => {
    setDocuments((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      // TODO: Conectar com a API do backend
      await new Promise((resolve) => setTimeout(resolve, 1500));

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `Esta é uma resposta simulada para: "${userMessage.content}".

Quando a API estiver conectada, as respostas serão baseadas nos documentos carregados e incluirão citações das fontes.`,
        sources: documents.length > 0 ? [documents[0]] : undefined,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Erro ao enviar mensagem:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-purple-500/10">
          <MessageSquare className="h-6 w-6 text-purple-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">RAG Chat</h1>
          <p className="text-muted-foreground">
            Converse com seus documentos usando IA generativa
          </p>
        </div>
        <Badge variant="outline" className="ml-auto">Dev</Badge>
      </div>

      <div className="flex flex-1 gap-4 overflow-hidden">
        {/* Documents Sidebar */}
        <Card className="w-64 flex-shrink-0">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Documentos</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-muted-foreground/25 p-4 transition-colors hover:border-primary/50">
              <Upload className="h-4 w-4" />
              <span className="text-sm">Adicionar PDF</span>
              <input
                type="file"
                accept=".pdf"
                multiple
                onChange={handleFileUpload}
                className="hidden"
              />
            </label>

            <ScrollArea className="h-[300px]">
              <div className="space-y-2">
                {documents.length === 0 ? (
                  <p className="text-center text-sm text-muted-foreground">
                    Nenhum documento carregado
                  </p>
                ) : (
                  documents.map((doc, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-2 rounded-lg bg-muted p-2"
                    >
                      <FileText className="h-4 w-4 flex-shrink-0" />
                      <span className="flex-1 truncate text-sm">{doc}</span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => handleRemoveDocument(index)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Chat Area */}
        <Card className="flex flex-1 flex-col">
          <CardContent className="flex flex-1 flex-col p-4">
            {/* Messages */}
            <ScrollArea className="flex-1 pr-4">
              <div className="space-y-4">
                {messages.length === 0 ? (
                  <div className="flex h-full items-center justify-center py-20">
                    <div className="text-center">
                      <MessageSquare className="mx-auto h-12 w-12 text-muted-foreground/50" />
                      <p className="mt-4 text-muted-foreground">
                        Carregue documentos e faça perguntas sobre eles
                      </p>
                    </div>
                  </div>
                ) : (
                  messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${
                        message.role === "user" ? "justify-end" : "justify-start"
                      }`}
                    >
                      <div
                        className={`max-w-[80%] rounded-lg p-3 ${
                          message.role === "user"
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted"
                        }`}
                      >
                        <p className="whitespace-pre-wrap text-sm">
                          {message.content}
                        </p>
                        {message.sources && message.sources.length > 0 && (
                          <div className="mt-2 border-t border-border/50 pt-2">
                            <p className="text-xs text-muted-foreground">
                              Fontes: {message.sources.join(", ")}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="rounded-lg bg-muted p-3">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-2 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
                        <div className="h-2 w-2 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
                        <div className="h-2 w-2 animate-bounce rounded-full bg-primary" />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            {/* Input */}
            <div className="mt-4 flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Faça uma pergunta sobre seus documentos..."
                className="flex-1 rounded-lg border border-input bg-background px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                disabled={isLoading}
              />
              <Button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                size="icon"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
